from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


class SensorMessage(BaseModel):
    device_id: str
    timestamp: str
    data: Dict[str, Any]
    value: Optional[float] = None
    unit: Optional[str] = None


class DeviceBaseSchema(BaseModel):
    device_id: str
    name: str
    description: Optional[str]


class DeviceReadSchema(DeviceBaseSchema):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = {
        "from_attributes": True,
        "str_strip_whitespace": True,
        "str_to_lower": False,
    }
    timestamp: datetime


class DeviceUpdateSchema(BaseModel):
    id: int
    device_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    updated_at: Optional[datetime] = None

    def model_post_init(self, __context):
        if not any(self.__dict__.values()):
            raise ValueError("At least one field must be provided for update")
