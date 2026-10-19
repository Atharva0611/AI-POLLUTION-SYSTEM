"""Fallback current air-quality/weather data from Open-Meteo for localities.

Open-Meteo CAMS values are model estimates, not CPCB station measurements.
"""
from __future__ import annotations

from typing import Any
import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


def get_open_meteo_current(location: str) -> dict[str, Any]:
    name = (location or "Pune").strip()
    # Adding Pune/Maharashtra/India helps disambiguate local neighbourhoods.
    query = name if name.casefold() == "pune" else f"{name}, Pune, Maharashtra, India"
    try:
        geo = requests.get(
            GEOCODING_URL,
            params={"name": query, "count": 10, "language": "en", "format": "json"},
            timeout=12,
        )
        geo.raise_for_status()
        results = geo.json().get("results") or []
        if not results:
            # Retry with the broader city name if a neighbourhood isn't indexed.
            geo = requests.get(
                GEOCODING_URL,
                params={"name": "Pune", "count": 5, "language": "en", "format": "json"},
                timeout=12,
            )
            geo.raise_for_status()
            results = geo.json().get("results") or []
        place = next(
            (p for p in results if p.get("country_code") == "IN" and "Pune" in (p.get("name", "") + " " + p.get("admin1", ""))),
            next((p for p in results if p.get("country_code") == "IN"), None),
        )
        if not place:
            return {"status": "error", "error": f"Could not geocode {name} in India."}

        params = {
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "timezone": "Asia/Kolkata",
        }
        air_response = requests.get(
            AIR_URL,
            params={
                **params,
                "current": "pm2_5,pm10,us_aqi",
                "hourly": "pm2_5,pm10,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone",
                "forecast_hours": 1,
            },
            timeout=20,
        )
        air_response.raise_for_status()
        air = air_response.json()
        current_air = air.get("current") or {}
        hourly = air.get("hourly") or {}
        times = hourly.get("time") or []
        idx = 0
        if times and current_air.get("time") in times:
            idx = times.index(current_air["time"])

        weather_response = requests.get(
            WEATHER_URL,
            params={
                **params,
                "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m,apparent_temperature",
                "forecast_days": 1,
            },
            timeout=20,
        )
        weather_response.raise_for_status()
        weather = weather_response.json().get("current") or {}

        def value(source, key, index=None):
            if source.get(key) is not None:
                return source.get(key)
            vals = hourly.get(key) or []
            return vals[index] if index is not None and index < len(vals) else None

        pm25 = value(current_air, "pm2_5", idx)
        pm10 = value(current_air, "pm10", idx)
        us_aqi = current_air.get("us_aqi")
        if us_aqi is None:
            # Do not fabricate an AQI if the provider did not return one.
            aqi_value = None
            category = "Unavailable"
        else:
            aqi_value = round(float(us_aqi))
            category = (
                "Good" if aqi_value <= 50 else
                "Moderate" if aqi_value <= 100 else
                "Unhealthy for Sensitive Groups" if aqi_value <= 150 else
                "Unhealthy" if aqi_value <= 200 else
                "Very Unhealthy" if aqi_value <= 300 else "Hazardous"
            )
        return {
            "status": "ok" if pm25 is not None or pm10 is not None or weather else "degraded",
            "location": {
                "requested_location": name,
                "display_name": f"{name} (Pune region)",
                "weatherapi_location": place.get("name", "Pune"),
                "region": place.get("admin1", "Maharashtra"),
                "country": place.get("country", "India"),
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "timezone": air.get("timezone", "Asia/Kolkata"),
                "local_time": current_air.get("time") or weather.get("time"),
            },
            "current": {
                "pm2_5": pm25,
                "pm10": pm10,
                "no2": value({}, "nitrogen_dioxide", idx),
                "so2": value({}, "sulphur_dioxide", idx),
                "co": value({}, "carbon_monoxide", idx),
                "o3": value({}, "ozone", idx),
                "temperature_c": weather.get("temperature_2m"),
                "feels_like_c": weather.get("apparent_temperature"),
                "humidity": weather.get("relative_humidity_2m"),
                "rainfall_mm": weather.get("precipitation"),
                "wind_speed_kph": weather.get("wind_speed_10m"),
                "wind_direction": weather.get("wind_direction_10m"),
                "condition": "Model-derived current conditions",
                "last_updated": current_air.get("time") or weather.get("time"),
            },
            "current_aqi": {
                "value": aqi_value,
                "category": category,
                "controlling_pollutant": "Open-Meteo US AQI",
                "basis": "Provider-reported US AQI from CAMS model; not CPCB Indian National AQI.",
            },
            "daily_air_quality": {},
            "forecast_6_hours": [],
            "forecast_24_hours": [],
            "prediction": {"pm25_next_1h": None, "label": "Unavailable"},
            "recommendations": [],
            "policy": [],
            "data_provenance": {
                "primary_source": "Open-Meteo CAMS air-quality model + Open-Meteo weather model",
                "location_source": "Open-Meteo Geocoding",
                "air_quality_source": "Open-Meteo CAMS model estimate",
                "forecast_source": "Open-Meteo",
                "cpcb_role": "Not queried; this is not an official CPCB station reading",
                "aqi_scale": "US AQI, explicitly labeled; not India's CPCB AQI",
            },
        }
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        return {"status": "error", "error": f"Open-Meteo fallback failed: {exc}"}
