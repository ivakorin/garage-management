from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends

from crud.plugins import Plugins
from db.database import get_async_session
from schemas.plugins import PluginReadShema, PluginUpdateSchema
from utils.collector import restart_collector

router = APIRouter(prefix="/plugins", tags=["Plugins"])


@router.get("/get", response_model=List[PluginReadShema])
async def list_plugins(session=Depends(get_async_session)):
    return await Plugins.get_all(session)


@router.patch("/update/", response_model=PluginReadShema)
async def update_plugin(data: PluginUpdateSchema, session=Depends(get_async_session)):
    data.updated_at = datetime.now()
    result = await Plugins.update(data=data, session=session)
    await restart_collector()
    return result


# @router.get("/{device_id}/status")
# def get_plugin_status(device_id: str):
#     pass
#     # if device_id not in plugins:
#     #     raise HTTPException(status_code=404, detail="Plugin not found")
#     # status = plugins[device_id].get_status()
#     # return {"device_id": device_id, "status": status}
#
#
# @router.post("/{device_id}/command")
# async def send_command(device_id: str, command: dict):
#     pass
# if device_id not in plugins:
#     raise HTTPException(status_code=404, detail="Plugin not found")
# try:
#     await plugins[device_id].handle_command(command)
#     return {"status": "command sent", "device_id": device_id}
# except Exception as e:
#     raise HTTPException(status_code=500, detail=str(e))
