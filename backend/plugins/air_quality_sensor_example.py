import asyncio
import random

from plugins.template import DevicePlugin


class AirQualitySensorPlugin(DevicePlugin):
    """
    Плагин для датчика качества воздуха.
    Генерирует значение CO₂ (ppm) в диапазоне 400–2000.
    """

    def __init__(self, device_id: str, co2_base: float = 800.0):
        super().__init__(device_id=device_id)
        self.co2_base = co2_base

    async def init_hardware(self):
        """Имитация инициализации аппаратной части."""
        # Здесь можно добавить реальную инициализацию (I2C, GPIO и т.п.)
        await asyncio.sleep(0.1)  # Имитация задержки
        return True  # Успех

    async def read_data(self) -> dict:
        """Имитация чтения данных с датчика."""
        co2 = self.co2_base + random.uniform(-50, 150)
        co2 = max(400, min(2000, co2))
        return {
            "co2": round(co2, 1),
            "unit": "ppm",
            "status": "normal" if co2 < 1000 else "elevated",
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
