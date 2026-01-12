import asyncio
import random

from plugins.template import DevicePlugin


class LeakSensorPlugin(DevicePlugin):
    """
    Плагин для датчика протечки.
    Генерирует бинарное значение: True — протечка, False — нет.
    """

    def __init__(self, device_id: str, leak_probability: float = 0.05):
        super().__init__(device_id=device_id)
        self.leak_probability = leak_probability

    async def init_hardware(self):
        """Имитация инициализации аппаратной части."""
        await asyncio.sleep(0.1)
        return True

    async def read_data(self) -> dict:
        """Имитация чтения состояния датчика."""
        result = {
            "leak": None,
            "alert": None,
            "unit": "boolean",
            "message": None,
            "online": False,
        }
        leak = random.random() < self.leak_probability
        if leak:
            data = 1
        else:
            data = 0
        result["leak"] = data
        result["alert"] = leak
        result["message"] = "Протечка!" if leak else "Всё сухо"
        result["online"] = True
        return result

    async def handle_command(self, command: dict) -> dict:
        """Обработка команд."""
        return {"status": "unsupported", "command": command}
