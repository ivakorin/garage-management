from enum import StrEnum
from typing import Optional, List, Literal, Dict, Any

from pydantic import BaseModel


class ConditionOperator(StrEnum):
    EQ = "=="
    NE = "!="
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="


class Hysteresis(BaseModel):
    low: float
    high: float


class Condition(BaseModel):
    sensor_id: str
    operator: ConditionOperator
    value: float
    hysteresis: Optional[Hysteresis] = None
    logic: Literal["AND", "OR"] = "AND"


class TriggerType(StrEnum):
    sensor_change = "sensor_change"
    time = "time"
    manual = "manual"
    multi_condition = "multi_condition"


class Trigger(BaseModel):
    type: TriggerType
    sensor_id: Optional[str] = None
    time: Optional[str] = None  # HH:MM
    conditions: Optional[List[Condition]] = None
    hysteresis: Optional[Hysteresis] = None
    combine_logic: Literal["AND", "OR"] = "AND"


class ActionType(StrEnum):
    send_notification = "send_notification"
    turn_on = "turn_on"
    turn_off = "turn_off"
    toggle_device = "toggle_device"
    set_value = "set_value"
    group_action = "group_action"


class Action(BaseModel):
    type: ActionType
    recipient: Optional[str] = None
    message: Optional[str] = None
    device_id: Optional[str] = None
    state: Optional[bool] = None
    value: Optional[float] = None
    # Для group_action
    commands: Optional[List[Dict[str, Any]]] = None


class Automation(BaseModel):
    id: str
    name: str
    trigger: Trigger
    action: Action
    enabled: bool = True
    description: Optional[str] = None
