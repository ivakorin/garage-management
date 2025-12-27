from fastapi import APIRouter

from api.api_v1.endpoints.layouts import router as layouts_router
from api.api_v1.endpoints.plugins import router as plugin_router
from api.api_v1.endpoints.sensors import router as sensors_router
from api.api_v1.endpoints.websocket import router as websocket_router
from core.settings import settings

router = APIRouter(prefix=settings.api.prefix)

router.include_router(layouts_router)
router.include_router(plugin_router)
router.include_router(sensors_router)
router.include_router(websocket_router)
