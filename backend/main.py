import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List, Optional

import redis.asyncio as redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from api.api_v1 import router
from collectors.data_collector import DataCollector
from collectors.mqtt_collector import MQTTCollector
from core.settings import settings
from crud.sensors import SensorDataCRUD
from db.database import init_db, async_session_context
from models import *  # noqa
from services.actuator_manager import ActuatorManager
from services.automations import load_all_automations
from services.mqtt_client import AsyncMQTTClient
from services.mqtt_helper import create_mqtt_client
from services.plugins import load_plugins
from utils.automations import AutomationEngine
from utils.dependencies import setup_plugin_dependencies, set_automation_engine

logging.basicConfig(level=settings.log.level)
logger = logging.getLogger(__name__)


plugins = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_plugin_dependencies()
    collect_tasks: List[asyncio.Task] = []
    redis_client: Optional[redis.Redis] = None
    mqtt_client: Optional[AsyncMQTTClient] = None
    actuator_manager: Optional[ActuatorManager] = None

    try:
        await init_db()
        logger.info("Database initialized")

        async with async_session_context() as db_session:
            await SensorDataCRUD.drop_state(db_session)
            loaded_plugins = await load_plugins(db_session)
            plugins.clear()
            plugins.update(loaded_plugins)
            actuator_manager = ActuatorManager()
            await actuator_manager.load_actuators(db_session)

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
            (
                asyncio.create_task(data_collector.collect())
                if settings.collector.plugins
                else None
            ),
            (
                asyncio.create_task(mqtt_collector.collect())
                if settings.collector.mqtt
                else None
            ),
        ]
        logger.info("DataCollector and MQTTCollector tasks created")

        automations = load_all_automations("./automations")
        automation_engine = AutomationEngine(
            redis_client=redis_client,
            actuator_manager=actuator_manager,
            automations=automations,
        )
        asyncio.create_task(automation_engine.run())
        set_automation_engine(automation_engine)

        logger.info("AutomationEngine started")

        yield

    except Exception as e:
        logger.error(f"Lifespan error: {e}", exc_info=True)
        raise

    finally:
        if automation_engine:
            automation_engine.running = False
            await automation_engine.cleanup()
        for task in collect_tasks:
            if task and not task.done():
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
                await redis_client.close()
                logger.info("Redis client closed")
            except Exception as e:
                logger.error(f"Error closing Redis client: {e}")
        if actuator_manager:
            for actuator in actuator_manager.actuators.values():
                try:
                    await actuator.cleanup()
                except Exception as e:
                    logger.error(f"Error cleaning up actuator {actuator.device_id}: {e}")
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
    openapi_schema["openapi"] = "3.0.0"
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
