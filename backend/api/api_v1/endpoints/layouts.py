from typing import Optional, List, Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from crud.layouts import Layout
from db.database import get_async_session
from schemas.layouts import LayoutSchema

router = APIRouter(prefix="/layouts", tags=["layouts"])


@router.get("/get", response_model=Optional[LayoutSchema] | List[Any])
async def get_layout(session: AsyncSession = Depends(get_async_session)):
    return await Layout.get(session=session)


@router.patch("/save", response_model=LayoutSchema)
async def save_layout(
    layout: LayoutSchema, session: AsyncSession = Depends(get_async_session)
):
    return await Layout.upsert(session=session, layout=layout)
