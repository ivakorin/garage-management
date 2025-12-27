from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from crud.sensor import DeviceDataCRUD
from db.database import get_async_session
from schemas.sensor import DeviceReadSchema

router = APIRouter(prefix="/sensors", tags=["sensors"])


@router.get("/get", response_model=List[DeviceReadSchema])
async def get_sensors(session: AsyncSession = Depends(get_async_session)):
    return await DeviceDataCRUD.get_all(session=session)
