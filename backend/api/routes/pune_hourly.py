"""API for station-level next-hour PM2.5 forecasts."""
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.ml.forecasting.pune_hourly_forecast import predict_next_hour

router = APIRouter()


class StationHistoryRequest(BaseModel):
    observations: list[dict[str, Any]] = Field(
        ...,
        min_length=1,
        description=(
            "Actual timestamped hourly station observations. "
            "Include station_name, timestamp, pm25 and available model input columns."
        ),
    )


@router.post("/predict")
def predict_pune_hourly(request: StationHistoryRequest):
    """Predict next-hour PM2.5 from supplied recent station histories."""
    try:
        result = predict_next_hour(request.observations)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        # Keep internal exception details out of public responses.
        raise HTTPException(
            status_code=500,
            detail="Hourly forecast inference failed. Check backend logs.",
        ) from exc

    if result.get("status") == "invalid_input":
        raise HTTPException(status_code=422, detail=result.get("reason"))
    return result
