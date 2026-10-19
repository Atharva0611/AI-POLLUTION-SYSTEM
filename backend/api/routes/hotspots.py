from fastapi import APIRouter, HTTPException
from pathlib import Path
import sys

router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from backend.ml.dbscan.hotspot_detection import get_hotspot_clusters
except ImportError:
    try:
        from ml.dbscan.hotspot_detection import get_hotspot_clusters
    except ImportError:
        get_hotspot_clusters = None


@router.get("/")
def get_hotspots():
    """Historical DBSCAN clusters; intentionally separate from live data."""
    if get_hotspot_clusters is None:
        raise HTTPException(status_code=503, detail="Hotspot detection module could not be imported.")
    try:
        results = get_hotspot_clusters()
        hotspots = results.to_dict(orient="records") if hasattr(results, "to_dict") else list(results)
        return {
            "status": "ok",
            "message": "Historical DBSCAN station clusters. These are not live pollution readings.",
            "source": "data/processed/pune_cpcb_features.csv",
            "count": len(hotspots),
            "hotspots": hotspots,
            "data_type": "historical_dbscan",
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"Hotspot input data is unavailable: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Hotspot detection failed: {exc}") from exc


@router.get("/live")
def get_live_hotspot_data():
    """Per-location current provider data/model estimates, not CPCB observations."""
    try:
        from backend.services.live_hotspots import get_live_hotspots
        result = get_live_hotspots()
        if result["status"] == "unavailable":
            raise HTTPException(status_code=503, detail=result)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        # Do not leak a provider exception or traceback to the public response.
        raise HTTPException(status_code=502, detail="Live hotspot providers could not be queried.") from exc
