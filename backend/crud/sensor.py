import json
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import DeviceData, SystemSetting


class DeviceDataCRUD:
    @staticmethod
    async def create(
        session: AsyncSession,
        device_id: str,
        data: dict,
        value: Optional[float] = None
    ) -> DeviceData:
        db_data = DeviceData(
            device_id=device_id,
            timestamp=datetime.now(),
            data=json.dumps(data),
            value=value
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
        session: AsyncSession,
        device_id: str,
        retention_days: int
    ):
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        stmt = delete(DeviceData).where(
            DeviceData.device_id == device_id,
            DeviceData.timestamp < cutoff
        )
        await session.execute(stmt)
