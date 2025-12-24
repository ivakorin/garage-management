import asyncio
import json
import logging
from typing import Callable, Dict, Optional

import aiomqtt

from core.settings import settings

logging.basicConfig(level=settings.log.level)
logger = logging.getLogger(__name__)

class AsyncMQTTClient:
    def __init__(self, broker: str, port: int = 1883, username: str = None, password: str = None, client_id: str = None):
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.identifier = client_id or "gm-gateway"
        self.client: Optional[aiomqtt.Client] = None
        self.subscriptions: Dict[str, Callable] = {}
        self._is_connected = False
        self._running = False

    async def connect(self):
        """Инициируем подключение к MQTT (не блокируем выполнение)."""
        if self._running:
            return

        self._running = True
        try:
            self.client = aiomqtt.Client(
                hostname=self.broker,
                port=self.port,
                username=self.username,
                password=self.password,
                identifier=self.identifier
            )
            # Запускаем _run() в фоне
            asyncio.create_task(self._run())
            logger.info("MQTT connection task started")
        except Exception as e:
            logger.error(f"MQTT connect failed: {e}")
            self._running = False
            raise


    async def _run(self):
        """Основной цикл работы MQTT-клиента с автоматическим переподключением."""
        while self._running:
            try:
                async with self.client:  # Соединение закрывается автоматически при выходе
                    self._is_connected = True
                    logger.info("MQTT client connected")

                    # Подписываемся на все топики
                    for topic in self.subscriptions.keys():
                        await self.client.subscribe(topic)

                    # Обработка сообщений
                    async for message in self.client.messages:
                        topic = str(message.topic)
                        try:
                            payload = json.loads(message.payload.decode())
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in message: {message.payload}")
                            continue

                        for subscribed_topic, callback in self.subscriptions.items():
                            if subscribed_topic == topic:
                                asyncio.create_task(callback(payload))

            except aiomqtt.MqttError as e:
                self._is_connected = False
                logger.warning(f"MQTT connection lost: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Unexpected MQTT error: {e}")
                self._running = False

    async def publish(self, topic: str, payload: dict):
        """Публикация сообщения."""
        if not self._is_connected or not self.client:
            raise ConnectionError("MQTT client is not connected")
        payload_str = json.dumps(payload)
        await self.client.publish(topic, payload_str)

    def subscribe(self, topic: str, callback: Callable):
        """Регистрируем callback для топика."""
        self.subscriptions[topic] = callback

    async def unsubscribe(self, topic: str):
        """Отписываемся от топика."""
        if self.client and self._is_connected:
            await self.client.unsubscribe(topic)
        self.subscriptions.pop(topic, None)

    async def disconnect(self):
        """Асинхронное отключение (не ждём завершения _run())."""
        self._running = False  # Это остановит цикл в _run()
        self._is_connected = False
        logger.info("MQTT disconnect initiated")
