import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Dict, Set, Optional

import redis.asyncio as redis
from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from core.settings import settings

router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)

# Оптимизированный Redis-клиент
redis_client = redis.Redis(
    host=settings.redis.host,
    port=settings.redis.port,
    db=settings.redis.db,
    decode_responses=False,
    socket_timeout=5,
    socket_connect_timeout=2,
)

# Использование WeakSet для более эффективного хранения подключений
active_connections: Dict[WebSocket, Set[str]] = {}


@asynccontextmanager
async def redis_pubsub_context():
    pubsub = redis_client.pubsub()
    try:
        await pubsub.subscribe("sensor_updates")
        yield pubsub
    finally:
        await pubsub.unsubscribe("sensor_updates")
        await pubsub.close()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections[websocket] = set()
    listener_task: Optional[asyncio.Task] = None

    try:
        listener_task = asyncio.create_task(redis_listener(websocket))
        try:
            while True:
                try:
                    message = await asyncio.wait_for(
                        websocket.receive_text(), timeout=60.0
                    )
                    try:
                        data = json.loads(message)
                        action = data.get("action")
                        sensor_id = data.get("sensor_id")
                        if action == "subscribe":
                            if sensor_id:
                                active_connections[websocket].add(sensor_id)
                                await websocket.send_json(
                                    {"status": "subscribed", "sensor_id": sensor_id}
                                )
                        elif action == "unsubscribe":
                            if sensor_id in active_connections[websocket]:
                                active_connections[websocket].remove(sensor_id)
                                await websocket.send_json(
                                    {"status": "unsubscribed", "sensor_id": sensor_id}
                                )
                        elif action == "get_subscriptions":
                            await websocket.send_json(
                                {"subscriptions": list(active_connections[websocket])}
                            )
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning(f"Invalid JSON: {e}")
                        await websocket.send_json({"error": "Invalid message format"})

                except asyncio.TimeoutError:
                    try:
                        await websocket.send_json({"type": "ping"})
                    except:
                        break  # Если не удалось отправить пинг, завершаем
                    continue  # Продолжаем цикл
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"Client error: {e}", exc_info=True)
            pass

    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        if websocket in active_connections:
            del active_connections[websocket]

        if listener_task:
            listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass

        try:
            await websocket.close()
        except:
            pass


async def redis_listener(websocket: WebSocket):
    async with redis_pubsub_context() as pubsub:
        try:
            # Оптимизированная подписка
            await pubsub.subscribe("sensor_updates")

            # Буферизация сообщений для уменьшения нагрузки
            message_buffer = []

            while True:
                try:
                    # Получаем сообщение с буферизацией
                    message = await pubsub.get_message(ignore_subscribe_messages=True)

                    if not message:
                        # Отправляем накопленные сообщения
                        if message_buffer:
                            await send_buffered_messages(websocket, message_buffer)
                            message_buffer.clear()
                        await asyncio.sleep(0.05)  # Увеличенная пауза
                        continue

                    if message["type"] == "message":
                        try:
                            # Накапливаем сообщения
                            message_buffer.append(message)

                            # Отправляем пакетно
                            if len(message_buffer) >= 10:
                                await send_buffered_messages(websocket, message_buffer)
                                message_buffer.clear()

                        except (json.JSONDecodeError, KeyError) as e:
                            logger.warning(f"Ошибка парсинга данных: {e}")

                except asyncio.CancelledError:
                    logger.info("Redis listener остановлен")
                    break

                except Exception as e:
                    logger.error(f"Критическая ошибка: {e}")
                    await asyncio.sleep(1.0)  # Переподключение

        finally:
            # Гарантированное освобождение ресурсов
            await pubsub.unsubscribe("sensor_updates")
            logger.info("Redis listener завершил работу")


async def send_buffered_messages(websocket: WebSocket, messages: list):
    try:
        if websocket not in active_connections:
            return

        for message in messages:
            try:
                data = json.loads(message["data"])
                device_id = data.get("device_id")

                if (
                    device_id
                    and device_id in active_connections[websocket]
                    and websocket.client_state != "disconnected"
                ):
                    try:
                        await websocket.send_text(json.dumps(data))
                    except WebSocketDisconnect:
                        if websocket in active_connections:
                            del active_connections[websocket]
                            return

            except (json.JSONDecodeError, KeyError):
                continue

    except WebSocketDisconnect:
        if websocket in active_connections:
            del active_connections[websocket]
