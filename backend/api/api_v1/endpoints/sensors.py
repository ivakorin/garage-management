from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from crud.plugins import Plugins
from crud.sensors import SensorDataCRUD
from db.database import get_async_session
from schemas.common import CommonResponse
from schemas.sensors import SensorReadSchema, SensorUpdateSchema, SensorDataReadSchema

router = APIRouter(prefix="/sensors", tags=["sensors"])


@router.delete("/delete/{device_id}", response_model=CommonResponse)
async def delete_sensor(
    device_id: str, session: AsyncSession = Depends(get_async_session)
):
    await SensorDataCRUD.delete(session=session, device_id=device_id)
    await Plugins.stop(device_id=device_id, session=session)
    return CommonResponse(success=True, message="Sensor deleted successfully")


@router.patch("/update", response_model=SensorReadSchema)
async def update_sensor(
    sensor: SensorUpdateSchema, session: AsyncSession = Depends(get_async_session)
):
    sensor.updated_at = datetime.now()
    return await SensorDataCRUD.update(data=sensor, session=session)


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


@router.get("/get/latest_avg_value/{measure_unit}", response_model=Optional[float])
async def get_average_latest_value(
    measure_unit: str, session: AsyncSession = Depends(get_async_session)
):
    return await SensorDataCRUD.get_average_latest_value(
        session=session, measure_unit=measure_unit
    )
