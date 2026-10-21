"""OpenWeather current air-pollution and weather API client.

Provider readings remain separate from OpenAQ observations. OpenWeather's AQI
is its own 1-5 index and must never be presented as CPCB AQI.
"""
from datetime import datetime, timezone
import os
import requests

BASE_URL = "https://api.openweathermap.org/data/2.5"
GEO_URL = "https://api.openweathermap.org/geo/1.0"


class OpenWeatherError(RuntimeError):
    """Safe, provider-specific error with no credentials in the message."""


def classify_provider_time(timestamp, max_age_minutes=None, now=None):
    """Classify a Unix timestamp or ISO timestamp against a strict live window."""
    if timestamp is None:
        return {"freshness": "missing_timestamp", "age_minutes": None, "is_current": False}
    try:
        if isinstance(timestamp, (int, float)):
            observed = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        else:
            observed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=timezone.utc)
            observed = observed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return {"freshness": "invalid_timestamp", "age_minutes": None, "is_current": False}
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    age = (now.astimezone(timezone.utc) - observed).total_seconds() / 60
    limit = max_age_minutes if max_age_minutes is not None else int(os.getenv("OPENWEATHER_LIVE_MAX_AGE_MINUTES", "180"))
    status = "future_timestamp" if age < 0 else "fresh" if age <= limit else "stale"
    return {"freshness": status, "age_minutes": round(max(age, 0), 1), "is_current": status == "fresh"}


class OpenWeatherClient:
    def __init__(self, api_key=None, timeout=None, session=None):
        self.api_key = (api_key if api_key is not None else os.getenv("OPENWEATHER_API_KEY", "")).strip()
        self.timeout = timeout or int(os.getenv("OPENWEATHER_TIMEOUT_SECONDS", "12"))
        self.session = session or requests.Session()

    def _get(self, base, path, params=None):
        if not self.api_key:
            raise OpenWeatherError("OpenWeather is not configured. Set OPENWEATHER_API_KEY in the backend environment.")
        query = dict(params or {})
        query["appid"] = self.api_key
        try:
            response = self.session.get(base + path, params=query, timeout=self.timeout)
            if response.status_code in (401, 403):
                raise OpenWeatherError("OpenWeather rejected the API key. Verify OPENWEATHER_API_KEY and account access.")
            if response.status_code == 429:
                raise OpenWeatherError("OpenWeather rate limit reached. Try again later.")
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise OpenWeatherError("OpenWeather returned an unexpected response.")
            return data
        except OpenWeatherError:
            raise
        except requests.Timeout as exc:
            raise OpenWeatherError("OpenWeather request timed out.") from exc
        except requests.RequestException as exc:
            raise OpenWeatherError("OpenWeather is temporarily unavailable.") from exc
        except ValueError as exc:
            raise OpenWeatherError("OpenWeather returned invalid JSON.") from exc

    def resolve_location(self, location):
        if not self.api_key:
            raise OpenWeatherError("OpenWeather is not configured. Set OPENWEATHER_API_KEY in the backend environment.")
        try:
            response = self.session.get(
                GEO_URL + "/direct",
                params={"q": location, "limit": 5, "appid": self.api_key},
                timeout=self.timeout,
            )
            if response.status_code in (401, 403):
                raise OpenWeatherError("OpenWeather rejected the API key. Verify OPENWEATHER_API_KEY and account access.")
            if response.status_code == 429:
                raise OpenWeatherError("OpenWeather rate limit reached. Try again later.")
            response.raise_for_status()
            rows = response.json()
            if not isinstance(rows, list):
                raise OpenWeatherError("OpenWeather geocoding returned an unexpected response.")
        except OpenWeatherError:
            raise
        except requests.Timeout as exc:
            raise OpenWeatherError("Location lookup timed out.") from exc
        except requests.RequestException as exc:
            raise OpenWeatherError("Location lookup is temporarily unavailable.") from exc
        except ValueError as exc:
            raise OpenWeatherError("Location lookup returned invalid JSON.") from exc
        if not rows:
            raise OpenWeatherError(f"No location match was found for '{location}'. Try a more specific town or city.")
        chosen = rows[0]
        return {
            "requested": location,
            "resolved_name": ", ".join(str(v) for v in [chosen.get("name"), chosen.get("state"), chosen.get("country")] if v),
            "latitude": chosen.get("lat"),
            "longitude": chosen.get("lon"),
            "country": chosen.get("country"),
            "state": chosen.get("state"),
            "matches": [{"name": r.get("name"), "state": r.get("state"), "country": r.get("country"),
                         "latitude": r.get("lat"), "longitude": r.get("lon")} for r in rows],
        }

    def current_air_pollution(self, latitude, longitude):
        payload = self._get(BASE_URL, "/air_pollution", {"lat": latitude, "lon": longitude})
        rows = payload.get("list") or []
        if not rows or not isinstance(rows[0], dict):
            raise OpenWeatherError("OpenWeather returned no current air-pollution record.")
        row = rows[0]
        components = row.get("components") or {}
        return {
            "provider": "OpenWeather",
            "source_type": "provider_current_air_pollution",
            "aqi": (row.get("main") or {}).get("aqi"),
            "aqi_scale": "OpenWeather 1-5",
            "components": {k: v for k, v in components.items() if isinstance(v, (int, float))},
            "observed_at": datetime.fromtimestamp(row["dt"], tz=timezone.utc).isoformat() if isinstance(row.get("dt"), (int, float)) else None,
            "observed_at_unix": row.get("dt"),
        }

    def current_weather(self, latitude, longitude):
        payload = self._get(BASE_URL, "/weather", {"lat": latitude, "lon": longitude, "units": "metric"})
        main = payload.get("main") or {}
        wind = payload.get("wind") or {}
        weather = (payload.get("weather") or [{}])[0]
        return {
            "provider": "OpenWeather",
            "source_type": "current_weather_observation",
            "temperature_c": main.get("temp"),
            "feels_like_c": main.get("feels_like"),
            "humidity_percent": main.get("humidity"),
            "pressure_hpa": main.get("pressure"),
            "wind_speed_m_s": wind.get("speed"),
            "wind_direction_degrees": wind.get("deg"),
            "cloud_cover_percent": (payload.get("clouds") or {}).get("all"),
            "condition": weather.get("description"),
            "observed_at": datetime.fromtimestamp(payload["dt"], tz=timezone.utc).isoformat() if isinstance(payload.get("dt"), (int, float)) else None,
            "observed_at_unix": payload.get("dt"),
        }
