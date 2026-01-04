import logging
import random
import time
from typing import Dict, Any

from .template import DevicePlugin

logger = logging.getLogger(__name__)


class DS18B20MuxPluginExample(DevicePlugin):
    """
    Плагин для имитации DS18B20, подключённого через CD74HC4067.
    Генерирует виртуальные температурные данные.
    """

    def __init__(
        self,
        device_id: str,
        num_sensors: int = 4,
        base_temp: float = 5.0,
        temp_variation: float = 20.0,
        poll_interval: float = 5.0,
    ):
        super().__init__(device_id, poll_interval)
        self.num_sensors = num_sensors
        self.base_temp = base_temp
        self.temp_variation = temp_variation
        self.sensor_states = {}

    async def init_hardware(self):
        logger.info(
            f"Инициализация виртуального мультиплексора для {self.num_sensors} датчиков"
        )
        for i in range(self.num_sensors):
            self.sensor_states[i] = {"online": True, "last_temp": self.base_temp}
        logger.info("Virtual hardware is ready")

    async def read_data(self) -> Dict[str, Any]:
        data = {"unit": "celsius"}

        for sensor_id in range(self.num_sensors):
            if self.sensor_states[sensor_id]["online"]:
                # Получаем текущее время для расчёта динамики
                now = time.time()

                # Если последнее обновление было недавно — используем плавное изменение
                if (now - self.sensor_states[sensor_id].get("last_update", 0)) < 60:
                    # Плавное колебание ±0.2°C от последнего значения
                    temp_change = random.uniform(-0.2, 0.2)
                    temp = self.sensor_states[sensor_id]["last_temp"] + temp_change
                else:
                    # Раз в 1–3 минуты имитируем небольшое изменение из-за внешних факторов
                    temp_change = random.uniform(-0.5, 1.0)
                    temp = self.base_temp + temp_change

                    # Имитируем влияние бытовых факторов (плита, солнце, проветривание)
                    if random.random() < 0.15:  # 15% вероятность локального влияния
                        temp += random.uniform(0.3, 1.5)
                    elif random.random() < 0.1:  # 10% вероятность охлаждения
                        temp -= random.uniform(0.2, 0.8)

                # Ограничиваем реалистичный диапазон для квартиры
                temp = max(18.0, min(30.0, temp))

                # Округляем до 1 знака после запятой
                temp = round(temp, 1)

                # Сохраняем значение и время обновления
                self.sensor_states[sensor_id]["last_temp"] = temp
                self.sensor_states[sensor_id]["last_update"] = now

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
                logger.info(f"Sensor {sensor} switched offline")
        elif action == "set_online":
            sensor = command.get("sensor")
            if sensor in self.sensor_states:
                self.sensor_states[sensor]["online"] = True
                logger.info(f"Sensor {sensor} has been transferred online")
        elif action == "set_base_temp":
            new_temp = command.get("temp")
            if isinstance(new_temp, (int, float)):
                self.base_temp = float(new_temp)
                logger.info(
                    f"The base temperature has been changed to {self.base_temp}°C"
                )
        else:
            logger.warning(f"Unknown command: {command}")
