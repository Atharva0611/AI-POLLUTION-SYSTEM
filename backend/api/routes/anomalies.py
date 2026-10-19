from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RESULTS_FILE = PROJECT_ROOT / "data" / "processed" / "pune_anomaly_results.csv"


@router.get("/")
def get_anomalies(limit: int = Query(default=100, ge=1, le=1000)):
    """Return historical Isolation Forest anomalies, not live detections."""
    if not RESULTS_FILE.exists():
        raise HTTPException(status_code=503, detail="Saved anomaly results are unavailable.")

    try:
        df = pd.read_csv(RESULTS_FILE)
        required = {"station_name", "timestamp", "pm25", "anomaly_score", "is_anomaly"}
        missing = required.difference(df.columns)
        if missing:
            raise HTTPException(
                status_code=503,
                detail=f"Anomaly results are missing columns: {sorted(missing)}",
            )

        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)

        # This timestamp represents the full dataset, not only anomalous rows.
        latest_timestamp = df["timestamp"].max()

        labels = (
            df["is_anomaly"].astype(str).str.strip().str.lower()
            .map({"true": True, "false": False, "1": True, "0": False})
        )
        df = df.loc[labels == True].copy()
        df["pm25"] = pd.to_numeric(df["pm25"], errors="coerce")
        df["anomaly_score"] = pd.to_numeric(df["anomaly_score"], errors="coerce")
        df = df.dropna(subset=["timestamp", "anomaly_score"])
        df = df.sort_values("anomaly_score", ascending=True)

        records = df.head(limit).copy()
        records["timestamp"] = records["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        records = records[["station_name", "timestamp", "pm25", "anomaly_score"]]
        records = records.astype(object).where(pd.notna(records), None)

        return {
            "status": "ok",
            "message": "Historical Isolation Forest anomalies. These are not live pollution readings.",
            "source": "data/processed/pune_anomaly_results.csv",
            "latest_observation": (
                latest_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
                if pd.notna(latest_timestamp) else None
            ),
            "total_anomalies": int(len(df)),
            "returned": int(len(records)),
            "limit": limit,
            "anomalies": records.to_dict(orient="records"),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Anomaly retrieval failed: {exc}") from exc
