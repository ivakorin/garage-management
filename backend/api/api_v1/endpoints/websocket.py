import json
import logging

from fastapi import APIRouter, WebSocket

from services.ws_manager import ws_manager

router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    try:
        # Принимаем подключение
        await ws_manager.connect(websocket)
        logger.info("Клиент подключился")

        while True:
            # Получаем текстовое сообщение от клиента
            data = await websocket.receive_text()
            logger.info(f"Получено от клиента: {data}")

            # Пример ответа клиенту (опционально)
            await websocket.send_text(json.dumps({"data": f"Сервер получил: {data}"}))

    except Exception as e:
        logger.warning(f"Клиент отключился: {e}")
    finally:
        # Гарантированно отключаем клиента
        ws_manager.disconnect(websocket)
        logger.info("Соединение закрыто")
