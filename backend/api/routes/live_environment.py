"""Unified, source-aware current air-quality and weather endpoint."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os

from fastapi import APIRouter, Query

from backend.services.openaq_service import OpenAQClient, OpenAQError, classify_freshness
from backend.services.openweather_service import OpenWeatherClient, OpenWeatherError, classify_provider_time

router = APIRouter()


def _openaq_result(latitude, longitude, radius_m):
    client = OpenAQClient()
    try:
        catalog = client.locations(latitude, longitude, radius_m, limit=30)
        stations = []
        measurements = []
        # Keep network calls bounded and parallel; each station uses its own HTTP session.
        def read_station(row):
            station_id = row.get("id")
            if station_id is None:
                return None
            try:
                detail = OpenAQClient().measurements(int(station_id))
            except OpenAQError:
                return None
            if not detail:
                return None
            station = detail.get("station") or {}
            coordinates = row.get("coordinates") or {}
            station.setdefault("latitude", coordinates.get("latitude"))
            station.setdefault("longitude", coordinates.get("longitude"))
            return station_id, station, detail.get("measurements") or []

        with ThreadPoolExecutor(max_workers=4) as pool:
            for outcome in pool.map(read_station, catalog[:8]):
                if not outcome:
                    continue
                station_id, station, rows = outcome
                stations.append(station)
                for source_item in rows:
                    item = dict(source_item)
                    item.update(classify_freshness(item.get("observed_at_utc")))
                    item["station"] = station.get("name")
                    item["station_id"] = station_id
                    item["latitude"] = station.get("latitude")
                    item["longitude"] = station.get("longitude")
                    item["eligible_for_live"] = False
                    measurements.append(item)
        max_age = int(os.getenv("OPENAQ_LIVE_MAX_AGE_MINUTES", "180"))
        eligible = []
        for item in measurements:
            age_seconds = item.get("age_seconds")
            if (age_seconds is not None and item.get("freshness") == "fresh"
                    and age_seconds <= max_age * 60
                    and isinstance(item.get("value"), (int, float))):
                item["eligible_for_live"] = True
                eligible.append(item)
            else:
                item["eligible_for_live"] = False
        return {
            "status": "ok" if eligible else ("no_fresh_data" if measurements else "no_measurements"),
            "provider": "OpenAQ",
            "source_type": "third_party_sensor_observations",
            "max_age_minutes": max_age,
            "stations": stations,
            "measurements": measurements,
            "live_measurements": eligible,
            "fresh_count": len(eligible),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "error": None if eligible else "No OpenAQ observations meet the current-data age limit.",
        }
    except OpenAQError as exc:
        return {"status": "unavailable", "provider": "OpenAQ", "stations": [], "measurements": [],
                "live_measurements": [], "fresh_count": 0, "error": str(exc)}


def _validated_openweather(raw, max_age):
    result = dict(raw)
    freshness = classify_provider_time(result.get("observed_at_unix"), max_age)
    result.update(freshness)
    if not result["is_current"]:
        result["status"] = "stale_or_invalid"
        result["error"] = "OpenWeather observation timestamp is missing, invalid, future-dated, or older than the configured live-data limit."
    else:
        result["status"] = "ok"
        result["error"] = None
    return result


@router.get("/air-quality")
def current_environment(location: str = Query(default="Wagholi, Pune, Maharashtra, India", min_length=2, max_length=120),
                        radius_m: int = Query(default=15000, ge=100, le=100000)):
    """Fetch independently timestamped current data; never use historical fallback values."""
    resolver = OpenWeatherClient()
    try:
        resolved = resolver.resolve_location(location.strip())
    except OpenWeatherError as geocode_error:
        # Keep OpenAQ usable when OpenWeather geocoding is down or its key is
        # missing, using the project's existing validated resolver / OSM.
        try:
            from backend.services.universal_location_resolver import resolve_universal_location
            fallback = resolve_universal_location(location.strip())
            if not fallback.get("success") or fallback.get("latitude") is None or fallback.get("longitude") is None:
                raise ValueError("Existing location resolver did not verify this place.")
            resolved = {
                "requested": location,
                "resolved_name": fallback.get("display_name") or fallback.get("location_name") or location,
                "latitude": fallback["latitude"],
                "longitude": fallback["longitude"],
                "resolution_source": fallback.get("resolution_source", "existing_location_resolver"),
            }
        except Exception:
            return {
                "status": "unavailable",
                "location": {"requested": location, "resolved_name": None, "latitude": None, "longitude": None},
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "providers": {
                    "openaq": {"status": "blocked_by_location_resolution", "error": "Coordinates could not be verified; OpenAQ was not queried.", "stations": [], "measurements": [], "live_measurements": []},
                    "openweather_air_pollution": {"status": "unavailable", "error": str(geocode_error)},
                    "openweather_weather": {"status": "unavailable", "error": str(geocode_error)},
                },
            }
    lat, lon = resolved["latitude"], resolved["longitude"]
    max_age = int(os.getenv("OPENWEATHER_LIVE_MAX_AGE_MINUTES", "180"))
    with ThreadPoolExecutor(max_workers=3) as pool:
        openaq_future = pool.submit(_openaq_result, lat, lon, radius_m)
        pollution_future = pool.submit(_safe_openweather, resolver, "current_air_pollution", lat, lon, max_age)
        weather_future = pool.submit(_safe_openweather, resolver, "current_weather", lat, lon, max_age)
        openaq = openaq_future.result()
        pollution = pollution_future.result()
        weather = weather_future.result()
    any_current = bool(openaq.get("live_measurements")) or pollution.get("status") == "ok" or weather.get("status") == "ok"
    return {
        "status": "ok" if any_current else "unavailable",
        "location": resolved,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "providers": {
            "openaq": openaq,
            "openweather_air_pollution": pollution,
            "openweather_weather": weather,
        },
        "notes": [
            "OpenWeather AQI uses its own 1-5 scale and is not CPCB AQI.",
            "OpenAQ sensor measurements and OpenWeather values are separate provider results and are not averaged.",
            "Only timestamp-validated readings are eligible to be called current.",
        ],
    }


def _safe_openweather(client, method, latitude, longitude, max_age):
    try:
        raw = getattr(client, method)(latitude, longitude)
        return _validated_openweather(raw, max_age)
    except OpenWeatherError as exc:
        return {"status": "unavailable", "provider": "OpenWeather", "error": str(exc)}
