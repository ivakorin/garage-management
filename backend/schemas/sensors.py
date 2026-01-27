from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


class SensorMessage(BaseModel):
    device_id: str
    timestamp: str
    data: Dict[str, Any]
    value: Optional[float | str] = None
    unit: str
    online: Optional[bool] = None


class SensorBaseSchema(BaseModel):
    device_id: str
    name: str
    description: Optional[str]


class SensorReadSchema(SensorBaseSchema):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = {
        "from_attributes": True,
        "str_strip_whitespace": True,
        "str_to_lower": False,
    }
    timestamp: datetime
    value: Optional[Any] = None
    online: bool


class SensoeUpdateSchema(BaseModel):
    id: Optional[int] = None
    device_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    updated_at: Optional[datetime] = None
    online: bool

    def model_post_init(self, __context):
        if not any(self.__dict__.values()):
            raise ValueError("At least one field must be provided for update")


class SensorDataReadSchema(BaseModel):
    device_id: str
    timestamp: datetime
    value: Optional[float] = None
    unit: Optional[str] = None
