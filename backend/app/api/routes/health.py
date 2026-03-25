from fastapi import APIRouter
from datetime import datetime, timezone
from app.models.schemas import HealthResponse
from app.services.hotpoints_engine import get_latest_hotpoints

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    latest = get_latest_hotpoints()
    return HealthResponse(
        status="ok",
        generated_at=datetime.now(timezone.utc),
        hotpoints_count=len(latest.nodes) if latest else 0,
    )
