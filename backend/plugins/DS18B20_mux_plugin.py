import logging
import random
from typing import Dict, Any

from .template import DevicePlugin

logger = logging.getLogger(__name__)



class DS18B20MuxPlugin(DevicePlugin):
    """
    Плагин для имитации DS18B20, подключённого через CD74HC4067.
    Генерирует виртуальные температурные данные.
    """

    def __init__(
        self,
        device_id: str,
        mqtt_client,
        db_session,
        num_sensors: int = 4,
        base_temp: float = 25.0,
        temp_variation: float = 2.0,
        poll_interval: float = 5.0
    ):
        super().__init__(device_id, mqtt_client, db_session, poll_interval)
        self.num_sensors = num_sensors
        self.base_temp = base_temp
        self.temp_variation = temp_variation
        self.sensor_states = {}

    async def init_hardware(self):
        logger.info(f"Инициализация виртуального мультиплексора для {self.num_sensors} датчиков")
        for i in range(self.num_sensors):
            self.sensor_states[i] = {"online": True, "last_temp": self.base_temp}
        logger.info("Виртуальное железо готово")

    async def read_data(self) -> Dict[str, Any]:
        data = {}
        for sensor_id in range(self.num_sensors):
            if self.sensor_states[sensor_id]["online"]:
                temp = self.base_temp + random.uniform(-self.temp_variation, self.temp_variation)
                temp = round(temp, 1)
                self.sensor_states[sensor_id]["last_temp"] = temp
                data[f"sensor_{sensor_id}"] = temp
            else:
                data[f"sensor_{sensor_id}"] = None
        return data

    async def handle_command(self, command: dict):
        action = command.get("action")
        if action == "set_offline":
            sensor = command.get("sensor")
            if sensor in self.sensor_states:
                self.sensor_states[sensor]["online"] = False
                logger.info(f"Датчик {sensor} переведён в offline")
        elif action == "set_online":
            sensor = command.get("sensor")
            if sensor in self.sensor_states:
                self.sensor_states[sensor]["online"] = True
                logger.info(f"Датчик {sensor} переведён в online")
        elif action == "set_base_temp":
            new_temp = command.get("temp")
            if isinstance(new_temp, (int, float)):
                self.base_temp = float(new_temp)
                logger.info(f"Базовая температура изменена на {self.base_temp}°C")
        else:
            logger.warning(f"Неизвестная команда: {command}")

    # _save_to_db() и start() наследуются от DevicePlugin — нет нужды переопределять!
