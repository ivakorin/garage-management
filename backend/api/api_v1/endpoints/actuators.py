from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from crud.actuators import ActuatorCRUD
from db.database import get_async_session
from schemas.actuators import ActuatorRead, ActuatorUpdate
from utils.automations import AutomationEngine

router = APIRouter(prefix="/actuators", tags=["actuators"])


@router.patch("/update", response_model=ActuatorRead)
async def actuators_update(
    actuator: ActuatorUpdate, session: AsyncSession = Depends(get_async_session)
):
    actuator.updated_at = datetime.now()
    if actuator.inverted:
        actuator.is_active = not actuator.is_active
    if actuator.is_active:
        await AutomationEngine()._control_device(actuator.device_id, actuator.is_active)
    return await ActuatorCRUD.update(actuator=actuator, session=session)


@router.get("/get/all", response_model=Optional[List[ActuatorRead]])
async def get_sensors(session: AsyncSession = Depends(get_async_session)):
    result = await ActuatorCRUD.get_all(session)
    for item in result:
        if item.inverted:
            item.is_active = not item.is_active
    return result


@router.get("/get/{device_id}", response_model=ActuatorRead)
async def get_actuator(
    device_id: str, session: AsyncSession = Depends(get_async_session)
):
    result = await ActuatorCRUD.get(device_id=device_id, session=session)
    if result.inverted:
        result.is_active = not result.is_active
    return result
