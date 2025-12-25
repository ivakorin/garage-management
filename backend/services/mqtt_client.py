import asyncio
import json
import logging
from typing import Callable, Dict, Optional

import aiomqtt

from core.settings import settings

logging.basicConfig(level=settings.log.level)
logger = logging.getLogger(__name__)



class AsyncMQTTClient:
    def __init__(
        self,
        broker: str,
        port: int = 1883,
        username: str = None,
        password: str = None,
        client_id: str = None
    ):
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.identifier = client_id or "gm-gateway"
        self.client: Optional[aiomqtt.Client] = None
        self.subscriptions: Dict[str, Callable] = {}
        self._is_connected = False
        self._running = False
        self._reconnect_task: Optional[asyncio.Task] = None  # Задача для переподключения

    async def connect(self):
        """Инициирует подключение и запускает фоновый процесс."""
        if self._running:
            return

        self._running = True
        logger.info(f"Подключение к MQTT {self.broker}:{self.port}")

        # Запускаем фоновое переподключение
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self):
        """Фоновый цикл: пытается подключиться, переподключается при ошибках."""
        while self._running:
            try:
                # Создаём клиент
                self.client = aiomqtt.Client(
                    hostname=self.broker,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    identifier=self.identifier
                )

                async with self.client:
                    self._is_connected = True
                    logger.info("MQTT client connected")

                    # Подписываемся на топики
                    for topic in self.subscriptions.keys():
                        try:
                            await self.client.subscribe(topic)
                            logger.debug(f"Подписан на {topic}")
                        except Exception as e:
                            logger.warning(f"Не удалось подписаться на {topic}: {e}")

                    # Обработка сообщений
                    async for message in self.client.messages:
                        topic = str(message.topic)
                        try:
                            payload = json.loads(message.payload.decode())
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON в сообщении: {message.payload}")
                            continue

                        for subscribed_topic, callback in self.subscriptions.items():
                            if subscribed_topic == topic:
                                try:
                                    asyncio.create_task(callback(payload))
                                except Exception as e:
                                    logger.error(f"Ошибка в callback для {topic}: {e}", exc_info=True)

            except aiomqtt.MqttError as e:
                self._is_connected = False
                logger.warning(f"MQTT соединение потеряно: {e}. Повтор через 5 сек...")
                await asyncio.sleep(5)  # Только здесь задержка — не влияет на основной цикл
            except Exception as e:
                logger.error(f"Неожиданная ошибка MQTT: {e}", exc_info=True)
                self._is_connected = False
                await asyncio.sleep(5)
            finally:
                if self.client:
                    try:
                        await self.client.disconnect()
                    except Exception:
                        pass

    async def publish(
        self,
        topic: str,
        payload: dict,
        qos: int = 0,
        retain: bool = False
    ) -> bool:
        """Публикует сообщение. Возвращает True при успехе."""
        if not self._is_connected or not self.client:
            logger.warning(f"MQTT не подключён. Пропуск публикации: {topic}")
            return False

        try:
            payload_str = json.dumps(payload)
            await self.client.publish(topic, payload_str, qos=qos, retain=retain)
            logger.debug(f"Отправлено MQTT: {topic} → {payload_str}")
            return True
        except aiomqtt.MqttError as e:
            self._is_connected = False
            logger.error(f"Ошибка MQTT publish: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при публикации {topic}: {e}", exc_info=True)
            return False

    def subscribe(self, topic: str, callback: Callable):
        """Регистрирует callback для топика."""
        self.subscriptions[topic] = callback
        logger.debug(f"Подписка зарегистрирована: {topic}")

    async def unsubscribe(self, topic: str):
        """Отписывается от топика."""
        if topic in self.subscriptions:
            if self.client and self._is_connected:
                try:
                    await self.client.unsubscribe(topic)
                    logger.debug(f"Отписан от {topic}")
                except Exception as e:
                    logger.warning(f"Ошибка при отписке от {topic}: {e}")
            self.subscriptions.pop(topic, None)

    async def disconnect(self):
        """Асинхронное отключение."""
        self._running = False
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        if self.client:
            try:
                await self.client.disconnect()
            except Exception:
                pass
        self._is_connected = False
        logger.info("MQTT клиент отключён")
