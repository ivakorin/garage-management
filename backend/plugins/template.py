import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, AsyncGenerator

from crud.plugins import Plugins
from schemas.sensor import SensorMessage

logger = logging.getLogger(__name__)


class DevicePlugin(ABC):
    """
    Базовый класс для плагинов устройств.
    Отвечает ТОЛЬКО за:
    - инициализацию устройства;
    - чтение данных с устройства;
    - обработку команд.

    Не занимается:
    - сохранением в БД;
    - публикацией в MQTT/Redis;
    - обработкой ошибок сохранения.
    """

    def __init__(self, device_id: str, poll_interval: float = 1.0):
        self.device_id = device_id
        self.poll_interval = max(poll_interval, 0.1)

    @abstractmethod
    async def init_hardware(self) -> None:
        """Инициализация аппаратной части."""
        pass

    @abstractmethod
    async def read_data(self) -> Dict[str, Any]:
        """
        Считывание данных с устройства.
        Возвращает словарь с данными (без метаинформации).
        """
        pass

    @abstractmethod
    async def handle_command(self, command: Dict[str, Any]) -> None:
        """Обработка команды от сервера."""
        pass

    async def start(self) -> AsyncGenerator[SensorMessage, Any]:
        """Запуск плагина — возвращает асинхронный генератор данных."""
        await self.init_hardware()
        logger.info(f"Плагин {self.device_id} запущен")
        while await Plugins.is_running(self.device_id):
            try:
                data = await self.read_data()
                if data:
                    result = SensorMessage(
                        device_id=self.device_id,
                        timestamp=datetime.now().isoformat(),
                        data=data,
                    )
                    # Возвращаем данные с метаинформацией
                    yield result
            except Exception as e:
                logger.error(f"Ошибка в цикле плагина {self.device_id}: {e}")

            await asyncio.sleep(self.poll_interval)

    async def stop(self) -> None:
        """Остановка плагина."""
        self.is_running = False
        logger.info(f"Плагин {self.device_id} остановлен")
