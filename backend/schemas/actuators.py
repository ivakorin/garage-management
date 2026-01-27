from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ActuatorBase(BaseModel):
    device_id: str
    name: str
    description: Optional[str] = None
    pin: int
    inverted: bool = False
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class ActuatorCommandBase(BaseModel):
    device_id: str
    command: str
    success: bool
    error_message: Optional[str] = None
    payload: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class ActuatorCreate(ActuatorBase):
    pass


class ActuatorCommandCreate(ActuatorCommandBase):
    pass


class ActuatorRead(ActuatorBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ActuatorCommandRead(ActuatorCommandBase):
    id: int
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)


class ActuatorUpdate(BaseModel):
    device_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    pin: Optional[int] = None
    inverted: Optional[bool] = None
    is_active: Optional[bool] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class ActuatorCommandUpdate(BaseModel):
    success: Optional[bool] = None
    error_message: Optional[str] = None
    payload: Optional[str] = None
    timestamp: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ActuatorDelete(BaseModel):
    id: int
    model_config = ConfigDict(from_attributes=True)


class ActuatorCommandDelete(BaseModel):
    id: int
    model_config = ConfigDict(from_attributes=True)


class ActuatorBulkDelete(BaseModel):
    ids: list[int]
    model_config = ConfigDict(from_attributes=True)


class ActuatorCommandBulkDelete(BaseModel):
    ids: list[int]
    model_config = ConfigDict(from_attributes=True)
