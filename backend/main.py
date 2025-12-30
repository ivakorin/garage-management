import asyncio
import logging
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from api.api_v1 import router
from core.settings import settings
from db.database import init_db, async_session_context
from models import *  # noqa
from services.plugins import load_plugins
from services.ws_manager import ws_manager
from tasks.data_collector import DataCollector
from utils.automations import automations_loader

logging.basicConfig(level=settings.log.level)
logger = logging.getLogger(__name__)


plugins = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    collect_task = None
    redis_client = None
    try:
        await init_db()
        logger.info("Database initialized")
        # await ws_manager.startup()
        async with async_session_context() as db_session:
            loaded_plugins = await load_plugins(db_session)
            plugins.clear()
            plugins.update(loaded_plugins)
            active_db_session = db_session
        plugins_list = list(plugins.values())
        redis_client = redis.Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            db=settings.redis.db,
        )
        data_collector = DataCollector(
            plugins=plugins_list, db_session=active_db_session, redis_client=redis_client
        )
        collect_task = asyncio.create_task(data_collector.collect())
        logger.info("DataCollector task created")
        await automations_loader("./automations")
        yield

    except Exception as e:
        logger.error(f"Lifespan error: {e}", exc_info=True)
    finally:
        if collect_task:
            collect_task.cancel()
            try:
                await collect_task
            except asyncio.CancelledError:
                pass
        if redis_client:
            await redis_client.close()
        if ws_manager:
            await ws_manager.shutdown()
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
    "https://your-domain.com",
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
