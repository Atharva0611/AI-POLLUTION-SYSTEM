from backend.services.live_aqi_service import (
    get_live_air_quality
)


def live_aqi_agent(
    question
):
    """
    Existing live air-quality service wrapper.
    """

    try:

        result = get_live_air_quality(
            question
        )

        return {
            "available": True,
            "data": result
        }

    except Exception as exc:

        return {
            "available": False,
            "error": str(exc)
        }
