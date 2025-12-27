from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


class SensorMessage(BaseModel):
    device_id: str
    timestamp: str
    data: Dict[str, Any]
    value: Optional[float] = None


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


class DeviceUpdateSchema(DeviceBaseSchema):
    device_id: Optional[str]
    name: Optional[str]
    description: Optional[str]

    def model_post_init(self, __context):
        if not any(self.__dict__.values()):
            raise ValueError("At least one field must be provided for update")
