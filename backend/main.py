import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from core.settings import settings
from db.database import init_db, async_session_context  # Добавляем async_session_context
from models import *  # noqa
from services.mqtt_client import AsyncMQTTClient
from services.plugins import load_plugins

logging.basicConfig(level=settings.log.level)
logger = logging.getLogger(__name__)

app = FastAPI()
mqtt_client = AsyncMQTTClient(
    broker=settings.mqtt.host,
    port=settings.mqtt.port,
    username=settings.mqtt.username,
    password=settings.mqtt.password
)
plugins = {}  # Глобальный словарь для хранения плагинов



async def handle_command(command: dict):
    device_id = command.get("device_id")
    if device_id in plugins:
        try:
            await plugins[device_id].handle_command(command)
            logger.info(f"Command executed for {device_id}: {command}")
        except Exception as e:
            logger.error(f"Error executing command for {device_id}: {e}")
    else:
        logger.warning(f"Plugin not found for device_id: {device_id}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
        logger.info("Database initialized")

        await mqtt_client.connect()
        await asyncio.sleep(5)
        if not mqtt_client._is_connected:
            raise ConnectionError("MQTT client failed to connect")
        logger.info("MQTT client connected")


        mqtt_client.subscribe("commands/+/action", handle_command)
        logger.info("MQTT subscriptions set up")

        # Получаем сессию для всех плагинов
        async with async_session_context() as db_session:  # ← Создаём единую сессию
            loaded_plugins = await load_plugins(db_session, mqtt_client)  # ← Передаём её в загрузку плагинов
            plugins.update(loaded_plugins)
            logger.info(f"Loaded {len(loaded_plugins)} plugins")

            logger.info("FastAPI app ready to serve requests")
            yield  # ← Здесь стартует HTTP-сервер

            # Блок finally выполняется после остановки сервера

    except Exception as e:
        logger.error(f"Lifespan startup error: {e}")
        raise

    finally:
        logger.info("FastAPI app shutting down")

        try:
            await mqtt_client.unsubscribe("commands/+/action")
        except Exception as e:
            logger.warning(f"Failed to unsubscribe: {e}")

        try:
            await asyncio.wait_for(mqtt_client.disconnect(), timeout=10.0)
        except asyncio.TimeoutError:
            logger.error("MQTT disconnect timed out")
        except Exception as e:
            logger.error(f"MQTT disconnect error: {e}")

        for plugin_id, plugin in plugins.items():
            try:
                await asyncio.wait_for(plugin.stop(), timeout=10.0)
                logger.info(f"Plugin {plugin_id} stopped")
            except asyncio.TimeoutError:
                logger.error(f"Plugin {plugin_id} did not stop in time")
            except Exception as e:
                logger.error(f"Error stopping plugin {plugin_id}: {e}")

        logger.info("Cleanup completed")

app = FastAPI(lifespan=lifespan)

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
