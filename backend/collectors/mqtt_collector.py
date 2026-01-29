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
        self._flush_interval = 1.0  # seconds
        self._batch_size = 100
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

    async def _on_message(self, topic: str, payload: bytes, qos: int, properties):
        logger.debug(f"[MQTT] Received raw message: topic={topic}, size={len(payload)} B")
        if topic not in self._topic_cache:
            self._topic_cache[topic] = self._extract_device_id(topic)
        device_id = self._topic_cache[topic]
        if not device_id:
            logger.warning(f"[MQTT] Cannot extract device_id from topic: {topic}")
            return
        try:
            data = json.loads(payload)  # Работает напрямую с bytes
        except json.JSONDecodeError as e:
            logger.error(
                f"[MQTT] Invalid JSON in payload (topic={topic}): {e}, raw={payload}"
            )
            return
        messages = []
        redis_tasks = []
        for key, value in data.items():
            if key == "online":
                continue

            message = SensorMessage(
                device_id=f"{key.upper()}_{device_id}",
                timestamp=datetime.now().isoformat(),
                data=value,
                value=value.get("value"),
                unit=value.get("unit"),
                online=True,
            )
            messages.append(message)
            redis_tasks.append(publish_to_redis(self.redis_client, message))

        self._buffer.extend(messages)
        current_time = asyncio.get_event_loop().time()

        if (
            len(self._buffer) >= self._batch_size
            or current_time - self._last_flush >= self._flush_interval
        ):
            await self._flush_buffer()
            self._last_flush = current_time
        if redis_tasks:
            await asyncio.gather(*redis_tasks, return_exceptions=True)

    def _extract_device_id(self, topic: str) -> Optional[str]:
        parts = topic.strip("/").split("/")
        return parts[-2] if len(parts) >= 2 else None

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
