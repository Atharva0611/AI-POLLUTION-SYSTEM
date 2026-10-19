"""Read-only API for the supplied OGD Pune/Pimpri-Chinchwad snapshot.

This serves a single downloaded snapshot; it does not fetch live data or
create a historical time series. Keep forecast freshness checks separate.
"""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/current-snapshot", tags=["Current pollution snapshot"])
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "pune_pcmc_station_summary.csv"
IST = ZoneInfo("Asia/Kolkata")


@router.get("")
def get_current_snapshot(city: str = Query(default="all", description="Pune, Pimpri-Chinchwad, or all")):
    if not DATA_PATH.exists():
        raise HTTPException(status_code=503, detail="Current snapshot CSV is missing")

    try:
        df = pd.read_csv(DATA_PATH)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not read current snapshot CSV") from exc

    allowed = {"pune": "Pune", "pimpri-chinchwad": "Pimpri-Chinchwad", "all": "all"}
    normalized = city.strip().casefold()
    if normalized not in allowed:
        raise HTTPException(status_code=400, detail="city must be Pune, Pimpri-Chinchwad, or all")
    selected = allowed[normalized]
    if selected != "all":
        df = df[df["city"] == selected]

    if df.empty:
        return {"status": "ok", "source": "OGD snapshot CSV", "count": 0, "stations": []}

    timestamps = pd.to_datetime(df["observation_time_ist"], errors="coerce")
    valid = timestamps.dropna()
    latest = valid.max() if not valid.empty else None
    now = datetime.now(IST).replace(tzinfo=None)
    age_hours = (now - latest).total_seconds() / 3600 if latest is not None else None
    fresh = age_hours is not None and 0 <= age_hours <= 72

    stations = []
    for row in df.where(pd.notna(df), None).to_dict(orient="records"):
        stations.append({
            "city": row.get("city"),
            "station": row.get("station"),
            "latitude": row.get("latitude"),
            "longitude": row.get("longitude"),
            "observation_time_ist": row.get("observation_time_ist"),
            "pm25": row.get("pm25"),
            "pm10": row.get("pm10"),
            "data_type": row.get("data_type"),
        })

    return {
        "status": "ok",
        "source": "data.gov.in OGD snapshot supplied by user",
        "observation_timezone": "Asia/Kolkata",
        "latest_observation_ist": latest.isoformat(sep=" ") if latest is not None else None,
        "observation_age_hours": round(age_hours, 2) if age_hours is not None else None,
        "fresh_within_72_hours": fresh,
        "warning": "This is a snapshot from a supplied CSV, not an automatically refreshed live feed. Missing pollutant values remain null.",
        "count": len(stations),
        "stations": stations,
    }
