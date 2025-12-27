from datetime import datetime
from typing import Optional

from pydantic import BaseModel, model_validator, field_validator


class PluginBaseShema(BaseModel):
    module_name: str
    class_name: str
    device_id: str


class PluginReadShema(PluginBaseShema):
    is_running: bool
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,  # for compatibility with ORM (SQLAlchemy, etc.)
        "str_strip_whitespace": True,
    }


class PluginUpdateSchema(PluginBaseShema):
    id: int
    updated_at: Optional[datetime] = None
    module_name: Optional[str] = None
    class_name: Optional[str] = None
    device_id: Optional[str] = None
    is_running: Optional[bool] = None

    @model_validator(mode="after")
    def check_at_least_one_set(self):
        if not any(getattr(self, field) is not None for field in self.model_fields_set):
            raise ValueError("You must specify at least one field to update.")
        return self

    @field_validator("module_name", "class_name", "device_id")
    @classmethod
    def not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("The value cannot be empty")
        return v

    model_config = {
        "extra": "forbid",  # forbid unknown fields
        "str_strip_whitespace": True,
    }
