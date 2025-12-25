from typing import Any, Dict, Optional

from pydantic import BaseModel


class SensorMessage(BaseModel):
    device_id: str
    timestamp: str
    data: Dict[str, Any]
    value: Optional[float] = None