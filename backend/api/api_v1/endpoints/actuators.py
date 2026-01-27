from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from crud.actuators import ActuatorCRUD
from db.database import get_async_session
from schemas.actuators import ActuatorRead, ActuatorUpdate
from utils.automations import AutomationEngine
from utils.dependencies import get_automation_engine

router = APIRouter(prefix="/actuators", tags=["actuators"])


@router.patch("/update", response_model=ActuatorRead)
async def actuators_update(
    actuator: ActuatorUpdate,
    session: AsyncSession = Depends(get_async_session),
    engine: AutomationEngine = Depends(get_automation_engine),
):
    if actuator.is_active in [True, False]:
        await engine._control_device(actuator.device_id, actuator.is_active)
    return await ActuatorCRUD.update(actuator=actuator, session=session)


@router.get("/get/all", response_model=Optional[List[ActuatorRead]])
async def get_sensors(session: AsyncSession = Depends(get_async_session)):
    return await ActuatorCRUD.get_all(session)


@router.get("/get/{device_id}", response_model=ActuatorRead)
async def get_actuator(
    device_id: str, session: AsyncSession = Depends(get_async_session)
):
    return await ActuatorCRUD.get(device_id=device_id, session=session)
