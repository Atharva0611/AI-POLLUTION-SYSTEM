from pathlib import Path
import math
import pandas as pd
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_FILE = PROJECT_ROOT / "data" / "processed" / "pune_pcmc_station_summary.csv"


def json_safe(value):
    """Convert pandas/numpy missing or non-finite values to JSON null."""
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, float) and not math.isfinite(value):
        return None

    if hasattr(value, "item"):
        value = value.item()
        if isinstance(value, float) and not math.isfinite(value):
            return None

    return value


@router.get("/")
def get_current_snapshot(
    city: str | None = Query(default=None, description="Pune or Pimpri-Chinchwad")
):
    """Read-only station snapshot; not a live-data ingestion service."""
    if not DATA_FILE.is_file():
        raise HTTPException(status_code=503, detail="Station snapshot CSV is unavailable.")

    try:
        df = pd.read_csv(DATA_FILE)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to read the station snapshot.") from exc

    required = {
        "city", "station", "latitude", "longitude",
        "observation_time_ist", "pm10", "pm25", "data_type"
    }
    missing = required.difference(df.columns)
    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"Snapshot schema is missing required columns: {sorted(missing)}"
        )

    if city:
        normalized = city.strip().casefold()
        aliases = {
            "pune": {"pune"},
            "pcmc": {"pimpri-chinchwad", "pimpri chinchwad", "pcmc"},
            "pimpri-chinchwad": {"pimpri-chinchwad", "pimpri chinchwad", "pcmc"},
            "pimpri chinchwad": {"pimpri-chinchwad", "pimpri chinchwad", "pcmc"},
        }
        accepted = aliases.get(normalized, {normalized})
        df = df[df["city"].astype(str).str.strip().str.casefold().isin(accepted)]

    records = [
        {key: json_safe(value) for key, value in record.items()}
        for record in df.to_dict(orient="records")
    ]

    return {
        "status": "ok",
        "data_type": "snapshot",
        "message": (
            "Snapshot data only. Check observation_time_ist before interpreting "
            "values as current conditions."
        ),
        "count": len(records),
        "city_filter": city,
        "source_file": "data/processed/pune_pcmc_station_summary.csv",
        "stations": records,
    }
