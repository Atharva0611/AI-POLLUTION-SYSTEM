"""Pune CPCB next-hour PM2.5 inference service.

Historical dataset rows are never treated as current observations.
Input rows must contain recent, timestamped station measurements.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
MODEL_DIR = ROOT / "models" / "forecasting" / "pune_pm25_24h_candidate"
MAX_OBSERVATION_AGE_HOURS = 72

BASE_COLUMNS = [
    "pm25", "pm10", "no2", "so2", "co", "o3", "nh3",
    "temperature", "humidity", "pressure", "wind_speed",
    "wind_direction", "rainfall",
]
LAGS = [1, 2, 3, 6, 12, 24, 48, 72]


def _load_artifacts():
    required = [
        MODEL_DIR / "feature_columns.joblib",
        MODEL_DIR / "stations.joblib",
        MODEL_DIR / "xgb_pm25_h01.joblib",
        MODEL_DIR / "medians_h01.joblib",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError("Missing forecast artifacts: " + ", ".join(missing))
    return (
        list(joblib.load(required[0])),
        list(joblib.load(required[1])),
        joblib.load(required[2]),
        joblib.load(required[3]),
    )


def predict_next_hour(observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Predict from supplied recent station histories.

    Each station must supply timestamped history sufficient to construct
    the trained lag features. Timestamps must represent actual observations.
    """
    if not observations:
        return {
            "status": "unavailable",
            "reason": "No current station observations were supplied.",
            "forecasts": [],
        }

    feature_columns, stations, model, medians = _load_artifacts()
    df = pd.DataFrame(observations)

    required = {"station_name", "timestamp", "pm25"}
    if not required.issubset(df.columns):
        return {
            "status": "invalid_input",
            "reason": f"Required fields: {sorted(required)}",
            "forecasts": [],
        }

    df["station_name"] = df["station_name"].astype("string").str.strip()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    for col in df.columns:
        if col not in ("station_name", "timestamp"):
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["station_name", "timestamp"])
    df = df.sort_values(["station_name", "timestamp"]).reset_index(drop=True)

    if df.duplicated(["station_name", "timestamp"]).any():
        return {
            "status": "invalid_input",
            "reason": "Duplicate station/timestamp observations were supplied.",
            "forecasts": [],
        }

    now = pd.Timestamp.now(tz="UTC")
    latest = df.groupby("station_name", sort=False).tail(1).copy()
    age_hours = (now - latest["timestamp"]).dt.total_seconds() / 3600

    # Do not return predictions for stale, future-dated, or missing PM2.5.
    valid = (
        age_hours.ge(0)
        & age_hours.le(MAX_OBSERVATION_AGE_HOURS)
        & latest["pm25"].notna()
    )
    latest = latest.loc[valid].copy()

    if latest.empty:
        return {
            "status": "unavailable",
            "reason": "No station has a valid PM2.5 observation within the freshness window.",
            "max_observation_age_hours": MAX_OBSERVATION_AGE_HOURS,
            "forecasts": [],
        }

    # Build lag features using supplied station histories, not one isolated row.
    valid_stations = set(latest["station_name"].astype(str))
    history = df[df["station_name"].astype(str).isin(valid_stations)].copy()
    base_columns = [c for c in BASE_COLUMNS if c in history.columns]

    for col in base_columns:
        for lag in LAGS:
            history[f"{col}_lag_{lag}h"] = (
                history.groupby("station_name", sort=False)[col].shift(lag)
            )

    # Use each station's most recent history row after feature construction.
    latest = history.groupby("station_name", sort=False).tail(1).copy()
    target_time = latest["timestamp"] + pd.Timedelta(hours=1)
    latest["hour"] = target_time.dt.hour
    latest["day_of_week"] = target_time.dt.dayofweek
    latest["month"] = target_time.dt.month
    latest["day_of_year"] = target_time.dt.dayofyear

    dummies = pd.get_dummies(latest["station_name"], prefix="station", dtype=float)
    latest = pd.concat([latest, dummies], axis=1)
    for col in feature_columns:
        if col not in latest.columns:
            latest[col] = 0.0

    X = latest[feature_columns].replace([np.inf, -np.inf], np.nan)
    X = X.fillna(pd.Series(medians)).fillna(0)
    predictions = np.asarray(model.predict(X), dtype=float)

    forecasts = []
    for (_, row), prediction in zip(latest.iterrows(), predictions):
        observed_at = row["timestamp"]
        age = (now - observed_at).total_seconds() / 3600
        station = str(row["station_name"])
        forecasts.append({
            "station_name": station,
            "observed_at_utc": observed_at.isoformat(),
            "forecast_for_utc": (observed_at + pd.Timedelta(hours=1)).isoformat(),
            "observation_age_hours": round(age, 2),
            "current_pm25": float(row["pm25"]),
            "predicted_pm25_next_hour": round(float(prediction), 2),
            "unit": "µg/m³",
            "source": "supplied_recent_station_observations",
            "model_horizon_hours": 1,
            "status": "forecast",
        })

    return {
        "status": "ok" if forecasts else "unavailable",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": "xgb_pm25_h01",
        "model_station_count": len(stations),
        "max_observation_age_hours": MAX_OBSERVATION_AGE_HOURS,
        "forecasts": forecasts,
        "note": (
            "Forecasts require actual recent station histories. "
            "Weather data or stale historical rows are not substituted for PM2.5."
        ),
    }
