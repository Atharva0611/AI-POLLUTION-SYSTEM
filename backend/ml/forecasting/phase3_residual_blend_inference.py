from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DATA_PATH = ROOT / "data" / "processed" / "pune_cpcb_all_stations_hourly.csv"
CANDIDATE_DIR = ROOT / "models" / "forecasting" / "phase3_residual_blend_candidate"
CANDIDATE_SOURCE = ROOT / "backend" / "ml" / "forecasting" / "pune_multistation_xgboost.phase3_candidate.py"

_MAX_OBSERVATION_AGE_HOURS = 72
_MODEL = None
_FEATURES = None
_MEDIANS = None
_STATIONS = None
_WEIGHTS = None
_CANDIDATE = None


def _load_candidate_module():
    global _CANDIDATE
    if _CANDIDATE is not None:
        return _CANDIDATE

    if not CANDIDATE_SOURCE.exists():
        raise FileNotFoundError(f"Candidate feature module missing: {CANDIDATE_SOURCE}")

    spec = importlib.util.spec_from_file_location(
        "oriva_phase3_feature_candidate", CANDIDATE_SOURCE
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load candidate feature module")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _CANDIDATE = module
    return module


def _load_artifacts():
    global _MODEL, _FEATURES, _MEDIANS, _STATIONS, _WEIGHTS

    paths = {
        "residual model": CANDIDATE_DIR / "residual_model.pkl",
        "features": CANDIDATE_DIR / "features.pkl",
        "medians": CANDIDATE_DIR / "medians.pkl",
        "stations": CANDIDATE_DIR / "stations.pkl",
        "station weights": CANDIDATE_DIR / "station_weights.pkl",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Phase 3 candidate artifacts missing: " + ", ".join(missing)
        )

    if _MODEL is None:
        _MODEL = joblib.load(paths["residual model"])
        _FEATURES = list(joblib.load(paths["features"]))
        _MEDIANS = joblib.load(paths["medians"])
        _STATIONS = list(joblib.load(paths["stations"]))
        _WEIGHTS = joblib.load(paths["station weights"])

        if not _FEATURES or "pm25" not in _FEATURES:
            raise ValueError("Candidate feature schema is invalid: pm25 is required")
        if not isinstance(_WEIGHTS, dict):
            raise ValueError("Candidate station weights must be a dictionary")

        expected = getattr(_MODEL, "n_features_in_", len(_FEATURES))
        if int(expected) != len(_FEATURES):
            raise ValueError(
                f"Feature mismatch: model expects {expected}, "
                f"candidate schema has {len(_FEATURES)}"
            )

    return _MODEL, _FEATURES, _MEDIANS, _STATIONS, _WEIGHTS


def predict_station(
    station_name: str,
    live_weather: dict[str, Any] | None = None,
    max_observation_age_hours: float = _MAX_OBSERVATION_AGE_HOURS,
) -> dict[str, Any]:
    """Predict next-hour PM2.5 using the isolated residual-blend candidate.

    Stations without a learned weight use weight=0 (persistence).
    This function does not load or modify production model artifacts.
    """
    try:
        model, features, medians, stations, weights = _load_artifacts()
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        return {"available": False, "reason": f"Phase 3 candidate unavailable: {exc}"}

    station_match = next(
        (
            str(name) for name in stations
            if str(name).strip().casefold() == str(station_name).strip().casefold()
        ),
        None,
    )
    if station_match is None:
        return {
            "available": False,
            "reason": f"Station '{station_name}' is not in the candidate training stations.",
        }

    if not DATA_PATH.is_file():
        return {"available": False, "reason": "Historical CPCB dataset is missing."}

    try:
        raw = pd.read_csv(DATA_PATH, low_memory=False)
        data, generated_features, _ = _load_candidate_module().make_features(
            raw, training=False
        )
    except Exception as exc:
        return {"available": False, "reason": f"Feature generation failed: {exc}"}

    if data.empty or "station_name" not in data or "timestamp" not in data:
        return {"available": False, "reason": "No usable station feature rows were generated."}

    station_rows = data[
        data["station_name"].astype(str).str.strip().str.casefold()
        == station_match.casefold()
    ].copy()
    if station_rows.empty:
        return {"available": False, "reason": f"No feature rows found for '{station_match}'."}

    station_rows["timestamp"] = pd.to_datetime(
        station_rows["timestamp"], utc=True, errors="coerce"
    )
    station_rows = station_rows.dropna(subset=["timestamp"]).sort_values("timestamp")
    if station_rows.empty:
        return {"available": False, "reason": "Station timestamps are invalid."}

    row = station_rows.iloc[-1].copy()
    observed_time = row["timestamp"]
    now = pd.Timestamp.now(tz="UTC")
    age_hours = (now - observed_time).total_seconds() / 3600.0

    if age_hours < -1:
        return {"available": False, "reason": "Latest station observation is in the future."}
    if age_hours > float(max_observation_age_hours):
        return {
            "available": False,
            "reason": (
                f"Latest CPCB observation is {age_hours:.1f} hours old; "
                f"limit is {max_observation_age_hours} hours."
            ),
            "timestamp_used": observed_time.isoformat(),
        }

    current = pd.to_numeric(pd.Series([row.get("pm25")]), errors="coerce").iloc[0]
    if pd.isna(current) or not np.isfinite(float(current)) or float(current) < 0:
        return {"available": False, "reason": "Current PM2.5 observation is missing or invalid."}
    current = float(current)

    weather_aliases = {
        "temperature": ("temperature", "temp_c", "temp"),
        "humidity": ("humidity",),
        "pressure": ("pressure", "pressure_mb", "pressure_hpa"),
        "wind_speed": ("wind_speed", "wind_kph", "wind_mps"),
        "rainfall": ("rainfall", "precip_mm", "precipitation"),
    }
    if isinstance(live_weather, dict):
        for feature, aliases in weather_aliases.items():
            for key in aliases:
                if live_weather.get(key) is not None:
                    try:
                        value = float(live_weather[key])
                        if np.isfinite(value):
                            row[feature] = value
                            break
                    except (TypeError, ValueError):
                        continue

    # Use the exact saved feature schema. Do not substitute production features.
    x = pd.DataFrame(
        [{feature: row.get(feature, np.nan) for feature in features}],
        columns=features,
    )
    x = x.replace([np.inf, -np.inf], np.nan)
    x = x.fillna(pd.Series(medians)).fillna(0.0)

    try:
        residual = float(model.predict(x)[0])
    except Exception as exc:
        return {"available": False, "reason": f"Residual model prediction failed: {exc}"}

    if not np.isfinite(residual):
        return {"available": False, "reason": "Residual model returned a non-finite value."}

    weight = float(weights.get(station_match, 0.0))
    if not np.isfinite(weight) or not 0.0 <= weight <= 1.0:
        return {"available": False, "reason": "Saved station blend weight is invalid."}

    unblended = max(0.0, current + residual)
    prediction = max(0.0, (1.0 - weight) * current + weight * unblended)

    return {
        "available": True,
        "source": "Phase 3 residual station blend candidate",
        "station": station_match,
        "predicted_pm25_next_1h": round(float(prediction), 3),
        "current_pm25": round(current, 3),
        "predicted_residual": round(residual, 3),
        "blend_weight": weight,
        "fallback": "persistence" if weight == 0.0 else None,
        "timestamp_used": observed_time.isoformat(),
        "observation_age_hours": round(age_hours, 2),
        "production_model_promoted": False,
    }
