from enum import Enum
from typing import Optional

from pydantic import BaseModel


class TriggerType(str, Enum):
    sensor_change = "sensor_change"
    time = "time"
    manual = "manual"


class ActionType(str, Enum):
    send_notification = "send_notification"
    toggle_device = "toggle_device"


class Trigger(BaseModel):
    type: TriggerType
    sensor_id: Optional[str] = None
    condition: Optional[str] = None
    time: Optional[str] = None  # HH:MM


class Action(BaseModel):
    type: ActionType
    recipient: Optional[str] = None
    message: Optional[str] = None
    device_id: Optional[str] = None
    state: Optional[bool] = None


class Automation(BaseModel):
    id: str
    name: str
    trigger: Trigger
    action: Action
    enabled: bool = True
