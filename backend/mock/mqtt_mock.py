import asyncio
import json
import random

from aiomqtt import Client

from backend.core.settings import settings


async def mock_device(device_id: str):
    async with Client(settings.mqtt.host) as client:
        while True:
            # Имитируем данные датчиков температуры
            payload = {
                "device_id": device_id,
                "sensor": "DS18B20",
                "value": round(random.uniform(20.0, 30.0), 2),
                "timestamp": asyncio.get_event_loop().time(),
            }
            await client.publish(f"sensors/{device_id}/temperature", json.dumps(payload))
            await asyncio.sleep(5)  # Каждые 5 секунд


# Запуск трёх эмулированных датчиков
async def main():
    await asyncio.gather(
        mock_device("sensor_01"), mock_device("sensor_02"), mock_device("sensor_03")
    )


if __name__ == "__main__":
    asyncio.run(main())
