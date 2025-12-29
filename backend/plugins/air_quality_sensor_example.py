import asyncio
import random
import time
from datetime import datetime

from plugins.template import DevicePlugin


class AirQualitySensorPlugin(DevicePlugin):
    """
    Плагин для датчика качества воздуха.
    Генерирует значение CO₂ (ppm) в диапазоне 400–2000.
    """

    def __init__(self, device_id: str, co2_base: float = 800.0):
        super().__init__(device_id=device_id)
        self.co2_base = co2_base
        self.last_update = time.time()

    async def init_hardware(self):
        """Имитация инициализации аппаратной части."""
        # Здесь можно добавить реальную инициализацию (I2C, GPIO и т.п.)
        await asyncio.sleep(0.1)  # Имитация задержки
        return True  # Успех

    async def read_data(self) -> dict:
        """Имитация чтения данных с датчика CO₂ с реалистичной динамикой."""

        now = time.time()

        # Обновляем значение раз в 30–120 секунд (реалистичный интервал)
        if now - self.last_update < random.uniform(30, 120):
            # Возвращаем текущее значение без изменений
            co2 = self.co2_base
        else:
            # Плавное изменение значения (имитация дыхания людей, проветривания и т.п.)
            change = random.uniform(-15, 40)  # медленные колебания

            # Имитация резких скачков (например, при входе человека в комнату)
            if random.random() < 0.1:  # 10% вероятность скачка
                change += random.uniform(50, 150)

            co2 = self.co2_base + change
            # Ограничиваем реалистичный диапазон
            co2 = max(400, min(2500, int(co2)))
            self.co2_base = co2
            self.last_update = now

        # Определяем статус на основе текущих норм
        if co2 < 800:
            status = "normal"  # Комфортный уровень
        elif co2 < 1200:
            status = "elevated"  # Повышенный, рекомендуется проветривание
        else:
            status = "high"  # Высокий, требуется вентиляция

        return {
            "co2": round(co2, 1),
            "unit": "ppm",
            "status": status,
            "timestamp": datetime.now().isoformat(),
        }

    async def handle_command(self, command: dict) -> dict:
        """Обработка команд (если нужны)."""
        return {"status": "unsupported", "command": command}

    # async def start(self):
    #     """Асинхронный генератор данных."""
    #     while True:
    #         data = await self.read_data()
    #         message = SensorMessage(
    #             device_id=self.device_id, timestamp=datetime.now().isoformat(), data=data
    #         )
    #         yield message
    #         await asyncio.sleep(10)  # Каждые 10 секунд
