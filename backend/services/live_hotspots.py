"""Location-specific live environmental data for the hotspot explorer.

WeatherAPI observations and Open-Meteo CAMS model estimates are kept distinct.
These results are not official CPCB station measurements.
"""
from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from backend.services.pune_locations import get_all_pune_stations

ROOT = Path(__file__).resolve().parents[2]
WEATHER_URL = "https://api.weatherapi.com/v1/current.json"
OPEN_METEO_AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
OPEN_METEO_WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(min(1.0, math.sqrt(a)))


def _severity(value: Any, scale: str | None) -> str:
    if value is None:
        return "unavailable"
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "unavailable"
    if scale == "US AQI":
        return ("good" if n <= 50 else "moderate" if n <= 100 else
                "unhealthy_sensitive" if n <= 150 else "unhealthy" if n <= 200 else
                "very_unhealthy" if n <= 300 else "hazardous")
    if scale == "US EPA index (1-6)":
        return ("good" if n <= 1 else "moderate" if n <= 2 else
                "unhealthy_sensitive" if n <= 3 else "unhealthy" if n <= 4 else
                "very_unhealthy" if n <= 5 else "hazardous")
    return "unavailable"


def _weatherapi_station(station: dict[str, Any], api_key: str) -> dict[str, Any]:
    lat, lon = float(station["latitude"]), float(station["longitude"])
    response = requests.get(
        WEATHER_URL,
        params={"key": api_key, "q": f"{lat},{lon}", "aqi": "yes"},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    loc = payload.get("location") or {}
    cur = payload.get("current") or {}
    aq = cur.get("air_quality") or {}
    resolved_lat = float(loc.get("lat", lat))
    resolved_lon = float(loc.get("lon", lon))
    distance = _distance_km(lat, lon, resolved_lat, resolved_lon)
    if distance > 10:
        raise ValueError(f"Provider resolved {distance:.1f} km from requested station")
    index = aq.get("us-epa-index")
    return {
        "status": "ok" if aq else "degraded",
        "requested_location": station["canonical_location"],
        "resolved_location": loc.get("name") or station["display_name"],
        "station_name": station.get("station_name") or station["display_name"],
        "latitude": resolved_lat, "longitude": resolved_lon,
        "requested_latitude": lat, "requested_longitude": lon,
        "resolution_distance_km": round(distance, 2),
        "aqi": index,
        "aqi_scale": "US EPA index (1-6)" if index is not None else None,
        "aqi_value_type": "category_index_not_numeric_AQI",
        "severity": _severity(index, "US EPA index (1-6)"),
        "pm2_5": aq.get("pm2_5"), "pm10": aq.get("pm10"),
        "pollutants": {k: aq.get(k) for k in ("no2", "so2", "co", "o3")},
        "weather": {
            "temperature_c": cur.get("temp_c"),
            "humidity_percent": cur.get("humidity"),
            "wind_speed_kph": cur.get("wind_kph"),
            "wind_direction": cur.get("wind_dir"),
            "rainfall_mm": cur.get("precip_mm"),
            "condition": (cur.get("condition") or {}).get("text"),
        },
        "timestamp": cur.get("last_updated"),
        "source": "WeatherAPI",
        "data_type": "provider_current_estimate",
        "warnings": [
            "WeatherAPI US EPA index is a 1-6 category index, not a numeric AQI.",
            "Not a verified CPCB station measurement unless independently confirmed.",
        ],
    }


def _open_meteo_station(station: dict[str, Any]) -> dict[str, Any]:
    lat, lon = float(station["latitude"]), float(station["longitude"])
    params = {"latitude": lat, "longitude": lon, "timezone": "Asia/Kolkata"}
    air_resp = requests.get(
        OPEN_METEO_AIR_URL,
        params={**params, "current": "pm2_5,pm10,us_aqi"},
        timeout=15,
    )
    air_resp.raise_for_status()
    air_payload = air_resp.json()
    air = air_payload.get("current") or {}
    weather_resp = requests.get(
        OPEN_METEO_WEATHER_URL,
        params={**params, "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m"},
        timeout=15,
    )
    weather_resp.raise_for_status()
    weather_payload = weather_resp.json()
    weather = weather_payload.get("current") or {}
    aqi = air.get("us_aqi")
    return {
        "status": "ok" if aqi is not None or air.get("pm2_5") is not None else "degraded",
        "requested_location": station["canonical_location"],
        "resolved_location": station["display_name"],
        "station_name": station.get("station_name") or station["display_name"],
        "latitude": air_payload.get("latitude", lat),
        "longitude": air_payload.get("longitude", lon),
        "requested_latitude": lat, "requested_longitude": lon,
        "resolution_distance_km": round(_distance_km(lat, lon, float(air_payload.get("latitude", lat)), float(air_payload.get("longitude", lon))), 2),
        "aqi": round(float(aqi)) if aqi is not None else None,
        "aqi_scale": "US AQI" if aqi is not None else None,
        "aqi_value_type": "numeric_AQI" if aqi is not None else None,
        "severity": _severity(aqi, "US AQI"),
        "pm2_5": air.get("pm2_5"), "pm10": air.get("pm10"),
        "pollutants": {},
        "weather": {
            "temperature_c": weather.get("temperature_2m"),
            "humidity_percent": weather.get("relative_humidity_2m"),
            "wind_speed_kph": weather.get("wind_speed_10m"),
            "wind_direction": weather.get("wind_direction_10m"),
            "rainfall_mm": weather.get("precipitation"),
        },
        "timestamp": air.get("time") or weather.get("time"),
        "source": "Open-Meteo CAMS + Open-Meteo weather model",
        "data_type": "model_grid_estimate",
        "warnings": [
            "Model-grid estimate, not a CPCB station observation.",
            "AQI uses the US AQI scale and must not be interpreted as India's CPCB AQI.",
        ],
    }


def get_live_hotspots() -> dict[str, Any]:
    """Fetch each registered station independently; return partial successes."""
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("WEATHER_API_KEY")
    stations = get_all_pune_stations()
    results: list[dict[str, Any]] = []
    for station in stations:
        if not station.get("latitude") or not station.get("longitude"):
            continue
        try:
            if api_key:
                try:
                    item = _weatherapi_station(station, api_key)
                except (requests.RequestException, ValueError, KeyError, TypeError):
                    item = _open_meteo_station(station)
                    item["warnings"].append("WeatherAPI unavailable for this station; Open-Meteo fallback used.")
            else:
                item = _open_meteo_station(station)
                item["warnings"].append("WEATHER_API_KEY is not configured; Open-Meteo fallback used.")
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            item = {
                "status": "error",
                "requested_location": station["canonical_location"],
                "resolved_location": station["display_name"],
                "station_name": station.get("station_name") or station["display_name"],
                "latitude": station["latitude"], "longitude": station["longitude"],
                "requested_latitude": station["latitude"], "requested_longitude": station["longitude"],
                "aqi": None, "aqi_scale": None, "severity": "unavailable",
                "pm2_5": None, "pm10": None, "weather": {}, "timestamp": None,
                "source": None, "data_type": "unavailable",
                "warnings": [f"Both live data providers failed: {type(exc).__name__}"],
            }
        results.append(item)
    success = sum(item["status"] == "ok" for item in results)
    return {
        "status": "ok" if success == len(results) and results else "partial" if success else "unavailable",
        "message": "Live environmental provider data/model estimates; not official CPCB station data.",
        "count": len(results), "successful_count": success,
        "data_type": "live_environmental_risk_layer",
        "risk_method": "Severity is based only on the returned provider AQI/index. Weather is contextual and does not modify AQI.",
        "sources": ["WeatherAPI", "Open-Meteo Air Quality API (CAMS model)", "Open-Meteo Forecast API"],
        "stations": results,
    }
