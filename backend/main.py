import asyncio
import logging
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocket

from core.settings import settings
from db.database import init_db, async_session_context  # Добавляем async_session_context
from models import *  # noqa
from services.plugins import load_plugins
from services.ws_manager import ws_manager
from tasks.data_collector import DataCollector

logging.basicConfig(level=settings.log.level)
logger = logging.getLogger(__name__)

app = FastAPI()

plugins = {}  # Глобальный словарь для хранения плагинов

@asynccontextmanager
async def lifespan(app: FastAPI):
    collect_task = None
    redis_client = None
    try:
        await init_db()
        logger.info("Database initialized")
        await ws_manager.startup()
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
            plugins=plugins_list,
            db_session=active_db_session,
            redis_client=redis_client
        )
        collect_task = asyncio.create_task(data_collector.collect())
        logger.info("DataCollector task created")
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





app.router.lifespan = lifespan

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Явно разрешаем WebSocket
    allow_origin_regex=".*",  # Если нужны сложные шаблоны
)

@app.get("/plugins")
def list_plugins():
    return {"plugins": list(plugins.keys())}

@app.get("/plugins/{device_id}/status")
def get_plugin_status(device_id: str):
    if device_id not in plugins:
        raise HTTPException(status_code=404, detail="Plugin not found")
    status = plugins[device_id].get_status()
    return {"device_id": device_id, "status": status}

@app.post("/plugins/{device_id}/command")
async def send_command(device_id: str, command: dict):
    if device_id not in plugins:
        raise HTTPException(status_code=404, detail="Plugin not found")
    try:
        await plugins[device_id].handle_command(command)
        return {"status": "command sent", "device_id": device_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Можно принимать команды от клиента (если нужно)
            data = await websocket.receive_text()
            logger.debug(f"Получено от клиента: {data}")
    except Exception as e:
        logger.warning(f"Клиент отключился: {e}")
    finally:
        ws_manager.disconnect(websocket)