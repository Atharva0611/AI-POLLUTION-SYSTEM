"""Current WeatherAPI endpoint; weather values remain separate from pollution observations."""
from fastapi import APIRouter, HTTPException, Query

from backend.services.weather_service import get_current_weather

router = APIRouter()


@router.get("/current")
def current_weather(location: str = Query(default="Pune", min_length=1, max_length=120)):
    try:
        result = get_current_weather(location.strip())
        return {
            "status": "ok",
            "provider": "WeatherAPI",
            "source_type": "current_weather_observation",
            "weather": result,
        }
    except Exception as exc:
        # Do not expose provider URLs, request details, or credentials.
        raise HTTPException(
            status_code=503,
            detail="Current weather is unavailable. Check WEATHER_API_KEY and provider status.",
        ) from exc
