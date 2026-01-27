import datetime
import logging
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import delete, select, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import SensorData, Sensor
from schemas.sensors import SensorReadSchema, SensoeUpdateSchema, SensorDataReadSchema

logger = logging.getLogger(__name__)


class SensorDataCRUD:

    @staticmethod
    async def update(data: SensoeUpdateSchema, session: AsyncSession) -> SensorReadSchema:
        try:
            update_stmt = (
                update(Sensor)
                .where(Sensor.device_id == data.device_id)
                .values(
                    data.model_dump(
                        exclude_defaults=True, exclude_none=True, exclude_unset=True
                    )
                )
            )
            await session.execute(update_stmt)
            await session.commit()

            return await SensorDataCRUD.get(data.device_id, session)

        except Exception as e:
            await session.rollback()
            logger.error(f"Error updating device {data.device_id}: {e}")
            raise HTTPException(status_code=400, detail="Failed to update device") from e

    @staticmethod
    async def drop_state(session: AsyncSession) -> None:
        try:
            stmt = update(Sensor).values(online=False)
            await session.execute(stmt)
            await session.commit()
            logger.info("All devices set to offline successfully")

        except Exception as e:
            await session.rollback()
            logger.error(f"Error dropping state: {e}", exc_info=True)

    @staticmethod
    async def _update_core(data: SensoeUpdateSchema, session: AsyncSession):
        """
        Базовая логика обновления — без commit/rollback.
        Используется в batch-операциях.
        """
        update_stmt = (
            update(Sensor)
            .where(Sensor.device_id == data.device_id)
            .values(data.model_dump(exclude_defaults=True, exclude_none=True))
        )
        await session.execute(update_stmt)

    @staticmethod
    async def cleanup_old_data(
        session: AsyncSession, device_id: str, retention_days: int
    ):
        cutoff = datetime.datetime.now() - datetime.timedelta(days=retention_days)
        stmt = delete(SensorData).where(
            SensorData.device_id == device_id, SensorData.timestamp < cutoff
        )
        await session.execute(stmt)

    @staticmethod
    async def get_all(session: AsyncSession) -> List[SensorReadSchema]:
        subq = (
            select(
                SensorData.device_id,
                func.max(SensorData.timestamp).label("max_timestamp"),
            )
            .group_by(SensorData.device_id)
            .subquery()
        )
        stmt = (
            select(Sensor, SensorData)
            .join(
                SensorData,
                and_(
                    Sensor.device_id == SensorData.device_id,
                    SensorData.timestamp == subq.c.max_timestamp,
                ),
            )
            .outerjoin(subq, SensorData.device_id == subq.c.device_id)
            .order_by(Sensor.created_at.desc())
        )

        try:
            result = await session.execute(stmt)
            rows = result.all()

            if not rows:
                return []

            # 3. Формируем ответ: Device + последняя DeviceData
            devices = []
            for device, data in rows:
                # Создаём dict на основе Device, добавляем timestamp из DeviceData
                device_dict = device.__dict__.copy()
                device_dict["timestamp"] = data.timestamp if data else None
                # Валидируем через Pydantic
                devices.append(
                    SensorReadSchema.model_validate(device_dict, from_attributes=True)
                )

            return devices

        except Exception as e:
            await session.rollback()
            logger.error(f"Error fetching devices with latest data: {e}")
            raise HTTPException(status_code=400, detail="No data found") from e

    @staticmethod
    async def get(device_id: str, session: AsyncSession) -> SensorReadSchema:
        subq = (
            select(
                SensorData.device_id,
                SensorData.value,
                func.max(SensorData.timestamp).label("max_timestamp"),
            )
            .group_by(SensorData.device_id)
            .subquery()
        )

        stmt = (
            select(Sensor, SensorData)
            .join(
                SensorData,
                and_(
                    Sensor.device_id == SensorData.device_id,
                    SensorData.timestamp == subq.c.max_timestamp,
                ),
            )
            .outerjoin(subq, SensorData.device_id == subq.c.device_id)
            .where(Sensor.device_id == device_id)
            .order_by(Sensor.created_at.desc())
        )

        result = await session.execute(stmt)
        row = result.first()

        if not row:
            await session.rollback()
            raise HTTPException(status_code=404, detail="Device not found")

        device, device_data = row
        device_dict = device.__dict__.copy()
        device_dict["timestamp"] = device_data.timestamp if device_data else None
        device_dict["value"] = device_data.value if device_data else None
        return SensorReadSchema.model_validate(device_dict, from_attributes=True)

    @staticmethod
    async def search(pattern: str, session: AsyncSession) -> Optional[List[str]]:
        stmt = select(Sensor.device_id).where(Sensor.device_id.like(f"%{pattern}%"))
        try:
            result = await session.execute(stmt)
            rows = result.scalars().all()
            if rows:
                return list(rows)
            return []

        except Exception as e:
            await session.rollback()
            logger.error(f"Error fetching devices: {e}")

    @staticmethod
    async def get_av_value(measure_unit: str, session: AsyncSession) -> Optional[float]:
        stmt = select(func.avg(SensorData.value)).where(SensorData.unit == measure_unit)
        try:
            result = await session.execute(stmt)
            data = result.scalar()
            return float(data) if data else None
        except Exception as e:
            await session.rollback()
            logger.error(f"Error fetching av value: {e}")

    @staticmethod
    async def get_value(device_id: str, session: AsyncSession) -> Optional[float]:
        stmt = (
            select(SensorData.value)
            .where(SensorData.device_id == device_id)
            .order_by(SensorData.timestamp.desc())
        )
        try:
            result = await session.execute(stmt)
            result = result.scalar()
            if result:
                return float(result)
            return None
        except Exception as e:
            await session.rollback()
            logger.error(f"Error fetching value: {e}")

    @staticmethod
    async def get_history(
        session: AsyncSession,
        device_id: str,
    ) -> List[SensorDataReadSchema]:
        stmt = (
            select(
                SensorData.device_id,
                SensorData.timestamp,
                SensorData.value,
                SensorData.unit,
            )
            .where(SensorData.device_id == device_id)
            .order_by(SensorData.timestamp.desc())
        )
        try:
            result = await session.execute(stmt)
            rows = result.all()  # Возвращает список кортежей

            if not rows:
                return []

            validated_data = []
            for row in rows:
                # row — это кортеж (device_id, timestamp, value, unit)
                schema = SensorDataReadSchema(
                    device_id=row[0],
                    timestamp=row[1],
                    value=row[2],
                    unit=row[3],
                )
                validated_data.append(schema)

            return validated_data

        except Exception as e:
            await session.rollback()
            logger.error(f"Error fetching history: {e}")
            raise HTTPException(status_code=500, detail="Internal server error") from e
