import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Set

from sqlalchemy import select, and_, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.settings import settings
from crud.sensors import SensorDataCRUD
from models import Sensor, SensorData
from schemas.sensors import SensorMessage, SensorUpdateSchema

logger = logging.getLogger(__name__)


async def save_batch_to_db(
    db_session: AsyncSession,
    messages: List[SensorMessage],
    retention_days: int = settings.app_settings.keep_data,
) -> int:
    if not messages:
        return 0

    try:
        device_ids = {msg.device_id for msg in messages}

        # Оптимизированная загрузка сенсоров
        sensor_result = await db_session.execute(
            select(Sensor.device_id, Sensor.name)
            .where(Sensor.device_id.in_(device_ids))
            .distinct()
        )

        # Создаем словарь, где ключом будет device_id, а значением - объект Sensor
        sensor_map = {
            row.device_id: Sensor(device_id=row.device_id, name=row.name)
            for row in sensor_result.scalars()
        }

        # Оптимизированный запрос для получения последних данных
        subq = (
            select(SensorData.device_id)
            .where(SensorData.device_id.in_(device_ids))
            .group_by(SensorData.device_id)
            .having(SensorData.timestamp == func.max(SensorData.timestamp))
        ).subquery()

        last_data_result = await db_session.execute(
            select(SensorData)
            .join(subq, SensorData.device_id == subq.c.device_id)
            .where(SensorData.device_id.in_(device_ids))
        )
        last_data_map = {item.device_id: item for item in last_data_result.scalars()}

        to_insert: List[SensorData] = []
        to_update_online: List[SensorUpdateSchema] = []
        to_cleanup_devices: Set[str] = set()

        for msg in messages:
            # Проверка существования сенсора
            if msg.device_id not in sensor_map:
                logger.debug(
                    f"[BATCH SAVER]No sensor {msg.device_id} in database, try to save"
                )
                device = Sensor(device_id=msg.device_id, name=msg.device_id)
                db_session.add(device)
                sensor_map[msg.device_id] = device
            else:
                logger.debug(
                    f"[BATCH SAVER]Sensor {msg.device_id} found in database, update data"
                )
                to_update_online.append(
                    SensorUpdateSchema(
                        device_id=msg.device_id,
                        online=msg.online,
                        updated_at=datetime.now(),
                    )
                )

            # Проверка изменений данных
            last_data = last_data_map.get(msg.device_id)
            if _is_data_changed(last_data, msg.data):
                to_cleanup_devices.add(msg.device_id)

                db_data = SensorData(
                    device_id=msg.device_id,
                    timestamp=datetime.fromisoformat(msg.timestamp),
                    data=json.dumps(msg.data),
                    value=msg.value,
                    unit=msg.unit,
                )
                to_insert.append(db_data)

        # Массовая вставка данных
        if to_insert:
            db_session.add_all(to_insert)

        # Обновление статуса онлайн
        if to_update_online:
            for update in to_update_online:
                await SensorDataCRUD._update_core(data=update, session=db_session)

        # Очистка старых данных
        if to_cleanup_devices:
            cutoff = datetime.now() - timedelta(days=retention_days)
            stmt = delete(SensorData).where(
                and_(
                    SensorData.device_id.in_(to_cleanup_devices),
                    SensorData.timestamp < cutoff,
                )
            )
            await db_session.execute(stmt)

        # Один коммит для всех операций
        await db_session.commit()
        logger.debug(f"Сохранено в БД: {len(to_insert)} записей")
        return len(to_insert)

    except Exception as e:
        logger.error


def _is_data_changed(last_data: Optional[SensorData], new_data: dict):
    if last_data is None:
        return True
    if not hasattr(last_data, "_parsed_data"):
        try:
            last_data._parsed_data = json.loads(last_data.data)
        except json.JSONDecodeError:
            return True
    return last_data._parsed_data != new_data


async def extract_numeric_value(data: dict) -> Optional[float]:
    """Extracts a numeric value from a data dictionary."""
    if data.get("value") is not None:
        try:
            return float(data["value"])
        except (ValueError, TypeError):
            pass

    numeric_values = [v for v in data.values() if isinstance(v, (int, float))]
    return sum(numeric_values) / len(numeric_values) if numeric_values else None


async def get_last_device_data(
    db_session: AsyncSession, device_id: str
) -> Optional[SensorData]:
    """Gets the latest record for the device from the database."""
    try:
        result = await db_session.execute(
            select(SensorData)
            .where(SensorData.device_id == device_id)
            .order_by(SensorData.timestamp.desc())
            .limit(1)
        )
        return result.scalars().first()
    except Exception as e:
        logger.error(
            f"Error when getting the last record for {device_id}: {e}",
            exc_info=True,
        )
        return None
