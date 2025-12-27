import logging
from typing import List

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import async_session_context
from models.plugins import PluginRegistry
from schemas.plugins import PluginReadShema, PluginUpdateSchema

logger = logging.getLogger(__name__)


class Plugins:

    @staticmethod
    async def update(data: PluginUpdateSchema, session: AsyncSession) -> PluginReadShema:
        stmt = (
            update(PluginRegistry)
            .where(PluginRegistry.id == data.id)
            .values(
                data.model_dump(
                    exclude_defaults=True, exclude_none=True, exclude_unset=True
                )
            )
        )
        try:
            await session.execute(stmt)
            await session.commit()
            result = await session.execute(
                select(PluginRegistry).where(PluginRegistry.id == data.id)
            )
            return PluginReadShema.model_validate(
                result.scalars().first(), from_attributes=True
            )
        except Exception as e:
            await session.rollback()
            logger.error(e)
            raise HTTPException(status_code=400, detail="Plugins not found")

    @staticmethod
    async def get_all(session: AsyncSession) -> List[PluginReadShema]:
        stmt = select(PluginRegistry).order_by(PluginRegistry.created_at.desc())
        try:
            result = await session.execute(stmt)
            if result:
                result = result.scalars().all()
                return [
                    PluginReadShema.model_validate(plugin, from_attributes=True)
                    for plugin in result
                ]
            return []
        except Exception as e:
            await session.rollback()
            logger.error(e)
            raise HTTPException(status_code=400, detail="Plugins not found")

    @staticmethod
    async def is_running(device_id: str) -> bool:
        stmt = select(PluginRegistry.is_running).where(
            PluginRegistry.device_id == device_id
        )
        async with async_session_context() as session:
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
