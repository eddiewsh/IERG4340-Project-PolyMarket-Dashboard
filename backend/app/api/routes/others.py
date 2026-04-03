from datetime import datetime, timezone

from fastapi import APIRouter

from app.models.schemas import OthersResponse
from app.services.fmp_others import build_others

router = APIRouter()


@router.get("/others", response_model=OthersResponse)
async def get_others():
    now = datetime.now(timezone.utc)
    payload = await build_others()
    return OthersResponse(generated_at=now, **payload)
