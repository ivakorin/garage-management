import json
import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.settings import settings
from crud.sensor import DeviceDataCRUD
from models import Device, DeviceData
from schemas.sensor import SensorMessage, DeviceUpdateSchema

logger = logging.getLogger(__name__)


async def save_batch_to_db(
    db_session: AsyncSession,
    messages: List[SensorMessage],
    retention_days: int = settings.app_settings.keep_data,
) -> int:
    """
    Batch-saving messages to the database with checking for changes and clearing old records.

    :param retention_days: time period to keep old records
    :param db_session: database session for operations
    :param messages: list of messages to save
    :param retention days: number of days of data storage (for cleaning)
    :return: number of successfully saved records
    """
    if not messages:
        return 0

    try:
        device_ids = {msg.device_id for msg in messages}
        result = await db_session.execute(
            select(Device).where(Device.device_id.in_(device_ids))
        )
        devices = {dev.device_id: dev for dev in result.scalars().all()}
        last_data_result = await db_session.execute(
            select(DeviceData)
            .where(DeviceData.device_id.in_(device_ids))
            .order_by(DeviceData.timestamp.desc())
        )
        last_data_list = last_data_result.scalars().all()
        last_data_map = {item.device_id: item for item in last_data_list}

        to_insert: List[DeviceData] = []
        to_cleanup: set = set()

        for msg in messages:
            if msg.device_id not in devices:
                device = Device(device_id=msg.device_id, name=msg.device_id)
                db_session.add(device)
                devices[msg.device_id] = device
            else:
                updated_online = DeviceUpdateSchema(
                    device_id=msg.device_id,
                    online=msg.online,
                    updated_at=datetime.now(),
                )
                await DeviceDataCRUD.update(data=updated_online, session=db_session)
            last_data = last_data_map.get(msg.device_id)
            if _is_data_changed(last_data, msg.data):
                to_cleanup.add(msg.device_id)
                db_data = DeviceData(
                    device_id=msg.device_id,
                    timestamp=datetime.fromisoformat(msg.timestamp),
                    data=json.dumps(msg.data),
                    value=msg.value,
                    unit=msg.unit,
                )
                to_insert.append(db_data)
        if to_cleanup:
            for dev_id in to_cleanup:
                await DeviceDataCRUD.cleanup_old_data(
                    session=db_session,
                    device_id=dev_id,
                    retention_days=retention_days,
                )
        if to_insert:
            db_session.add_all(to_insert)
            await db_session.commit()
            logger.info(f"Batch saved in DB: {len(to_insert)} records")
            return len(to_insert)

        await db_session.commit()
        return 0

    except Exception as e:
        logger.error(f"Error when saving batch to DATABASE: {e}", exc_info=True)
        await db_session.rollback()
        return 0


def _is_data_changed(
    last_data: Optional[DeviceData], new_data: dict, cached_data: dict = None
) -> bool:
    """
    Checks whether the data has changed compared to the last record.

    :param last_data: last record from the database (may be None)
    :param new_data: new data for comparison
    :param cached_data: cached data from the previous state (for optimization)
    :return: True if the data has changed
    """
    if last_data is None:
        return True
    if cached_data is not None:
        return cached_data != new_data
    try:
        cached = json.loads(last_data.data)
        return cached != new_data
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"last_data.data parsing error: {e}")
        return True


async def extract_numeric_value(data: dict) -> Optional[float]:
    """
    Extracts a numeric value from a data dictionary.

    Logic:
    1. If there is a 'value' key, we take it.
    2. Otherwise, we look for all numeric values and take the average.

    :param data: data dictionary
    :return: numeric value or None
    """
    if data.get("value") is not None:
        try:
            return float(data["value"])
        except (ValueError, TypeError):
            pass

    numeric_values = [v for v in data.values() if isinstance(v, (int, float))]
    if numeric_values:
        return sum(numeric_values) / len(numeric_values)

    return None


async def get_last_device_data(
    db_session: AsyncSession, device_id: str
) -> Optional[DeviceData]:
    """
    Gets the latest record for the device from the database.

    :param db_session: DB session
    :param device_id: device ID
    :return: last DeviceData entry or None
    """
    try:
        result = await db_session.execute(
            select(DeviceData)
            .where(DeviceData.device_id == device_id)
            .order_by(DeviceData.timestamp.desc())
            .limit(1)
        )
        return result.scalars().first()
    except Exception as e:
        logger.error(
            f"Error when getting the last record for {device_id}: {e}",
            exc_info=True,
        )
        return None
