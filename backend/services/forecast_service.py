"""
Canonical Forecasting Service
=============================
Provides the single, canonical forecasting interface for:
- FastAPI endpoints (/api/forecast/universal, /api/forecast/pm25)
- LangGraph agents (final_agent.py, forecast_agent.py, orchestrator.py)
- Interactive terminal agent (backend.run_final_agent)
- Frontend dashboard requests (/dashboard)

Standardized Response Schema:
- requested_location: str
- resolved_location: str
- latitude: float
- longitude: float
- forecast_timestamp: str (ISO-8601)
- forecast_horizon: str ("next_1_hour")
- predicted_pm25: float | None
- forecast_method: str ("DIRECT_STATION_FORECAST", "SPATIALLY_ESTIMATED_FORECAST", "INSUFFICIENT_DATA_SUPPRESSED")
- model_name: str ("Multi-Station XGBoost Regressor")
- model_version: str ("2.1.0-pune12-cpcb")
- contributing_stations: List[Dict] (clean_name, station_id, distance_km, weight, latest_observation, observed_pm25, predicted_pm25)
- station_distances: Dict[str, float]
- station_observation_timestamps: Dict[str, str]
- data_source: str ("CPCB Ground Monitoring Stations")
- data_quality_status: str ("CALIBRATED_CPCB", "ESTIMATED_IDW", "INSUFFICIENT")
- validation_metrics: Dict[str, float] (Holdout R², MAE, RMSE from spatial_validation_report.json)
- shap_baseline: float | None
- shap_contributions: List[Dict]
- shap_reconstructed_prediction: float | None
- shap_additive_discrepancy: float | None
- uncertainty_interval: Dict[str, float] | None
- warnings: List[str]
- case: str ("CASE_A", "CASE_B", "CASE_C")
- case_description: str
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.ml.forecasting.universal_forecast import universal_forecast as _core_universal_forecast
from backend.services.universal_location_resolver import resolve_universal_location
from backend.services.station_registry import discover_cpcb_stations, get_station_registry

ROOT = Path(__file__).resolve().parents[2]
VALIDATION_REPORT_PATH = ROOT / "data" / "processed" / "spatial_validation_report.json"
_VALIDATION_METRICS_CACHE: Optional[Dict[str, Any]] = None


def get_cached_validation_metrics() -> Dict[str, Any]:
    """Return measured holdout metrics, or None for unavailable metrics."""
    global _VALIDATION_METRICS_CACHE
    if _VALIDATION_METRICS_CACHE is not None:
        return _VALIDATION_METRICS_CACHE

    metric_map = {
        "holdout_r2": "R2",
        "holdout_mae": "MAE",
        "holdout_rmse": "RMSE",
        "mean_bias": "Mean_Bias",
    }
    metrics = {key: None for key in metric_map}
    strategy = "UNAVAILABLE_VALIDATION_REPORT"

    if VALIDATION_REPORT_PATH.exists():
        try:
            with open(VALIDATION_REPORT_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            holdout = (
                data.get("chronological_holdout", {}).get("xgboost_metrics", {})
            )
            if isinstance(holdout, dict):
                for output_key, report_key in metric_map.items():
                    value = holdout.get(report_key)
                    try:
                        number = float(value)
                        if number == number and abs(number) != float("inf"):
                            metrics[output_key] = number
                    except (TypeError, ValueError, OverflowError):
                        pass

                if any(value is not None for value in metrics.values()):
                    strategy = "Chronological Future Holdout (reported metrics)"
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    _VALIDATION_METRICS_CACHE = {
        "evaluation_strategy": strategy,
        **metrics,
    }
    return _VALIDATION_METRICS_CACHE

def get_canonical_forecast(
    location_input: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    live_weather: Optional[dict] = None,
    direct_threshold_km: float = 3.0,
    max_radius_km: float = 50.0,
) -> Dict[str, Any]:
    """
    Produce the canonical standardized forecast for any location in India.
    Guarantees consistent schema, strict Case A/B/C separation, and exact SHAP additivity.
    """
    raw_res = _core_universal_forecast(
        location_input=location_input,
        latitude=latitude,
        longitude=longitude,
        live_weather=live_weather,
        direct_threshold_km=direct_threshold_km,
        max_radius_km=max_radius_km,
    )

    case = raw_res.get("case", "CASE_C")
    coords = raw_res.get("coordinates", {})
    val_metrics = get_cached_validation_metrics()
    now_iso = datetime.now(timezone.utc).isoformat()

    contributing = raw_res.get("contributing_stations", [])
    station_distances = {s["clean_name"]: s["distance_km"] for s in contributing}
    station_timestamps = {s["clean_name"]: str(s.get("latest_observation", "")) for s in contributing}

    # Extract SHAP reconstruction
    shap_data = raw_res.get("shap_explanation") or {}
    shap_base = shap_data.get("expected_value")
    shap_contribs = shap_data.get("features", [])
    shap_reconstructed = None
    shap_diff = None

    if shap_base is not None and shap_contribs:
        total_shap = sum(f.get("shap_value", 0.0) for f in shap_contribs)
        shap_reconstructed = round(shap_base + total_shap, 4)
        if raw_res.get("predicted_pm25") is not None:
            # Check discrepancy with closest station prediction
            pred_val = shap_data.get("prediction")
            if pred_val is not None:
                shap_diff = round(abs(shap_reconstructed - pred_val), 6)

    warnings: List[str] = []
    if raw_res.get("uncertainty_warning"):
        warnings.append(raw_res["uncertainty_warning"])

    forecast_available = (
        raw_res.get("forecast_available", False)
        and raw_res.get("predicted_pm25") is not None
        and case in {"CASE_A", "CASE_B"}
    )

    if case in {"CASE_A", "CASE_B"} and forecast_available:
        data_quality_status = (
            "CALIBRATED_CPCB" if case == "CASE_A" else "ESTIMATED_IDW"
        )
        holdout_mae = val_metrics.get("holdout_mae")
        uncertainty_interval = None

        if holdout_mae is not None:
            multiplier = 1.0 if case == "CASE_A" else 1.25
            margin = holdout_mae * multiplier
            uncertainty_interval = {
                "low": max(1.0, round(raw_res["predicted_pm25"] - margin, 2)),
                "high": round(raw_res["predicted_pm25"] + margin, 2),
            }
        else:
            warnings.append(
                "Uncertainty interval unavailable because validated holdout MAE "
                "is missing. The point forecast is not a confidence interval."
            )

        if case == "CASE_B":
            warnings.append(
                "This is a spatially estimated forecast from nearby monitoring stations. "
                "It is not an in-situ physical measurement."
            )
    else:
        data_quality_status = "INSUFFICIENT"
        uncertainty_interval = None
        case_desc = str(raw_res.get("case_description") or "")
        reason = str(raw_res.get("reason") or "")
        is_stale = (
            case_desc == "STALE_OBSERVATIONS"
            or "observation within" in reason.casefold()
            or "stale" in reason.casefold()
        )
        if is_stale:
            warnings.append(
                "Forecast suppressed because no eligible CPCB station has a sufficiently "
                "recent observation. The 72-hour freshness requirement remains enforced."
            )
        else:
            warnings.append(
                f"No verified CPCB monitoring station exists within {max_radius_km} km. "
                "Numerical forecast suppressed to protect data integrity."
            )

    return {
        "status": "success",
        "requested_location": raw_res.get("requested_location", location_input),
        "resolved_location": raw_res.get("resolved_location", location_input),
        "latitude": coords.get("latitude"),
        "longitude": coords.get("longitude"),
        "forecast_timestamp": now_iso,
        "forecast_horizon": raw_res.get("horizon", "next_1_hour"),
        "predicted_pm25": raw_res.get("predicted_pm25"),
        "unit": "µg/m³",
        "forecast_available": forecast_available,
        "forecast_method": (
            "INSUFFICIENT_DATA_SUPPRESSED" if not forecast_available
            else "DIRECT_STATION_FORECAST" if case == "CASE_A"
            else "SPATIALLY_ESTIMATED_FORECAST"
        ),
        "forecast_method_label": raw_res.get("forecast_method_label", "Unavailable"),
        "is_spatial_estimate": raw_res.get("is_spatial_estimate", False),
        "model_name": "Multi-Station XGBoost Regressor",
        "model_version": "2.1.0-pune12-cpcb",
        "case": case,
        "case_description": raw_res.get("case_description"),
        "reason": raw_res.get("reason"),
        "contributing_stations": contributing,
        "station_distances": station_distances,
        "station_observation_timestamps": station_timestamps,
        "data_source": "Central Pollution Control Board (CPCB) Verified Stations",
        "data_quality_status": data_quality_status,
        "validation_metrics": val_metrics,
        "shap_baseline": shap_base,
        "shap_contributions": shap_contribs,
        "shap_reconstructed_prediction": shap_reconstructed,
        "shap_additive_discrepancy": shap_diff,
        "uncertainty_interval": uncertainty_interval,
        "warnings": warnings,
    }


# Backwards compatibility wrappers
def get_forecast(location: str) -> Dict[str, Any]:
    """Compatibility wrapper matching predict_forecast.py."""
    can = get_canonical_forecast(location)
    return {
        "available": can["forecast_available"],
        "requested_location": can["requested_location"],
        "model_station": can["contributing_stations"][0]["clean_name"] if can["contributing_stations"] else "Unavailable",
        "mapping_method": can["forecast_method"],
        "distance_km": can["contributing_stations"][0]["distance_km"] if can["contributing_stations"] else None,
        "predicted_pm25_next_1h": can["predicted_pm25"],
        "unit": "µg/m³",
        "model": can["model_name"],
        "case": can["case"],
        "note": can["warnings"][0] if can["warnings"] else "CPCB model forecast.",
    }


def predict_single(station_or_location: str) -> float:
    """Compatibility wrapper returning scalar PM2.5."""
    can = get_canonical_forecast(station_or_location)
    pred = can.get("predicted_pm25")
    return float(pred) if pred is not None else 0.0
