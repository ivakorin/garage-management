import datetime
import json
import logging
from typing import Optional, List

from fastapi import HTTPException
from sqlalchemy import delete, select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models import DeviceData, SystemSetting, Device
from schemas.sensor import DeviceReadSchema

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
        # 1. Находим последнюю запись DeviceData для каждого device_id
        subq = (
            select(
                DeviceData.device_id,
                func.max(DeviceData.timestamp).label("max_timestamp"),
            )
            .group_by(DeviceData.device_id)
            .subquery()
        )

        # 2. Соединяем Device с последней записью DeviceData
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
