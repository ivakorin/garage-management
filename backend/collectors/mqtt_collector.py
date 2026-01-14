import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.settings import settings
from crud.sensor import DeviceDataCRUD
from schemas.sensor import SensorMessage, DeviceUpdateSchema
from services.base_collector import BaseCollector
from services.batch_saver import save_batch_to_db
from services.mqtt_client import AsyncMQTTClient
from services.mqtt_helper import (
    safe_unsubscribe,
    safe_subscribe,
)
from services.redis_publisher import publish_to_redis

logger = logging.getLogger(__name__)


class MQTTCollector(BaseCollector):
    """
    Data collector from MQTT topics.
    Subscribes to topics, parses messages and passes them to the handler.
    It does not publish data to MQTT (the devices do it themselves).
    """

    def __init__(
        self,
        mqtt_client: Optional[AsyncMQTTClient] = None,
        redis_client: Optional[redis.Redis] = None,
        db_session: Optional[AsyncSession] = None,
        subscription_topics: Optional[list[str]] = None,
    ):
        super().__init__(
            mqtt_client=mqtt_client, redis_client=redis_client, db_session=db_session
        )
        self.subscription_topics = subscription_topics or ["devices/#"]

    async def collect(self):
        self._is_running = True
        try:
            await self.mqtt_client.connect()
            for topic in self.subscription_topics:
                success = await safe_subscribe(
                    self.mqtt_client,
                    topic,
                    self._on_message,
                )
                if not success:
                    logger.error(f"Failed to subscribe to topic: {topic}")
                    return
                logger.info(f"Successfully subscribed to topic: {topic}")

            logger.info("MQTT client started, listening to '/devices/#'")

            while self._is_running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"MQTT Client Error: {e}")
        finally:
            await self.mqtt_client.disconnect()
            logger.info("MQTT client disconnected")

    async def _on_message(self, topic: str, payload: bytes, qos: int, properties):
        logger.debug(f"[MQTT] Received raw message: topic={topic}, size={len(payload)} B")
        device_id = self._extract_device_id(topic)
        try:
            payload_str = payload.decode("utf-8")
        except UnicodeDecodeError as e:
            logger.error(f"[MQTT] Failed to decode payload (topic={topic}): {e}")
            return
        split_topic = topic.split("/")
        if "online" in split_topic:
            try:
                online = json.loads(payload_str).strip().lower() == "true"
            except AttributeError as e:
                online = payload_str
            devices = await DeviceDataCRUD.search(
                pattern=device_id, session=self.db_session
            )
            if not devices:
                logger.warning(f"[MQTT] Cannot find device {device_id}")
                return
            for device in devices:
                update_online = DeviceUpdateSchema(
                    device_id=device,
                    online=online,
                    updated_at=datetime.now(),
                )
                try:
                    await DeviceDataCRUD.update(
                        data=update_online, session=self.db_session
                    )
                except Exception as e:
                    logger.error(
                        f"[MQTT] Unexpected error when try to update device state: {e}"
                    )
                    continue
            return
        try:
            try:
                data = json.loads(payload_str)
            except json.JSONDecodeError as e:
                logger.error(
                    f"[MQTT] Invalid JSON in payload (topic={topic}): {e}, raw={payload_str}"
                )
                return
            if not device_id:
                logger.warning(f"[MQTT] Cannot extract device_id from topic: {topic}")
                return
            logger.debug(f"[MQTT] Extracted device_id={device_id} from topic={topic}")
            for key, value in data.items():
                if key == "online":
                    continue
                message = SensorMessage(
                    device_id=f"{str(key.upper())}_{device_id}",
                    timestamp=datetime.now().isoformat(),
                    data=value,
                    value=value.get("value"),
                    unit=value.get("unit"),
                    online=True,
                )
                await asyncio.gather(
                    publish_to_redis(self.redis_client, message),
                    save_batch_to_db(
                        self.db_session,
                        [message],
                        retention_days=settings.app_settings.keep_data,
                    ),
                )
                logger.debug(f"[MQTT] Message successfully published to redis: {message}")
        except Exception as e:
            logger.critical(f"[MQTT] Unexpected error in _on_message: {e}", exc_info=True)

    def _extract_device_id(self, topic: str) -> Optional[str]:
        parts = topic.strip("/").split("/")
        if len(parts) >= 2:
            return parts[-2]
        return None

    async def _cleanup(self):
        await super()._cleanup()
        for topic in self.subscription_topics:
            await safe_unsubscribe(self.mqtt_client, topic)
