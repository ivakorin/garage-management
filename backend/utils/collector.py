import asyncio
import logging
from typing import Optional

import redis.asyncio as redis

from core.settings import settings
from db.database import async_session_context
from services.plugins import load_plugins
from tasks.data_collector import DataCollector

logger = logging.getLogger(__name__)

# Глобальные переменные для коллектора
collect_task: Optional[asyncio.Task] = None
redis_client: Optional[redis.Redis] = None
data_collector: Optional[DataCollector] = None
plugins = {}


async def restart_collector():
    """
    Перезапускает DataCollector с актуальными плагинами.
    Может вызываться из API или по таймеру.
    """
    global collect_task, redis_client, data_collector

    # 1. Останавливаем старый коллектор
    if collect_task:
        collect_task.cancel()
        try:
            await collect_task
        except asyncio.CancelledError:
            pass

    # 2. Перезагружаем плагины
    async with async_session_context() as db_session:
        loaded_plugins = await load_plugins(db_session)
        plugins.clear()
        plugins.update(loaded_plugins)
        active_db_session = db_session

    plugins_list = list(plugins.values())

    # 3. Пересоздаём Redis‑клиент (если нужно)
    if redis_client is None:
        redis_client = redis.Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            db=settings.redis.db,
        )

    # 4. Создаём новый коллектор
    data_collector = DataCollector(
        plugins=plugins_list, db_session=active_db_session, redis_client=redis_client
    )
    collect_task = asyncio.create_task(data_collector.collect())
    logger.info("DataCollector перезапущен с новыми плагинами")
