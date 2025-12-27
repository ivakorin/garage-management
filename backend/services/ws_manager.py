import asyncio
import json
import logging
from typing import List

import redis.asyncio as redis
from fastapi import WebSocket

from core.settings import settings
from schemas.sensor import SensorMessage  # ваш класс сообщения

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self, redis_url: str, channel: str = "sensor_updates"):
        self.clients: List[WebSocket] = []
        self.redis_url = redis_url
        self.channel = channel
        self.redis_client: redis.Redis | None = None
        self.listener_task: asyncio.Task | None = None

    async def connect(self, websocket: WebSocket):
        """Принять новое WebSocket‑соединение."""
        await websocket.accept()
        self.clients.append(websocket)
        logger.info(f"WebSocket подключён: {len(self.clients)} клиентов")

    def disconnect(self, websocket: WebSocket):
        """Отсоединить клиента."""
        if websocket in self.clients:
            self.clients.remove(websocket)
            logger.info(f"WebSocket отключён: {len(self.clients)} клиентов")

    async def _listen_redis(self):
        """Фоновый процесс: слушает Redis и рассылает сообщения клиентам."""
        try:
            self.redis_client = redis.from_url(self.redis_url)
            pubsub = self.redis_client.pubsub()
            await pubsub.subscribe(self.channel)

            logger.info(f"Подписан на Redis-канал: {self.channel}")

            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                if message and message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        sensor_msg = SensorMessage(**data)  # Парсим в SensorMessage
                        await self._broadcast(sensor_msg)
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.error(f"Не удалось разобрать сообщение из Redis: {e}")
        except Exception as e:
            logger.error(f"Ошибка слушателя Redis: {e}", exc_info=True)
        finally:
            await pubsub.unsubscribe(self.channel)
            await self.redis_client.close()

    async def _broadcast(self, message: SensorMessage):
        """Рассылать сообщение всем подключённым WebSocket‑клиентам."""
        for client in self.clients:
            try:
                await client.send_text(message.model_dump_json())
            except Exception as e:
                logger.error(f"Ошибка отправки клиенту: {e}")
                self.disconnect(client)  # Удаляем неотзывчивого клиента

    async def startup(self):
        """Запустить фоновый слушатель Redis."""
        self.listener_task = asyncio.create_task(self._listen_redis())

    async def shutdown(self):
        """Остановить слушатель и закрыть соединения."""
        if self.listener_task:
            self.listener_task.cancel()
            try:
                await self.listener_task
            except asyncio.CancelledError:
                pass

        for client in self.clients:
            await client.close()
        self.clients.clear()

        if self.redis_client:
            await self.redis_client.close()


ws_manager = WebSocketManager(redis_url=settings.redis.url, channel="sensor_updates")
