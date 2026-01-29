import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Set

from sqlalchemy import select, and_, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

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
    """
    Batch-saving messages to the database with checking for changes and clearing old records.
    """
    if not messages:
        return 0

    try:
        device_ids = {msg.device_id for msg in messages}

        # 1. Load existing Sensors (only needed fields)
        sensor_result = await db_session.execute(
            select(Sensor)
            .where(Sensor.device_id.in_(device_ids))
            .options(load_only(Sensor.device_id, Sensor.name))
        )
        devices: Dict[str, Sensor] = {
            dev.device_id: dev for dev in sensor_result.scalars().all()
        }

        # 2. Load latest SensorData per device (most recent per device_id)
        # Using subquery for efficiency
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
        last_data_list = last_data_result.scalars().all()
        last_data_map: Dict[str, SensorData] = {
            item.device_id: item for item in last_data_list
        }

        to_insert: List[SensorData] = []
        to_update_online: List[SensorUpdateSchema] = []
        to_cleanup_devices: Set[str] = set()

        # 3. Process each message
        for msg in messages:
            # Ensure Sensor exists
            if msg.device_id not in devices:
                device = Sensor(device_id=msg.device_id, name=msg.device_id)
                db_session.add(device)
                devices[msg.device_id] = device
            else:
                to_update_online.append(
                    SensorUpdateSchema(
                        device_id=msg.device_id,
                        online=msg.online,
                        updated_at=datetime.now(),
                    )
                )

            # Check if data changed
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

        # 4. Bulk insert new SensorData (real SQLAlchemy method)
        if to_insert:
            db_session.add_all(to_insert)

        # 5. Update online status — batch via existing CRUD (assumed to be efficient)
        if to_update_online:
            for update in to_update_online:
                await SensorDataCRUD._update_core(data=update, session=db_session)

        # 6. Cleanup old data — batch delete per device_ids
        if to_cleanup_devices:
            cutoff = datetime.now() - timedelta(days=retention_days)
            stmt = delete(SensorData).where(
                and_(
                    SensorData.device_id.in_(to_cleanup_devices),
                    SensorData.timestamp < cutoff,
                )
            )
            await db_session.execute(stmt)

        # 7. Single commit
        await db_session.commit()
        logger.debug(f"Batch saved in DB: {len(to_insert)} records")
        return len(to_insert)

    except Exception as e:
        logger.error(f"Error when saving batch to DATABASE: {e}", exc_info=True)
        await db_session.rollback()
        return 0


def _is_data_changed(
    last_data: Optional[SensorData],
    new_data: dict,
    cached_data: Optional[dict] = None,
) -> bool:
    """Checks whether the data has changed compared to the last record."""
    if last_data is None:
        return True
    if cached_data is not None:
        return cached_data != new_data

    try:
        # Cache parsed data to avoid repeated JSON parsing
        if not hasattr(last_data, "_parsed_data"):
            last_data._parsed_data = json.loads(last_data.data)
        return last_data._parsed_data != new_data
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"last_data.data parsing error: {e}")
        return True


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
