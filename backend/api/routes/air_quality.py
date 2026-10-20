"""Source-aware OpenAQ endpoints for ORIVA."""
from fastapi import APIRouter, HTTPException, Query

from backend.services.openaq_service import OpenAQClient, OpenAQError, get_station_catalog

router = APIRouter()


@router.get("/locations")
def nearby_locations(
    latitude: float = Query(default=18.5204, ge=-90, le=90),
    longitude: float = Query(default=73.8567, ge=-180, le=180),
    radius_m: int = Query(default=15000, ge=100, le=100000),
    limit: int = Query(default=100, ge=1, le=1000),
):
    """Discover nearby OpenAQ locations; this is not an official CPCB station list."""
    try:
        return get_station_catalog(latitude, longitude, radius_m, limit)
    except OpenAQError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/stations/{location_id}")
def station_measurements(location_id: int):
    """Return latest provider measurements with timestamps and freshness labels."""
    try:
        result = OpenAQClient().measurements(location_id)
        if result is None:
            raise HTTPException(status_code=404, detail="OpenAQ location was not found.")
        return {
            "status": "ok",
            "provider": "OpenAQ",
            "source_type": "third_party_measurements",
            "location_id": location_id,
            **result,
        }
    except OpenAQError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
