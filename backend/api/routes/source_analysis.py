from fastapi import APIRouter, HTTPException, Query

from backend.ml.source_analysis import analyze_source_indicators

router = APIRouter()


@router.get("/")
def source_analysis(
    station: str | None = Query(
        default=None,
        description="Optional monitoring station name; omit for all stations.",
    )
):
    try:
        result = analyze_source_indicators(station)
        return {
            "status": "ok",
            "message": "Historical statistical pollution-source indicators.",
            **result,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Source analysis failed: {type(exc).__name__}: {exc}",
        )
