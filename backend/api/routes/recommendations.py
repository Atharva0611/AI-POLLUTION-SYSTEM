# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Query

from backend.services.india_environment import get_environment_for_user

router = APIRouter()


@router.get("/")
def get_recommendations(
    location: str = Query(default="Pune", description="Location name")
):
    """Get current pollution control recommendations for a location."""
    try:
        env = get_environment_for_user(location)
        return {
            "location": location,
            "recommendations": env.get("recommendations", []),
            "policy_actions": env.get("policy", []),
        }
    except Exception as exc:
        return {
            "status": "error",
            "message": str(exc),
            "location": location,
        }
