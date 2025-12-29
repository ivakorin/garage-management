import datetime
import logging
from typing import List

from fastapi import HTTPException
from sqlalchemy import delete, select, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import DeviceData, Device
from schemas.sensor import DeviceReadSchema, DeviceUpdateSchema, DeviceDataReadSchema

logger = logging.getLogger(__name__)


class DeviceDataCRUD:

    @staticmethod
    async def update(data: DeviceUpdateSchema, session: AsyncSession) -> DeviceReadSchema:
        try:
            update_stmt = (
                update(Device)
                .where(Device.device_id == data.device_id)
                .values(
                    data.model_dump(
                        exclude_defaults=True, exclude_none=True, exclude_unset=True
                    )
                )
            )
            await session.execute(update_stmt)
            await session.commit()

            return await DeviceDataCRUD.get(data.device_id, session)

        except Exception as e:
            await session.rollback()
            logger.error(f"Error updating device {data.device_id}: {e}")
            raise HTTPException(status_code=400, detail="Failed to update device") from e

    @staticmethod
    async def cleanup_old_data(
        session: AsyncSession, device_id: str, retention_days: int
    ):
        cutoff = datetime.datetime.now() - datetime.timedelta(days=retention_days)
        stmt = delete(DeviceData).where(
            DeviceData.device_id == device_id, DeviceData.timestamp < cutoff
        )
        await session.execute(stmt)

    @staticmethod
    async def get_all(session: AsyncSession) -> List[DeviceReadSchema]:
        subq = (
            select(
                DeviceData.device_id,
                func.max(DeviceData.timestamp).label("max_timestamp"),
            )
            .group_by(DeviceData.device_id)
            .subquery()
        )
        stmt = (
            select(Device, DeviceData)
            .join(
                DeviceData,
                and_(
                    Device.device_id == DeviceData.device_id,
                    DeviceData.timestamp == subq.c.max_timestamp,
                ),
            )
            .outerjoin(subq, DeviceData.device_id == subq.c.device_id)
            .order_by(Device.created_at.desc())
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
                    DeviceReadSchema.model_validate(device_dict, from_attributes=True)
                )

            return devices

        except Exception as e:
            await session.rollback()
            logger.error(f"Error fetching devices with latest data: {e}")
            raise HTTPException(status_code=400, detail="No data found") from e

    @staticmethod
    async def get(device_id: str, session: AsyncSession) -> DeviceReadSchema:
        subq = (
            select(
                DeviceData.device_id,
                func.max(DeviceData.timestamp).label("max_timestamp"),
            )
            .group_by(DeviceData.device_id)
            .subquery()
        )

        stmt = (
            select(Device, DeviceData)
            .join(
                DeviceData,
                and_(
                    Device.device_id == DeviceData.device_id,
                    DeviceData.timestamp == subq.c.max_timestamp,
                ),
            )
            .outerjoin(subq, DeviceData.device_id == subq.c.device_id)
            .where(Device.device_id == device_id)
            .order_by(Device.created_at.desc())
        )

        result = await session.execute(stmt)
        row = result.first()

        if not row:
            await session.rollback()
            raise HTTPException(status_code=404, detail="Device not found")

        device, device_data = row
        device_dict = device.__dict__.copy()
        device_dict["timestamp"] = device_data.timestamp if device_data else None
        return DeviceReadSchema.model_validate(device_dict, from_attributes=True)

    @staticmethod
    async def get_history(
        session: AsyncSession,
        device_id: str,
    ) -> List[DeviceDataReadSchema]:
        stmt = (
            select(
                DeviceData.device_id,
                DeviceData.timestamp,
                DeviceData.value,
                DeviceData.unit,
            )
            .where(DeviceData.device_id == device_id)
            .order_by(DeviceData.timestamp.desc())
        )
        try:
            result = await session.execute(stmt)
            rows = result.all()  # Возвращает список кортежей

            if not rows:
                return []

            validated_data = []
            for row in rows:
                # row — это кортеж (device_id, timestamp, value, unit)
                schema = DeviceDataReadSchema(
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
