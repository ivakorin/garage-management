import logging
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import async_session_context
from models.plugins import PluginRegistry
from schemas.plugins import PluginReadSchema, PluginUpdateSchema, PluginBaseSchema

logger = logging.getLogger(__name__)


class Plugins:

    @staticmethod
    async def add(plugin: PluginBaseSchema, session: AsyncSession) -> PluginReadSchema:
        try:
            plugin_db = PluginRegistry(
                **plugin.model_dump(exclude_none=True, exclude_unset=True)
            )
            session.add(
                plugin_db,
            )
            await session.commit()
            return await Plugins.get(module_name=plugin.module_name, session=session)
        except Exception as e:
            await session.rollback()
            logger.error(e)

    @staticmethod
    async def update(data: PluginUpdateSchema, session: AsyncSession) -> PluginReadSchema:
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
            return PluginReadSchema.model_validate(
                result.scalars().first(), from_attributes=True
            )
        except Exception as e:
            await session.rollback()
            logger.error(e)
            raise HTTPException(status_code=400, detail="Plugins not found")

    @staticmethod
    async def get(module_name: str, session: AsyncSession) -> Optional[PluginReadSchema]:
        stmt = select(PluginRegistry).where(PluginRegistry.module_name == module_name)
        try:
            result = await session.execute(stmt)
            plugin = result.scalars().first()
            if plugin:
                return PluginReadSchema.model_validate(plugin, from_attributes=True)
            return None
        except Exception as e:
            await session.rollback()
            logger.error(e)

    @staticmethod
    async def get_all(session: AsyncSession) -> List[PluginReadSchema]:
        stmt = select(PluginRegistry).order_by(PluginRegistry.created_at.desc())
        try:
            result = await session.execute(stmt)
            if result:
                result = result.scalars().all()
                return [
                    PluginReadSchema.model_validate(plugin, from_attributes=True)
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
