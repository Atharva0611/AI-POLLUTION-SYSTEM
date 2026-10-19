"""
Forecast API Route
==================
Provides endpoints for:
- Universal PM2.5 forecasting supporting arbitrary locations or coordinates across India
- Dynamic Case A (direct station), Case B (spatial IDW estimate), Case C (insufficient data)
- Transparent reporting of contributing stations, distances, observation timestamps, and SHAP explainability
- Spatial validation metrics and coverage reports
"""

from backend.ml.forecasting.universal_forecast import universal_forecast
from typing import Optional
from fastapi import APIRouter, Query

from backend.services.forecast_service import get_canonical_forecast
from backend.services.india_environment import get_environment_for_user
from backend.services.station_registry import discover_cpcb_stations, get_station_registry

router = APIRouter()


@router.get("/universal")
def get_universal_forecast(
    location: str = Query(default="Pune", description="City, locality, town, or place name"),
    lat: Optional[float] = Query(default=None, description="Optional latitude coordinate"),
    lon: Optional[float] = Query(default=None, description="Optional longitude coordinate"),
    direct_threshold_km: float = Query(default=3.0, description="Radius for Case A direct station match"),
    max_radius_km: float = Query(default=50.0, description="Radius for Case B spatial estimation"),
):
    """
    Get a location-independent PM2.5 forecast for any user-selected location in India.
    Dynamically applies Case A, Case B, or Case C via the canonical forecasting service.
    """
    try:
        # Fetch current live weather to update meteorological inputs if available
        live_env = None
        try:
            live_env = get_environment_for_user(location)
        except Exception:
            pass

        current_weather = live_env.get("current") if live_env else None

        result = get_canonical_forecast(
            location_input=location,
            latitude=lat,
            longitude=lon,
            live_weather=current_weather,
            direct_threshold_km=direct_threshold_km,
            max_radius_km=max_radius_km,
        )

        # Use provider PM2.5 only when the canonical forecast is unavailable.
        if not isinstance(result, dict):
            result = {"forecast_available": False, "reason": "Invalid canonical forecast response."}

        canonical_available = (
            result.get("forecast_available") is True
            and result.get("predicted_pm25") is not None
        )
        provider_fallback = None if canonical_available else _phase3_provider_pm25_fallback(live_env)

        if provider_fallback is not None:
            result["predicted_pm25"] = provider_fallback["pm25"]
            result["forecast_available"] = True
            result["forecast_method"] = "environment_provider"
            result["forecast_method_label"] = "Provider PM2.5 estimate (not custom XGBoost)"
            result["prediction_source"] = provider_fallback["source"]
            result["prediction_type"] = provider_fallback["prediction_type"]
            result["model_generated"] = False
            result["fallback_used"] = True
            result["canonical_forecast_reason"] = result.get("reason")
            result["reason"] = "Canonical forecast unavailable; returning provider hourly PM2.5 estimate."
        elif not canonical_available:
            result["forecast_available"] = False
            result["model_generated"] = False
            result["fallback_used"] = False
            result.setdefault("reason", "No valid canonical forecast or provider PM2.5 estimate is available.")

        if live_env and live_env.get("forecast_24_hours"):
            result["hourly_context"] = live_env["forecast_24_hours"]

        return {"status": "success", "requested_location": location, **result}
    except Exception as exc:
        return {
            "status": "error",
            "message": str(exc),
            "requested_location": location,
        }


@router.get("/pm25")
def legacy_forecast_pm25(
    location: str = Query(default="Pune", description="Location name")
):
    """
    Maintained for backwards compatibility. Uses universal_forecast internally.
    """
    try:
        res = universal_forecast(location)
        env = get_environment_for_user(location)
        return {
            "location": location,
            "case": res["case"],
            "pm25_next_1h": res.get("predicted_pm25"),
            "label": res.get("forecast_method_label", "Unavailable"),
            "source": res.get("forecast_method"),
            "hourly": env.get("forecast_24_hours", []),
            "contributing_stations": res.get("contributing_stations", []),
            "shap": res.get("shap_explanation"),
            "forecast_available": res.get("forecast_available", False),
            "reason": res.get("reason"),
        }
    except Exception as exc:
        return {
            "status": "error",
            "message": str(exc),
            "location": location,
        }


@router.get("/stations")
def list_cpcb_stations(
    lat: Optional[float] = Query(default=None, description="Optional target latitude to calculate distances"),
    lon: Optional[float] = Query(default=None, description="Optional target longitude to calculate distances"),
    max_radius_km: float = Query(default=50.0, description="Max search radius"),
):
    """
    List all verified CPCB monitoring stations in the registry and optionally rank them by distance.
    """
    registry = get_station_registry()
    if lat is not None and lon is not None:
        audit = discover_cpcb_stations(lat, lon, max_radius_km=max_radius_km)
        return {
            "status": "success",
            "target": {"latitude": lat, "longitude": lon},
            "discovery": audit,
        }
    return {
        "status": "success",
        "station_count": len(registry),
        "stations": registry,
    }


@router.get("/validation-report")
def get_validation_report():
    """
    Return the spatial and temporal holdout validation report.
    """
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]
    report_file = root / "data" / "processed" / "spatial_validation_report.json"
    if report_file.exists():
        with open(report_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "status": "pending",
        "message": "Spatial validation report has not been generated yet. Run backend.evaluation.spatial_validation.",
    }
# ORIVA_PHASE3_PROVIDER_FALLBACK_HELPER
def _phase3_provider_pm25_fallback(environment):
    """Extract a provider hourly PM2.5 estimate without mislabelling it."""
    if not isinstance(environment, dict):
        return None

    hours = environment.get("forecast_24_hours")
    if isinstance(hours, list):
        for hour in hours:
            if not isinstance(hour, dict):
                continue
            for key in ("pm2_5_estimate", "pm25_estimate", "pm2_5", "pm25"):
                value = hour.get(key)
                if (
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and 0 <= value < float("inf")
                ):
                    return {
                        "pm25": float(value),
                        "source": "environment_provider",
                        "prediction_type": "provider_estimate",
                        "model_generated": False,
                    }
    return None
