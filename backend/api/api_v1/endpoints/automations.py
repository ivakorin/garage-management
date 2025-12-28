from fastapi import APIRouter, HTTPException

from schemas.automations import Automation
from utils.automations import AutomationEngine

router = APIRouter(prefix="/automations", tags=["automations"])
engine = AutomationEngine([])


@router.get("/automations")
def list_automations():
    return list(engine.automations.values())


@router.post("/automations")
def create_automation(automation: Automation):
    engine.automations[automation.id] = automation
    return {"status": "created"}


@router.put("/automations/{id}/enable")
def enable_automation(id: str):
    if id not in engine.automations:
        raise HTTPException(404)
    engine.automations[id].enabled = True
    return {"status": "enabled"}


@router.put("/automations/{id}/disable")
def disable_automation(id: str):
    if id not in engine.automations:
        raise HTTPException(404)
    engine.automations[id].enabled = False
    return {"status": "disabled"}
