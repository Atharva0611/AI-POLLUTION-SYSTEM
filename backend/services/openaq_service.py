"""OpenAQ v3 client with explicit measurement provenance and freshness."""
from datetime import datetime, timezone
import os
import requests

BASE_URL = "https://api.openaq.org/v3"
POLLUTANTS = {"pm25", "pm2.5", "pm10", "no2", "so2", "o3", "co"}


class OpenAQError(RuntimeError):
    pass


def classify_freshness(timestamp, now=None):
    if not timestamp:
        return {"freshness": "missing_timestamp", "age_hours": None, "is_fresh": False}
    try:
        observed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        observed = observed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return {"freshness": "invalid_timestamp", "age_hours": None, "is_fresh": False}
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    age = (now.astimezone(timezone.utc) - observed).total_seconds() / 3600
    max_age_minutes = float(os.getenv("OPENAQ_LIVE_MAX_AGE_MINUTES", "180"))
    fresh_h = float(os.getenv("OPENAQ_FRESH_HOURS", "24"))
    delayed_h = float(os.getenv("OPENAQ_DELAYED_HOURS", "72"))
    age_minutes = age * 60
    status = ("future_timestamp" if age < 0 else
              "fresh" if age_minutes <= max_age_minutes else
              "delayed" if age <= delayed_h else "stale")
    return {"freshness": status, "age_hours": round(max(age, 0), 3),
            "age_minutes": round(max(age_minutes, 0), 1),
            "is_fresh": status == "fresh" and age >= 0}


class OpenAQClient:
    def __init__(self, api_key=None, timeout=None):
        self.api_key = (api_key if api_key is not None else os.getenv("OPENAQ_API_KEY", "")).strip()
        self.timeout = timeout or int(os.getenv("OPENAQ_TIMEOUT_SECONDS", "12"))
        self.session = requests.Session()

    def get(self, path, params=None):
        if not self.api_key:
            raise OpenAQError("OpenAQ is not configured. Set OPENAQ_API_KEY in the backend environment.")
        try:
            response = self.session.get(
                BASE_URL + path, params=params,
                headers={"X-API-Key": self.api_key, "Accept": "application/json"},
                timeout=self.timeout,
            )
            if response.status_code == 401:
                raise OpenAQError("OpenAQ rejected the API key. Check or rotate the configured key.")
            if response.status_code == 429:
                raise OpenAQError("OpenAQ rate limit reached. Try again later.")
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise OpenAQError("OpenAQ returned an unexpected response.")
            return payload
        except OpenAQError:
            raise
        except requests.Timeout as exc:
            raise OpenAQError("OpenAQ request timed out.") from exc
        except requests.RequestException as exc:
            raise OpenAQError("OpenAQ is temporarily unavailable.") from exc
        except ValueError as exc:
            raise OpenAQError("OpenAQ returned invalid JSON.") from exc

    def locations(self, latitude=18.5204, longitude=73.8567, radius_m=15000, limit=100):
        payload = self.get("/locations", {"coordinates": f"{latitude},{longitude}",
                                          "radius": max(100, min(int(radius_m), 100000)),
                                          "limit": max(1, min(int(limit), 1000))})
        rows = payload.get("results", [])
        return rows if isinstance(rows, list) else []

    def measurements(self, location_id):
        location_payload = self.get(f"/locations/{int(location_id)}")
        rows = location_payload.get("results") or []
        if not rows or not isinstance(rows[0], dict):
            return None
        station = rows[0]
        sensor_payload = self.get(f"/locations/{int(location_id)}/sensors")
        sensors = sensor_payload.get("results") or []
        result = []
        for sensor in sensors:
            parameter = sensor.get("parameter") or {}
            pollutant = str(parameter.get("name") or "").lower()
            if pollutant not in POLLUTANTS:
                continue
            latest = sensor.get("latest") or {}
            dt = sensor.get("datetimeLast") or {}
            timestamp = dt.get("utc") or (latest.get("datetime") or {}).get("utc")
            result.append({
                "sensor_id": sensor.get("id"),
                "pollutant": "pm25" if pollutant == "pm2.5" else pollutant,
                "value": latest.get("value"),
                "unit": parameter.get("units"),
                "observed_at_utc": timestamp,
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "provider": "OpenAQ",
                "source_type": "third_party_measurement",
                **classify_freshness(timestamp),
            })
        coordinates = station.get("coordinates") or {}
        return {
            "station": {
                "id": station.get("id"), "name": station.get("name"),
                "locality": station.get("locality"), "is_monitor": station.get("isMonitor"),
                "latitude": coordinates.get("latitude"), "longitude": coordinates.get("longitude"),
                "provider": "OpenAQ",
            },
            "measurements": result,
            "note": "OpenAQ observations are not automatically official CPCB AQI. Check each timestamp before calling it current.",
        }


def get_station_catalog(latitude=18.5204, longitude=73.8567, radius_m=15000, limit=100):
    rows = OpenAQClient().locations(latitude, longitude, radius_m, limit)
    stations = []
    for row in rows:
        coords = row.get("coordinates") or {}
        stations.append({
            "id": row.get("id"), "name": row.get("name"), "locality": row.get("locality"),
            "is_monitor": row.get("isMonitor"), "latitude": coords.get("latitude"),
            "longitude": coords.get("longitude"), "provider": "OpenAQ",
        })
    return {
        "status": "ok", "provider": "OpenAQ", "source_type": "third_party_station_catalog",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "count": len(stations),
        "stations": stations,
        "note": "Station presence does not guarantee fresh readings. Inspect sensor timestamps.",
    }
