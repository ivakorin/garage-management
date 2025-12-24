from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DeviceDataCreateSchema(BaseModel):
    device_id:str
    device_name:str
    timestamp:datetime
    data: str
    value: Optional[float]