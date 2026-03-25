from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.models.schemas import OthersResponse
from app.services.fmp_others import build_others

router = APIRouter()


@router.get("/others", response_model=OthersResponse)
async def get_others():
    if not settings.fmp_api_key:
        raise HTTPException(500, "Missing fmp_api_key")

    payload = await build_others()
    now = datetime.now(timezone.utc)
    return OthersResponse(generated_at=now, **payload)

