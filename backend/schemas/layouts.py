from typing import List, Dict, Any

from pydantic import BaseModel


class LayoutSchema(BaseModel):
    layout: List[Dict[str, Any]]
