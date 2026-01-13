import asyncio
import logging

from core.settings import settings
from services.mqtt_client import AsyncMQTTClient

logger = logging.getLogger(__name__)


class MQTTCollector:
    def __init__(self):
        self.mqtt_client = AsyncMQTTClient(
            broker=settings.mqtt.host,
            port=settings.mqtt.port,
            username=settings.mqtt.username,
            password=settings.mqtt.password,
            client_id="gm-subscriber",
        )
        self._is_running = False

    async def collect(self):
        self._is_running = True
        try:
            await self.mqtt_client.connect()

            # Подписываемся на ВСЕ топики в /devices/
            await self.mqtt_client.subscribe(topic="devices/#", callback=self._on_message)

            logger.info("MQTT client started, listening to '/devices/#'")

            while self._is_running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"MQTT Client Error: {e}")
        finally:
            await self.mqtt_client.disconnect()
            logger.info("MQTT client disconnected")

    async def _on_message(self, topic: str, payload: bytes, qos: int, properties):
        try:
            if not topic.startswith("devices/"):
                return

            subtopic = topic[len("devices/") :]  # Получаем часть после /devices/
            logger.debug(f"Subtopic: {subtopic}")
            message = payload.decode("utf-8")
            logger.debug(f"[{topic}] {message}")

            device_id = subtopic.split("/")[0]
            logger.debug(f"Device ID: {device_id}")
            self._handle_device_message(device_id, message)

        except UnicodeDecodeError:
            logger.warning(f"[{topic}] Payload could not be decoded")
        except Exception as e:
            logger.error(f"Message processing error: {e}")

    def _handle_device_message(self, device_id: str, message: str):
        """Ваша логика обработки данных с устройства"""
        logger.info(f"Data from the device {device_id}: {message}")

    def stop(self):
        self._is_running = False


if __name__ == "__main__":
    client = MQTTCollector()
    asyncio.run(client.collect())
