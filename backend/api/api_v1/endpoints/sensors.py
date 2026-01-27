from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from crud.sensors import SensorDataCRUD
from db.database import get_async_session
from schemas.sensors import SensorReadSchema, SensoeUpdateSchema, SensorDataReadSchema

router = APIRouter(prefix="/sensors", tags=["sensors"])


@router.get("/get/all", response_model=List[SensorReadSchema])
async def get_sensors(session: AsyncSession = Depends(get_async_session)):
    return await SensorDataCRUD.get_all(session=session)


@router.get("/get/history/{device_id}", response_model=List[SensorDataReadSchema])
async def get_sensors_history(
    device_id: str, session: AsyncSession = Depends(get_async_session)
):
    return await SensorDataCRUD.get_history(session=session, device_id=device_id)


@router.get("/get/{device_id}", response_model=SensorReadSchema)
async def get_sensor(device_id: str, session: AsyncSession = Depends(get_async_session)):
    return await SensorDataCRUD.get(device_id=device_id, session=session)


@router.get("/get/avg_value/{measure_unit}", response_model=Optional[float])
async def get_avg_value(
    measure_unit: str, session: AsyncSession = Depends(get_async_session)
):
    return await SensorDataCRUD.get_av_value(session=session, measure_unit=measure_unit)


@router.patch("/update", response_model=SensorReadSchema)
async def update_sensor(
    sensor: SensoeUpdateSchema, session: AsyncSession = Depends(get_async_session)
):
    sensor.updated_at = datetime.now()
    return await SensorDataCRUD.update(data=sensor, session=session)
