"""Historical meteorological observations from the Open-Meteo reanalysis archive.

These are modeled/reanalysis weather estimates, not CPCB pollution measurements.
"""
from datetime import date, timedelta
from typing import Any

import requests
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HOURLY_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
    "wind_direction_10m",
]


def get_historical_weather(
    location: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """Return hourly historical weather for a named location."""
    name = (location or "").strip()
    if not name:
        raise ValueError("Provide a location, for example Wagholi or Pune.")

    end = end_date or (date.today() - timedelta(days=2))
    start = start_date or (end - timedelta(days=6))
    if start > end:
        raise ValueError("start_date must be on or before end_date.")
    if (end - start).days > 30:
        raise ValueError("Please request a maximum of 31 calendar days per request.")

    try:
        geo_response = requests.get(
            GEOCODING_URL,
            params={"name": name, "count": 5, "language": "en", "format": "json"},
            timeout=15,
        )
        geo_response.raise_for_status()
        places = geo_response.json().get("results") or []
        if not places:
            raise ValueError(f"Could not find a location named '{name}'. Try a nearby city.")
        # Prefer an India result when multiple matches exist.
        place = next((p for p in places if p.get("country_code") == "IN"), places[0])

        response = requests.get(
            ARCHIVE_URL,
            params={
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "hourly": ",".join(HOURLY_VARIABLES),
                "timezone": "Asia/Kolkata",
                "wind_speed_unit": "kmh",
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        hourly = data.get("hourly") or {}
        times = hourly.get("time") or []
        if not times:
            raise ValueError("The historical weather provider returned no hourly observations.")

        rows = []
        for i, timestamp in enumerate(times):
            row = {"time": timestamp}
            for variable in HOURLY_VARIABLES:
                values = hourly.get(variable) or []
                row[variable] = values[i] if i < len(values) else None
            rows.append(row)

        return {
            "status": "ok",
            "source": "Open-Meteo Historical Weather API (reanalysis)",
            "data_type": "historical_weather_estimates",
            "location": {
                "requested": name,
                "resolved": place.get("name", name),
                "admin1": place.get("admin1"),
                "country": place.get("country"),
                "latitude": place["latitude"],
                "longitude": place["longitude"],
            },
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "timezone": data.get("timezone", "Asia/Kolkata"),
            "units": {
                "temperature_2m": "°C",
                "relative_humidity_2m": "%",
                "precipitation": "mm",
                "wind_speed_10m": "km/h",
                "wind_direction_10m": "°",
            },
            "hourly": rows,
            "note": "Weather reanalysis estimates; not official station observations, PM2.5 measurements, or AQI.",
        }
    except requests.RequestException as exc:
        raise RuntimeError(f"Historical weather provider request failed: {exc}") from exc


@router.get("/history", tags=["Historical Weather"])
def historical_weather(
    location: str = Query("Pune", min_length=1, max_length=100),
    start_date: date | None = None,
    end_date: date | None = None,
):
    try:
        return get_historical_weather(location, start_date, end_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
