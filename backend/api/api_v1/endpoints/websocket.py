import asyncio
import json
import logging
from typing import Dict, Set, Optional

import redis.asyncio as redis
from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from core.settings import settings

router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)

# Redis-клиент с явным пулом соединений
redis_client = redis.Redis(
    host=settings.redis.host,
    port=settings.redis.port,
    db=settings.redis.db,
    decode_responses=False,  # работаем с байтами → быстрее
)

# Храним подключения и их подписки
active_connections: Dict[WebSocket, Set[str]] = {}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections[websocket] = set()
    listener_task: Optional[asyncio.Task] = None

    try:
        # Запускаем слушателя Redis только после успешного accept
        listener_task = asyncio.create_task(redis_listener(websocket))

        while True:
            try:
                # Таймаут на приём сообщения (защита от зависаний)
                message = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                logger.debug(
                    f"Received: {message[:100]}..."
                )  # обрезаем длинные сообщения

                try:
                    data = json.loads(message)
                    action = data.get(b"action".decode())  # json возвращает байты
                    sensor_id = data.get(b"sensor_id".decode())

                    if action == "subscribe":
                        if sensor_id:
                            active_connections[websocket].add(sensor_id)
                            await websocket.send_text(
                                json.dumps(
                                    {"status": "subscribed", "sensor_id": sensor_id}
                                )
                            )
                            logger.info(f"Subscribed: {sensor_id}")
                        else:
                            await websocket.send_text(
                                json.dumps({"error": "sensor_id required"})
                            )

                    elif action == "unsubscribe":
                        if sensor_id in active_connections[websocket]:
                            active_connections[websocket].remove(sensor_id)
                            await websocket.send_text(
                                json.dumps(
                                    {"status": "unsubscribed", "sensor_id": sensor_id}
                                )
                            )
                        else:
                            await websocket.send_text(
                                json.dumps({"error": f"Not subscribed to {sensor_id}"})
                            )

                    elif action == "get_subscriptions":
                        subscriptions = list(active_connections[websocket])
                        await websocket.send_text(
                            json.dumps({"subscriptions": subscriptions})
                        )

                    else:
                        await websocket.send_text(
                            json.dumps({"error": f"Unknown action: {action}"})
                        )

                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Invalid JSON or missing key: {e}")
                    await websocket.send_text(
                        json.dumps({"error": "Invalid message format"})
                    )

            except asyncio.TimeoutError:
                # Проверяем, жив ли клиент (ping)
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break  # клиент не ответил — разрываем
                continue

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Client error: {type(e).__name__}: {e}", exc_info=True)
                break

    except Exception as e:
        logger.error(f"WebSocket outer error: {e}", exc_info=True)
    finally:
        # Гарантированная очистка
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
        except Exception:
            pass  # уже закрыто


async def redis_listener(websocket: WebSocket):
    """Слушатель Redis для трансляции сообщений подписчику."""
    pubsub = redis_client.pubsub()

    try:
        await pubsub.subscribe("sensor_updates")
        logger.info("Redis subscriber started")

        while True:
            try:
                # Получаем сообщение с таймаутом
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True), timeout=5.0
                )

                if message and message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        device_id = data.get(b"device_id".decode())

                        # Проверяем подписку и состояние соединения
                        if (
                            device_id
                            and device_id in active_connections.get(websocket, set())
                            and websocket.client_state != "disconnected"
                        ):
                            await websocket.send_text(json.dumps(data))

                    except json.JSONDecodeError as e:
                        logger.warning(f"Redis JSON error: {e}")

                # Небольшой сон для снижения нагрузки
                await asyncio.sleep(0.1)

            except asyncio.TimeoutError:
                # Периодическая проверка соединения
                if websocket.client_state == "disconnected":
                    break
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Redis listener error: {e}", exc_info=True)
                await asyncio.sleep(1.0)  # пауза при ошибке

    finally:
        try:
            await pubsub.unsubscribe("sensor_updates")
            await pubsub.close()
        except Exception:
            pass
        logger.info("Redis subscriber stopped")
