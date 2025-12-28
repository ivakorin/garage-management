from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from crud.sensor import DeviceDataCRUD
from db.database import get_async_session
from schemas.sensor import DeviceReadSchema, DeviceUpdateSchema

router = APIRouter(prefix="/sensors", tags=["sensors"])


@router.get("/get/all", response_model=List[DeviceReadSchema])
async def get_sensors(session: AsyncSession = Depends(get_async_session)):
    return await DeviceDataCRUD.get_all(session=session)


@router.get("/get/{device_id}", response_model=DeviceReadSchema)
async def get_sensor(device_id: str, session: AsyncSession = Depends(get_async_session)):
    return await DeviceDataCRUD.get(device_id=device_id, session=session)


@router.patch("/update", response_model=DeviceReadSchema)
async def update_sensor(
    sensor: DeviceUpdateSchema, session: AsyncSession = Depends(get_async_session)
):
    sensor.updated_at = datetime.now()
    return await DeviceDataCRUD.update(data=sensor, session=session)
