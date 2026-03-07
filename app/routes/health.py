"""Health endpoints."""

import logging

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.schemas import ApiResponse, HealthData

router = APIRouter(prefix="/health", tags=["health"])
logger = logging.getLogger(__name__)


@router.get("", response_model=ApiResponse[HealthData])
async def health_check() -> ApiResponse[HealthData]:
    """Return service health and runtime metadata."""
    settings = get_settings()
    try:
        payload = HealthData.build(
            app_name=settings.app_name,
            environment=settings.app_env,
        )
        return ApiResponse[HealthData](success=True, data=payload, error=None)
    except Exception as exc:
        logger.exception("Health check failed: %s", exc)
        raise HTTPException(status_code=500, detail="Health check failed") from exc
