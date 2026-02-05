import asyncio
import json
import logging
from collections import deque
from datetime import datetime
from typing import Optional

import redis.asyncio as redis

from core.settings import settings
from schemas.sensors import SensorMessage
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
        subscription_topics: Optional[list[str]] = None,
    ):
        super().__init__(mqtt_client=mqtt_client, redis_client=redis_client)
        self.subscription_topics = subscription_topics or ["devices/#"]
        self._buffer = deque()
        self._last_flush = 0.0
        self._flush_interval = 5.0  # seconds
        self._batch_size = 10
        self._topic_cache = {}

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

    async def _on_message(self, topic: str, payload: bytes, qos: int, properties) -> None:
        logger.debug(f"[MQTT] Received message: topic={topic}")
        if topic not in self._topic_cache:
            self._topic_cache[topic] = self._extract_device_id(topic)
        device_id = self._topic_cache[topic]

        if not device_id:
            logger.warning(f"[MQTT] Invalid device_id for topic: {topic}")
            return

        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            logger.error(f"[MQTT] JSON decode error: {e}")
            return

        messages = []
        online_status = True  # дефолт

        try:
            if "online" in data:
                online_val = data["online"]
                if isinstance(online_val, str):
                    online_status = online_val.lower() == "true"
                elif isinstance(online_val, bool):
                    online_status = online_val
                else:
                    logger.warning(
                        f"[MQTT] Unexpected type for 'online' ({type(online_val)}) in topic {topic}"
                    )
                    online_status = False
            for sensor_key, sensor_value in data.items():
                if sensor_key == "online":
                    continue
                if not isinstance(sensor_value, dict):
                    logger.debug(
                        f"[MQTT] Skip non-dict item '{sensor_key}' in topic {topic}"
                    )
                    continue
                for param_key, param_value in sensor_value.items():
                    if not isinstance(param_value, dict):
                        logger.debug(
                            f"[MQTT] Skip non-dict param '{param_key}' in {sensor_key} for {device_id}"
                        )
                        continue
                    value = param_value.get("value")
                    unit = param_value.get("unit")

                    if unit is None:
                        logger.warning(
                            f"[MQTT] Missing 'unit' for {sensor_key}.{param_key} in device {device_id}"
                        )
                        continue
                    full_device_id = (
                        f"{sensor_key.upper()}_{param_key.upper()}_{device_id.upper()}"
                    )
                    try:
                        msg = SensorMessage(
                            device_id=full_device_id,
                            timestamp=datetime.now().isoformat(),
                            data=param_value,
                            value=value,
                            unit=unit,
                            online=online_status,
                        )
                        messages.append(msg)
                    except Exception as e:
                        logger.error(
                            f"[MQTT] Failed to create SensorMessage for {full_device_id}: {e}"
                        )

        except Exception as e:
            logger.error(f"[MQTT] Error during message processing: {e}")
            return
        if messages:
            self._buffer.extend(messages)
            current_time = asyncio.get_event_loop().time()
            if (
                len(self._buffer) >= self._batch_size
                or current_time - self._last_flush >= self._flush_interval
            ):
                try:
                    await self._flush_buffer()
                    self._last_flush = current_time
                except Exception as e:
                    logger.error(f"[MQTT] Flush buffer error: {e}")
            try:
                tasks = [publish_to_redis(self.redis_client, msg) for msg in messages]
                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for i, result in enumerate(results):
                        if isinstance(result, Exception):
                            logger.error(
                                f"[MQTT] Redis publish failed for message {i}: {result}"
                            )
            except Exception as e:
                logger.error(f"[MQTT] Redis publish error: {e}")
        else:
            logger.debug(f"[MQTT] No valid sensor messages from topic {topic}")

    def _extract_device_id(self, topic: str) -> Optional[str]:
        parts = topic.strip("/").split("/")
        return parts[-1] if len(parts) >= 2 else None

    async def _flush_buffer(self):
        if not self._buffer:
            return
        messages = list(self._buffer)
        self._buffer.clear()
        try:
            await save_batch_to_db(
                self.db_session,
                messages,
                retention_days=settings.app_settings.keep_data,
            )
        except Exception as e:
            logger.error(f"[MQTT] Failed to save batch to DB: {e}", exc_info=True)

    async def _cleanup(self):
        await super()._cleanup()
        if self._buffer:
            await self._flush_buffer()
        for topic in self.subscription_topics:
            await safe_unsubscribe(self.mqtt_client, topic)
