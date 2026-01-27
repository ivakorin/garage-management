import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List, Optional

import redis.asyncio as redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
# Импорт профилировщика
from pyinstrument import Profiler

from api.api_v1 import router
from collectors.data_collector import DataCollector
from collectors.mqtt_collector import MQTTCollector
from core.settings import settings
from crud.sensors import SensorDataCRUD
from db.database import init_db, async_session_context
from models import *  # noqa
from services.mqtt_client import AsyncMQTTClient
from services.mqtt_helper import create_mqtt_client
from services.plugins import load_plugins
from utils.automations import automations_loader

logging.basicConfig(level=settings.log.level)
logger = logging.getLogger(__name__)

plugins = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    collect_tasks: List[asyncio.Task] = []
    redis_client: Optional[redis.Redis] = None
    mqtt_client: Optional[AsyncMQTTClient] = None

    try:
        await init_db()
        logger.info("Database initialized")
        async with async_session_context() as db_session:
            await SensorDataCRUD.drop_state(db_session)
            loaded_plugins = await load_plugins(db_session)
            plugins.clear()
            plugins.update(loaded_plugins)

        plugins_list = list(plugins.values())
        redis_client = redis.Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            db=settings.redis.db,
        )
        mqtt_client = create_mqtt_client()
        data_collector = DataCollector(
            plugins=plugins_list,
            redis_client=redis_client,
            mqtt_client=mqtt_client,
        )
        mqtt_collector = MQTTCollector(
            mqtt_client=mqtt_client,
            redis_client=redis_client,
            subscription_topics=["devices/#"],
        )
        collect_tasks = [
            asyncio.create_task(data_collector.collect()),
            asyncio.create_task(mqtt_collector.collect()),
        ]
        logger.info("DataCollector and MQTTCollector tasks created")
        await automations_loader("./automations")

        yield

    except Exception as e:
        logger.error(f"Lifespan error: {e}", exc_info=True)
        raise

    finally:
        for task in collect_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        if mqtt_client:
            try:
                await mqtt_client.disconnect()
                logger.info("MQTT client disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting MQTT client: {e}")
        if redis_client:
            try:
                await redis_client.aclose()
                logger.info("Redis client closed")
            except Exception as e:
                logger.error(f"Error closing Redis client: {e}")
        logger.info("Application shutdown complete")


app = FastAPI(
    title="Garage Management",
    description="API с WebSocket‑подключением",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)

origins = [
    "http://localhost",
    "http://localhost:8000",
]

allow_all_origins = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if not allow_all_origins else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=[
        "*",
        "Upgrade",
        "Connection",
        "Sec-WebSocket-Key",
        "Sec-WebSocket-Version",
        "Sec-WebSocket-Protocol",
    ],
    expose_headers=[],
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    # Добавляем описание WebSocket
    openapi_schema["paths"]["/api/v1/ws"] = {
        "get": {
            "summary": "WebSocket Endpoint",
            "description": (
                "Двунаправленный канал через WebSocket.\n\n"
                "**Методы:**\n"
                "- Клиент → Сервер: отправка текстовых сообщений\n"
                "- Сервер → Клиент: трансляция событий\n\n"
                "**URL:** `ws://{host}/api/v1/ws`\n"
                "**Пример подключения:**\n"
                "```javascript\n"
                "const ws = new WebSocket('ws://localhost:8000/api/v1/ws');\n"
                "ws.onmessage = (e) => console.log(e.data);\n"
                "```"
            ),
            "operationId": "websocket_endpoint",
            "parameters": [],
            "responses": {
                "101": {"description": "Переключение на WebSocket"},
                "400": {"description": "Ошибка подключения"},
            },
            "tags": ["WebSocket"],
        }
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

app.include_router(router=router)


# === ПРОФИЛИРОВАНИЕ ===
if __name__ == "__main__":
    profiler = Profiler()
    profiler.start()

    try:
        import uvicorn

        # Запускаем Uvicorn внутри профилировщика
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except KeyboardInterrupt:
        pass
    finally:
        profiler.stop()
        # Выводим отчёт в консоль
        # print(profiler.output_text(show_all=True))
        # Или сохраняем в файл
        with open("profile_report.html", "w") as f:
            f.write(profiler.output_html())
