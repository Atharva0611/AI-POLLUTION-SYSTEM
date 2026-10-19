"""
Universal Location-Independent Forecasting Engine
================================================
Supports ANY user-selected location in India.
Integrates:
- Universal Location Resolver (GPS coordinates, text search, geocoding)
- CPCB Station Registry (Haversine distance, freshness, data quality)
- Dynamic 3-Case Strategy:
  - CASE A: Direct CPCB Station Forecast (<= 3 km)
  - CASE B: Spatially Estimated Forecast (Inverse Distance Weighting across eligible stations within search radius)
  - CASE C: Insufficient Data (> 50 km) - Suppresses numerical forecast with clear explanation
- Multi-station XGBoost with SHAP TreeExplainer feature attributions
- Zero target leakage; preserves requested location independently.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
import joblib

from backend.services.universal_location_resolver import resolve_universal_location
from backend.services.station_registry import discover_cpcb_stations, get_station_registry
from backend.services.shap_service import explain_xgboost_prediction

ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = ROOT / "models" / "forecasting" / "pune_multistation_xgboost.pkl"
FEATURES_PATH = ROOT / "models" / "forecasting" / "pune_multistation_features.pkl"
MEDIANS_PATH = ROOT / "models" / "forecasting" / "pune_multistation_medians.pkl"
STATIONS_PATH = ROOT / "models" / "forecasting" / "pune_multistation_stations.pkl"
CACHE_PATH = ROOT / "data" / "processed" / "pune_multistation_latest_rows.pkl"
DATA_PATH = ROOT / "data" / "processed" / "pune_cpcb_all_stations_hourly.csv"

_MODEL = None
_FEATURES = None
_MEDIANS = None
_STATIONS = None
_LATEST_ROWS_CACHE = None


def _load_artifacts():
    global _MODEL, _FEATURES, _MEDIANS, _STATIONS, _LATEST_ROWS_CACHE

    if _MODEL is None and MODEL_PATH.exists():
        _MODEL = joblib.load(MODEL_PATH)
    if _FEATURES is None and FEATURES_PATH.exists():
        _FEATURES = joblib.load(FEATURES_PATH)
    if _MEDIANS is None and MEDIANS_PATH.exists():
        _MEDIANS = joblib.load(MEDIANS_PATH)
    if _STATIONS is None and STATIONS_PATH.exists():
        _STATIONS = joblib.load(STATIONS_PATH)
    if _LATEST_ROWS_CACHE is None and CACHE_PATH.exists():
        _LATEST_ROWS_CACHE = joblib.load(CACHE_PATH)


def _get_station_latest_row(station_full_name: str) -> Optional[pd.Series]:
    """Retrieve the latest pre-computed feature row for a given station."""
    _load_artifacts()
    if _LATEST_ROWS_CACHE is not None:
        matches = _LATEST_ROWS_CACHE[
            _LATEST_ROWS_CACHE["station_name"].astype(str).str.lower() == station_full_name.strip().lower()
        ]
        if not matches.empty:
            return matches.iloc[-1].copy()

    # Fallback to loading data_path directly if not in cache
    if DATA_PATH.exists():
        from backend.ml.forecasting.pune_multistation_xgboost import make_features
        raw = pd.read_csv(DATA_PATH, low_memory=False)
        data, _, _ = make_features(raw, training=False)
        st_data = data[data["station_name"].astype(str).str.lower() == station_full_name.strip().lower()]
        if not st_data.empty:
            return st_data.iloc[-1].copy()
    return None


def predict_for_single_station(station_full_name: str, live_weather: Optional[dict] = None) -> Dict[str, Any]:
    """
    Run XGBoost prediction for a specific CPCB station using its latest historical data.
    """
    _load_artifacts()
    if _MODEL is None or _FEATURES is None:
        return {"success": False, "error": "XGBoost model artifacts not loaded"}

    row = _get_station_latest_row(station_full_name)
    if row is None:
        return {"success": False, "error": f"No historical records found for station '{station_full_name}'"}

    # Update meteorological inputs if live weather report is provided
    if live_weather:
        weather_map = {
            "temperature": ["temperature", "temp_c", "temp"],
            "humidity": ["humidity"],
            "pressure": ["pressure", "pressure_mb", "pressure_hpa"],
            "wind_speed": ["wind_speed", "wind_kph", "wind_mps"],
            "rainfall": ["rainfall", "precip_mm", "precipitation"],
        }
        for feat, keys in weather_map.items():
            for k in keys:
                if k in live_weather and live_weather[k] is not None:
                    try:
                        row[feat] = float(live_weather[k])
                        break
                    except (ValueError, TypeError):
                        pass

    # Build one-hot station features
    for feat in _FEATURES:
        if feat.startswith("station_"):
            row[feat] = 1.0 if feat == f"station_{station_full_name}" else 0.0

    # Build one-row feature DataFrame
    feat_dict = {f: row.get(f, np.nan) for f in _FEATURES}
    X = pd.DataFrame([feat_dict], columns=_FEATURES)
    if _MEDIANS is not None:
        X = X.fillna(pd.Series(_MEDIANS)).fillna(0.0)
    else:
        X = X.fillna(0.0)

    # Predict PM2.5
    raw_pred = float(_MODEL.predict(X)[0])
    pred_pm25 = max(1.0, round(raw_pred, 2))

    # Compute SHAP explanation on this exact row and model
    try:
        shap_res = explain_xgboost_prediction(_MODEL, X)
    except Exception as exc:
        shap_res = {"available": False, "error": str(exc), "features": [], "expected_value": None}

    return {
        "success": True,
        "station_name": station_full_name,
        "predicted_pm25": pred_pm25,
        "timestamp_used": str(row.get("timestamp", "")),
        "observed_pm25_latest": float(row.get("pm25", 0.0)) if pd.notna(row.get("pm25")) else None,
        "feature_row": X,
        "shap": shap_res,
    }


def universal_forecast(
    location_input: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    live_weather: Optional[dict] = None,
    direct_threshold_km: float = 3.0,
    max_radius_km: float = 50.0,
) -> Dict[str, Any]:
    """
    Produce a location-independent PM2.5 forecast for ANY user location across India.

    3-Case Strategy:
    CASE A: Direct Station Forecast (distance <= 3 km)
    CASE B: Spatially Estimated Forecast (IDW combination across eligible stations within search radius)
    CASE C: Insufficient Data (> 50 km) - Suppresses forecast with transparent explanation.
    """
    _load_artifacts()

    # 1. Resolve universal location coordinates independently
    loc_meta = resolve_universal_location(location_input, latitude=latitude, longitude=longitude)
    target_lat = loc_meta["latitude"]
    target_lon = loc_meta["longitude"]

    # 2. Discover CPCB stations dynamically (Haversine distance, freshness, data quality)
    discovery = discover_cpcb_stations(
        target_lat,
        target_lon,
        max_radius_km=max_radius_km,
        direct_threshold_km=direct_threshold_km,
    )

    case = discovery["case"]
    case_desc = discovery["case_description"]

    base_response = {
        "requested_location": location_input,
        "resolved_location": loc_meta["display_name"],
        "coordinates": {"latitude": target_lat, "longitude": target_lon},
        "location_metadata": loc_meta,
        "case": case,
        "case_description": case_desc,
        "horizon": "next_1_hour",
        "unit": "µg/m³",
        "model": "Multi-Station XGBoost Regressor",
    }

    # =========================================================================
    # CASE C: Insufficient Data (> 50 km)
    # =========================================================================
    if case == "CASE_C":
        nearest_outside = discovery.get("nearest_station_outside_radius")
        outside_dist_str = f"{nearest_outside['distance_km']:.1f} km" if nearest_outside else "N/A"
        outside_name = nearest_outside['clean_name'] if nearest_outside else "N/A"

        return {
            **base_response,
            "forecast_available": False,
            "predicted_pm25": None,
            "forecast_method": "INSUFFICIENT_DATA_SUPPRESSED",
            "reason": discovery.get("message") or (
                f"No verified CPCB monitoring station exists within the {max_radius_km} km search radius. "
                f"The nearest available station is '{outside_name}' at {outside_dist_str}. "
                "A numerical forecast is suppressed to prevent misleading extrapolation."
            ),
            "nearest_available_station": nearest_outside,
            "contributing_stations": [],
            "shap_explanation": None,
            "uncertainty_warning": (
                "Ground-level pollutant dispersion is highly localized. Without a monitoring "
                "station within 50 km, numerical forecast confidence is insufficient."
            ),
        }

    # =========================================================================
    # CASE A: Direct Station Forecast (distance <= 3 km)
    # =========================================================================
    if case == "CASE_A":
        primary = discovery["primary_station"]
        st_pred = predict_for_single_station(primary["station_name"], live_weather=live_weather)

        if not st_pred["success"]:
            return {
                **base_response,
                "forecast_available": False,
                "predicted_pm25": None,
                "forecast_method": "DIRECT_STATION_FORECAST",
                "reason": st_pred.get("error", "Error predicting for direct station"),
                "contributing_stations": [primary],
                "shap_explanation": None,
            }

        return {
            **base_response,
            "forecast_available": True,
            "predicted_pm25": st_pred["predicted_pm25"],
            "forecast_method": "DIRECT_STATION_FORECAST",
            "forecast_method_label": "Direct CPCB Station Forecast",
            "is_spatial_estimate": False,
            "primary_station": primary,
            "contributing_stations": [{
                "station_name": primary["station_name"],
                "clean_name": primary["clean_name"],
                "station_id": primary["station_id"],
                "distance_km": primary["distance_km"],
                "weight": 1.0,
                "latest_observation": primary["latest_timestamp"],
                "observed_pm25": st_pred.get("observed_pm25_latest"),
                "predicted_pm25": st_pred["predicted_pm25"],
            }],
            "shap_explanation": st_pred.get("shap"),
            "data_quality_score": primary.get("data_quality_score"),
            "uncertainty_warning": None,
        }

    # =========================================================================
    # CASE B: Spatially Estimated Forecast (IDW across stations within radius)
    # =========================================================================
    eligible = discovery.get("eligible_stations", [])
    if not eligible:
        return {
            **base_response,
            "forecast_available": False,
            "predicted_pm25": None,
            "forecast_method": "SPATIAL_ESTIMATE_FAILED",
            "reason": "No eligible stations could be processed for spatial estimation.",
        }

    weighted_predictions = []
    contributing_info = []
    total_weight = 0.0
    primary_shap = None

    for st in eligible:
        st_res = predict_for_single_station(st["station_name"], live_weather=live_weather)
        if st_res["success"]:
            w = st.get("spatial_weight", 0.0)
            weighted_predictions.append(st_res["predicted_pm25"] * w)
            total_weight += w

            contributing_info.append({
                "station_name": st["station_name"],
                "clean_name": st["clean_name"],
                "station_id": st["station_id"],
                "distance_km": st["distance_km"],
                "weight": w,
                "latest_observation": st["latest_timestamp"],
                "observed_pm25": st_res.get("observed_pm25_latest"),
                "predicted_pm25": st_res["predicted_pm25"],
            })

            # Capture SHAP from the closest contributing station as reference
            if primary_shap is None and st_res.get("shap") and st_res["shap"].get("available"):
                primary_shap = st_res["shap"]

    if not weighted_predictions or total_weight <= 0:
        return {
            **base_response,
            "forecast_available": False,
            "predicted_pm25": None,
            "forecast_method": "SPATIAL_ESTIMATION_ERROR",
            "reason": "Could not compute weighted spatial estimate from eligible stations.",
        }

    # Normalize by actual weight sum if subset succeeded
    final_pm25 = round(sum(weighted_predictions) / total_weight, 2)

    return {
        **base_response,
        "forecast_available": True,
        "predicted_pm25": final_pm25,
        "forecast_method": "SPATIALLY_ESTIMATED_FORECAST",
        "forecast_method_label": "Spatially Estimated Forecast (Inverse Distance Weighted)",
        "is_spatial_estimate": True,
        "primary_station": discovery.get("primary_station"),
        "contributing_stations": contributing_info,
        "shap_explanation": primary_shap,
        "note": (
            f"This is a spatially estimated forecast derived from {len(contributing_info)} "
            f"nearby CPCB monitoring stations within {max_radius_km} km. "
            "It is not a direct in-situ measurement."
        ),
        "uncertainty_warning": (
            f"Spatial estimate based on {len(contributing_info)} stations. "
            f"Nearest station is {discovery['primary_station']['clean_name']} ({discovery['primary_station']['distance_km']:.2f} km away)."
        ),
    }
