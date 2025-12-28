import datetime
import json
import logging
from typing import Optional, List

from fastapi import HTTPException
from sqlalchemy import delete, select, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import DeviceData, SystemSetting, Device
from schemas.sensor import DeviceReadSchema, DeviceUpdateSchema

logger = logging.getLogger(__name__)


class DeviceDataCRUD:
    @staticmethod
    async def create(
        session: AsyncSession, device_id: str, data: dict, value: Optional[float] = None
    ) -> DeviceData:
        db_data = DeviceData(
            device_id=device_id,
            timestamp=datetime.datetime.now(),
            data=json.dumps(data),
            value=value,
        )
        session.add(db_data)
        await session.flush()  # Чтобы получить ID до commit
        return db_data

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
    async def get_retention_days(session: AsyncSession) -> int:
        result = await session.execute(
            select(SystemSetting).where(SystemSetting.key == "data_retention_days")
        )
        setting = result.scalars().first()
        if setting:
            return max(1, int(setting.value))
        return 7  # По умолчанию 7 дней

    @staticmethod
    async def cleanup_old_data(
        session: AsyncSession, device_id: str, retention_days: int
    ):
        cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
            days=retention_days
        )
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
