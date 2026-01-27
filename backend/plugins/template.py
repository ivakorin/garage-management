import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, AsyncGenerator

from crud.plugins import Plugins
from mock.gpio_adapter import GPIO, is_rpi
from schemas.sensors import SensorMessage

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
        """Do not use this method directly from plugins.
        Method will be automatically called from data collector when the plugin is loaded.
        """
        await self.init_hardware()
        logger.info(f"The {self.device_id} plugin is running")
        while await Plugins.is_running(self.device_id):
            try:
                data = await self.read_data()
                if data:
                    result = SensorMessage(
                        device_id=self.device_id,
                        timestamp=datetime.now().isoformat(),
                        data=data,
                        unit=data["unit"],
                        online=data.get("online"),
                    )
                    if data.get("value"):
                        result.value = data["value"]
                    yield result
            except Exception as e:
                logger.error(f"Error in the plugin loop {self.device_id}: {e}")

            await asyncio.sleep(self.poll_interval)

    async def stop(self) -> None:
        """Do not use this method directly from plugins."""
        self.is_running = False
        logger.info(f"The {self.device_id} plugin has been stopped")


class ActuatorPlugin(ABC):
    def __init__(self, device_id: str, pin: int, inverted: bool = False):
        self.device_id = device_id
        self.pin = pin
        self.inverted = inverted
        self._initialized = False

    async def init_hardware(self):
        if self._initialized:
            return  # Уже настроено

        if not is_rpi():
            logger.info(f"[{self.device_id}] GPIO not available (dev mode)")
            self._initialized = True
            return

        try:
            GPIO.setmode(GPIO.BCM)
            if GPIO.gpio_function(self.pin) != GPIO.OUT:
                GPIO.setup(self.pin, GPIO.OUT)
            self._initialized = True
            logger.info(f"[{self.device_id}] GPIO initialized on pin {self.pin}")
        except Exception as e:
            logger.error(f"[{self.device_id}] Failed to setup GPIO: {e}")
            raise

    @abstractmethod
    async def handle_command(self, command: dict) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_state(self) -> dict:
        raise NotImplementedError

    async def cleanup(self):
        if not self._initialized:
            return
        if is_rpi():
            try:
                GPIO.cleanup(self.pin)
                logger.info(f"[{self.device_id}] GPIO cleaned up")
            except Exception as e:
                logger.error(f"[{self.device_id}] Error in cleanup: {e}")
        self._initialized = False
