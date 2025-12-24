import asyncio
import json
import logging
from abc import abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import DeviceData  # Импорт модели
from models.sensor import Device

logger = logging.getLogger(__name__)



class DevicePlugin:
    """
    Абстрактный базовый класс для всех плагинов устройств.
    Обеспечивает:
    - базовую структуру плагина
    - автоматическое сохранение в БД (если не переопределено)
    """

    def __init__(self, device_id: str, mqtt_client, db_session: AsyncSession, poll_interval: float = 1.0):
        self.device_id = device_id
        self.mqtt_client = mqtt_client
        self.db_session = db_session
        self.is_running = False
        self.poll_interval = max(poll_interval, 0.1)

    @abstractmethod
    async def init_hardware(self):
        """Инициализация аппаратной части."""
        pass

    @abstractmethod
    async def read_data(self) -> Dict[str, Any]:
        """Считывание данных с устройства. Возвращает dict."""
        pass

    @abstractmethod
    async def handle_command(self, command: dict):
        """Обработка команды от сервера."""
        pass

    async def _save_to_db(self, data: Dict[str, Any]):
        try:
            # Проверяем, существует ли устройство в БД
            result = await self.db_session.execute(
                select(Device).where(Device.device_id == self.device_id)
            )
            device = result.scalars().first()

            if not device:
                # Автоматически создаём устройство с именем = device_id
                logger.info(f"Устройство {self.device_id} не найдено. Создаём новую запись в БД.")
                new_device = Device(
                    device_id=self.device_id,
                    name=self.device_id,  # Используем device_id как начальное имя
                    description=None,
                )
                self.db_session.add(new_device)
                await self.db_session.flush()
                logger.debug(f"Создано новое устройство: {self.device_id}")

            # Получаем последние сохранённые данные для этого устройства
            last_result = await self.db_session.execute(
                select(DeviceData)
                .where(DeviceData.device_id == self.device_id)
                .order_by(DeviceData.timestamp.desc())
                .limit(1)
            )
            last_record = last_result.scalars().first()

            # Сравниваем новые данные с последними сохранёнными
            if last_record:
                try:
                    last_data = json.loads(last_record.data)
                    # Сравниваем по значениям (игнорируем порядок ключей)
                    if self._data_equal(data, last_data):
                        logger.debug(f"Данные не изменились для {self.device_id}. Пропуск сохранения.")
                        return  # Данные не изменились — не сохраняем
                except json.JSONDecodeError:
                    logger.warning(f"Не удалось декодировать предыдущие данные для {self.device_id}")

            # Сохраняем новые данные (они отличаются или это первая запись)
            db_data = DeviceData(
                device_id=self.device_id,
                timestamp=datetime.now(),
                data=json.dumps(data),
                value=self._extract_numeric_value(data)
            )
            self.db_session.add(db_data)

            await self.db_session.commit()
            logger.debug(f"Сохранено в БД: устройство {self.device_id}, данные: {data}")

        except Exception as e:
            logger.error(f"Ошибка сохранения в БД для {self.device_id}: {e}")
            await self.db_session.rollback()

    def _data_equal(self, new_data: Dict[str, Any], old_data: Dict[str, Any]) -> bool:
        """
        Сравнивает два словаря данных.
        Возвращает True, если они эквивалентны (с учётом типов и значений).
        """
        if set(new_data.keys()) != set(old_data.keys()):
            return False

        for key in new_data:
            new_val = new_data[key]
            old_val = old_data[key]

            # Обрабатываем None
            if new_val is None and old_val is None:
                continue
            if new_val is None or old_val is None:
                return False

            # Для чисел проверяем приблизительное равенство (из‑за float)
            if isinstance(new_val, (int, float)) and isinstance(old_val, (int, float)):
                if abs(new_val - old_val) > 1e-9:
                    return False
            else:
                if new_val != old_val:
                    return False

        return True


    def _extract_numeric_value(self, data: Dict[str, Any]) -> Optional[float]:
        """
        Извлекает числовое значение из данных (для поля `value` в БД).
        По умолчанию: среднее арифметическое всех числовых значений в dict.
        Переопределите, если нужен другой алгоритм.
        """
        numeric_values = [
            v for v in data.values()
            if isinstance(v, (int, float)) and v is not None
        ]
        return sum(numeric_values) / len(numeric_values) if numeric_values else None

    async def start(self):
        """Запуск плагина."""
        await self.init_hardware()
        self.is_running = True
        logger.info(f"Плагин {self.device_id} запущен")

        while self.is_running:
            try:
                data = await self.read_data()
                if data:
                    # 1. Публикуем в MQTT
                    topic = f"devices/{self.device_id}/data"
                    payload = json.dumps(data)
                    await self.mqtt_client.publish(topic, payload)
                    logger.debug(f"Отправлено в MQTT: {topic} → {payload}")

                    # 2. Сохраняем в БД (автоматически, если не переопределено)
                    await self._save_to_db(data)

            except Exception as e:
                logger.error(f"Ошибка в цикле плагина {self.device_id}: {e}")

            await asyncio.sleep(self.poll_interval)  # Интервал опроса


    async def stop(self):
        """Остановка плагина."""
        self.is_running = False
        logger.info(f"Плагин {self.device_id} остановлен")
