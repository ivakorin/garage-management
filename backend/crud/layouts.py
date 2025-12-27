import json
import logging
from typing import List, Any

from fastapi import HTTPException
from sqlalchemy import select, insert, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.layouts import Layout as LayoutModel
from schemas.layouts import LayoutSchema

logger = logging.getLogger(__name__)


class Layout:

    @staticmethod
    async def upsert(layout: LayoutSchema, session: AsyncSession) -> LayoutSchema:
        try:
            stmt = select(LayoutModel)
            result = await session.execute(stmt)
            layout_exists = result.scalars().first()
            layout_data_json = json.dumps(layout.model_dump())

            if layout_exists:
                stmt = (
                    update(LayoutModel)
                    .where(LayoutModel.id == 1)
                    .values(layout=layout_data_json)
                )
                await session.execute(stmt)
            else:
                stmt = insert(LayoutModel).values(id=1, layout=layout_data_json)
                await session.execute(stmt)

            await session.commit()

            return layout

        except Exception as e:
            await session.rollback()
            logger.error(f"Error in upsert: {e}")
            raise HTTPException(status_code=400, detail="Failed to save layout") from e

    @staticmethod
    async def get(session: AsyncSession) -> LayoutSchema | List[Any]:
        try:
            stmt = select(LayoutModel)
            result = await session.execute(stmt)
            layout = result.scalars().first()

            if layout:
                layout_data = json.loads(layout.layout)
                return LayoutSchema.model_validate(layout_data)
            else:
                return []

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            raise HTTPException(status_code=500, detail="Invalid JSON in layout field")
        except Exception as e:
            await session.rollback()
            logger.error(f"Error in get: {e}")
            raise HTTPException(status_code=400, detail="Failed to get layout") from e
