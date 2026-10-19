"""Coordinate-specific Open-Meteo fallback; CAMS values are model estimates."""
from __future__ import annotations
from typing import Any
import requests
from backend.services.pune_locations import resolve_pune_location

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


def _resolve_coordinates(name: str) -> dict[str, Any] | None:
    # Prefer our canonical Pune station/locality registry; never silently swap
    # an unresolved locality for city-centre Pune coordinates.
    known = resolve_pune_location(name)
    if known and known.get("latitude") is not None and known.get("longitude") is not None:
        return {
            "name": known.get("display_name") or known.get("canonical_location"),
            "latitude": float(known["latitude"]),
            "longitude": float(known["longitude"]),
            "region": "Maharashtra",
            "country": "India",
            "resolution_source": "ORIVA canonical station registry",
        }
    query = name if "," in name else f"{name}, Pune, Maharashtra, India"
    response = requests.get(
        GEOCODING_URL,
        params={"name": query, "count": 10, "language": "en", "format": "json"},
        timeout=12,
    )
    response.raise_for_status()
    results = response.json().get("results") or []
    candidates = [p for p in results if p.get("country_code") == "IN"]
    # Only accept an explicit locality match; never fall back to generic Pune.
    target = name.casefold().strip()
    place = next((p for p in candidates if str(p.get("name", "")).casefold() == target), None)
    if not place:
        return None
    return {
        "name": place.get("name"),
        "latitude": float(place["latitude"]),
        "longitude": float(place["longitude"]),
        "region": place.get("admin1"),
        "country": place.get("country"),
        "resolution_source": "Open-Meteo Geocoding",
    }


def get_open_meteo_current(location: str) -> dict[str, Any]:
    name = (location or "").strip()
    if not name:
        return {"status": "location_unresolved", "error": "A location is required."}
    try:
        place = _resolve_coordinates(name)
        if not place:
            return {"status": "location_unresolved", "error": f"Could not confidently resolve '{name}'. No Pune-centre fallback was used."}
        params = {"latitude": place["latitude"], "longitude": place["longitude"], "timezone": "Asia/Kolkata"}
        air_response = requests.get(AIR_URL, params={**params, "current": "pm2_5,pm10,us_aqi", "hourly": "pm2_5,pm10,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone"}, timeout=20)
        air_response.raise_for_status()
        air_payload = air_response.json()
        current_air = air_payload.get("current") or {}
        hourly = air_payload.get("hourly") or {}
        times = hourly.get("time") or []
        idx = times.index(current_air["time"]) if current_air.get("time") in times else 0
        weather_response = requests.get(WEATHER_URL, params={**params, "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m,apparent_temperature", "forecast_days": 1}, timeout=20)
        weather_response.raise_for_status()
        weather_payload = weather_response.json()
        weather = weather_payload.get("current") or {}

        def pollutant(key):
            direct = current_air.get(key)
            values = hourly.get(key) or []
            return direct if direct is not None else values[idx] if idx < len(values) else None

        aqi = current_air.get("us_aqi")
        category = ("Good" if aqi <= 50 else "Moderate" if aqi <= 100 else "Unhealthy for Sensitive Groups" if aqi <= 150 else "Unhealthy" if aqi <= 200 else "Very Unhealthy" if aqi <= 300 else "Hazardous") if aqi is not None else "Unavailable"
        resolved_lat = float(air_payload.get("latitude", place["latitude"]))
        resolved_lon = float(air_payload.get("longitude", place["longitude"]))
        return {
            "status": "ok" if pollutant("pm2_5") is not None or pollutant("pm10") is not None else "degraded",
            "location": {
                "requested_location": name, "display_name": place["name"],
                "region": place.get("region"), "country": place.get("country"),
                "latitude": resolved_lat, "longitude": resolved_lon,
                "requested_latitude": place["latitude"], "requested_longitude": place["longitude"],
                "timezone": air_payload.get("timezone", "Asia/Kolkata"),
                "local_time": current_air.get("time") or weather.get("time"),
                "resolution_source": place["resolution_source"],
                "grid_resolution_note": "Open-Meteo returns atmospheric model grid coordinates; nearby locations may share a grid cell."
            },
            "current": {
                "pm2_5": pollutant("pm2_5"), "pm10": pollutant("pm10"),
                "no2": pollutant("nitrogen_dioxide"), "so2": pollutant("sulphur_dioxide"),
                "co": pollutant("carbon_monoxide"), "o3": pollutant("ozone"),
                "temperature_c": weather.get("temperature_2m"), "feels_like_c": weather.get("apparent_temperature"),
                "humidity": weather.get("relative_humidity_2m"), "rainfall_mm": weather.get("precipitation"),
                "wind_speed_kph": weather.get("wind_speed_10m"), "wind_direction": weather.get("wind_direction_10m"),
                "condition": "Model-derived current conditions", "last_updated": current_air.get("time") or weather.get("time"),
            },
            "current_aqi": {
                "value": round(float(aqi)) if aqi is not None else None, "category": category,
                "controlling_pollutant": "Open-Meteo US AQI",
                "basis": "Provider-reported US AQI from CAMS model; not CPCB Indian National AQI."
            },
            "daily_air_quality": {}, "forecast_6_hours": [], "forecast_24_hours": [],
            "prediction": {"pm25_next_1h": None, "label": "Unavailable"},
            "recommendations": [], "policy": [],
            "data_provenance": {
                "primary_source": "Open-Meteo CAMS air-quality model + Open-Meteo weather model",
                "location_source": place["resolution_source"], "air_quality_source": "Open-Meteo CAMS model estimate",
                "forecast_source": "Open-Meteo", "cpcb_role": "Not queried; this is not an official CPCB station reading",
                "aqi_scale": "US AQI, not India's CPCB AQI",
            },
        }
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        return {"status": "error", "error": f"Open-Meteo fallback failed: {type(exc).__name__}: {exc}"}
