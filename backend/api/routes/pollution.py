# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Query

from backend.services.india_environment import get_environment_for_user

router = APIRouter()


@router.get("/current")
def get_current_pollution(
    location: str = Query(default="Pune", description="Location name (e.g. Pune, Alandi)")
):
    """Get current pollution and weather data for a location."""
    try:
        result = get_environment_for_user(location)
        return result
    except Exception as exc:
        return {
            "status": "error",
            "message": str(exc),
            "location": location,
        }
