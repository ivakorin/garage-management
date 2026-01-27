import logging
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import Actuator, ActuatorCommand
from schemas.actuators import (
    ActuatorRead,
    ActuatorCreate,
    ActuatorUpdate,
    ActuatorCommandCreate,
)

logger = logging.getLogger(__name__)


class ActuatorCRUD:

    @staticmethod
    async def add(actuator: ActuatorCreate, session: AsyncSession) -> ActuatorRead:
        try:
            actuator_db = Actuator(
                **actuator.model_dump(exclude_none=True, exclude_unset=True)
            )
            session.add(actuator_db)
            await session.commit()
            return await ActuatorCRUD.get(actuator.device_id, session)
        except Exception as e:
            await session.rollback()
            logger.error(e)

    @staticmethod
    async def update(
        actuator: ActuatorUpdate, session: AsyncSession
    ) -> Optional[ActuatorRead]:
        stmt = (
            update(Actuator)
            .where(Actuator.device_id == actuator.device_id)
            .values(actuator.model_dump(exclude_none=True, exclude_unset=True))
        )
        try:
            await session.execute(stmt)
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(e)

    @staticmethod
    async def add_command(commands: ActuatorCommandCreate, session: AsyncSession):
        try:
            command = ActuatorCommand(
                **commands.model_dump(exclude_none=True, exclude_unset=True)
            )
            session.add(command)
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(e)

    @staticmethod
    async def get(device_id: str, session: AsyncSession) -> Optional[ActuatorRead]:
        stmt = select(Actuator).where(Actuator.device_id == device_id)
        try:
            result = await session.execute(stmt)
            actuator = result.scalars().first()
            if actuator:
                return ActuatorRead.model_validate(actuator, from_attributes=True)
            return None
        except Exception as e:
            await session.rollback()
            logger.error(e)
