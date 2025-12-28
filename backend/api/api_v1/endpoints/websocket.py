import asyncio
import json
import logging
from typing import Dict, Set

import redis.asyncio as redis
from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from core.settings import settings

router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)

redis_client = redis.Redis(
    host=settings.redis.host,
    port=settings.redis.port,
    db=settings.redis.db,
    decode_responses=True,
)

active_connections: Dict[WebSocket, Set[str]] = {}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections[websocket] = set()

    # Flag to track connection state
    is_closed = False

    try:
        # Background Redis listener task
        listener_task = asyncio.create_task(redis_listener(websocket, is_closed))

        while not is_closed:
            try:
                message = await websocket.receive_text()
                logger.info(f"Received message: {message}")
                data = json.loads(message)
                action = data.get("action")
                sensor_id = data.get("sensor_id")

                if action == "subscribe":
                    if sensor_id:
                        active_connections[websocket].add(sensor_id)
                        await websocket.send_text(
                            json.dumps({"status": "subscribed", "sensor_id": sensor_id})
                        )
                        logger.info(f"Client subscribed to {sensor_id}")
                    else:
                        await websocket.send_text(
                            json.dumps({"error": "sensor_id required for subscribe"})
                        )

                elif action == "unsubscribe":
                    if sensor_id in active_connections[websocket]:
                        active_connections[websocket].remove(sensor_id)
                        await websocket.send_text(
                            json.dumps({"status": "unsubscribed", "sensor_id": sensor_id})
                        )
                        print(f"Client unsubscribed from {sensor_id}")
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

            except WebSocketDisconnect:
                # Client disconnected
                is_closed = True
                break
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                is_closed = True
                break

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Ensure connection is closed only once
        if not is_closed:
            await websocket.close()
        # Clean up resources
        if websocket in active_connections:
            del active_connections[websocket]
        # Cancel background task
        listener_task.cancel()
        try:
            await listener_task
        except asyncio.CancelledError:
            pass


async def redis_listener(websocket: WebSocket, is_closed: bool):
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("sensor_updates")

    try:
        while not is_closed:
            message = await pubsub.get_message(ignore_subscribe_messages=True)
            if message and message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    device_id = data.get("device_id")

                    if device_id and device_id in active_connections.get(
                        websocket, set()
                    ):
                        # Check if connection is still alive
                        if websocket.client_state != "disconnected":
                            await websocket.send_text(json.dumps(data))
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse Redis message: {e}")

            await asyncio.sleep(0.05)

    except asyncio.CancelledError:
        # Task cancelled - normal operation
        pass
    except Exception as e:
        logger.error(f"Redis listener error: {e}")
    finally:
        await pubsub.close()
