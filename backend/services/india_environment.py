from __future__ import annotations

from backend.services.pune_locations import resolve_pune_location, get_all_pune_stations

from datetime import datetime, timedelta
import os
import re
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]
WEATHER_URL = "https://api.weatherapi.com/v1/forecast.json"

LOCALITIES = {
    "pune",
    "alandi",
    "akurdi",
    "baner",
    "bavdhan",
    "bhosari",
    "bhumkar nagar",
    "camp",
    "chakan",
    "dhankawadi",
    "dhanori",
    "dhayari",
    "hadapsar",
    "hinjewadi",
    "kalyani nagar",
    "karve nagar",
    "karve road",
    "katraj",
    "khadki",
    "kharadi",
    "kondhwa",
    "kothrud",
    "lohegaon",
    "magarpatta",
    "manjri",
    "mundhwa",
    "nigdi",
    "pashan",
    "pimpri",
    "pimpri chinchwad",
    "ravet",
    "sangvi",
    "shivajinagar",
    "sppu",
    "swargate",
    "talegaon",
    "viman nagar",
    "wakad",
    "warje",
    "yerawada",
    "moshi",
    "vishrantwadi",
    "aundh",
    "deccan",
    "koregaon park",
    "fc road",
}


AQI_BP = {
    "pm2_5": [
        (0.0, 30.0, 0, 50),
        (30.0, 60.0, 51, 100),
        (60.0, 90.0, 101, 200),
        (90.0, 120.0, 201, 300),
        (120.0, 250.0, 301, 400),
        (250.0, 500.0, 401, 500),
    ],
    "pm10": [
        (0.0, 50.0, 0, 50),
        (50.0, 100.0, 51, 100),
        (100.0, 250.0, 101, 200),
        (250.0, 350.0, 201, 300),
        (350.0, 430.0, 301, 400),
        (430.0, 500.0, 401, 500),
    ],
    "no2": [
        (0.0, 40.0, 0, 50),
        (40.0, 80.0, 51, 100),
        (80.0, 180.0, 101, 200),
        (180.0, 280.0, 201, 300),
        (280.0, 400.0, 301, 400),
        (400.0, 500.0, 401, 500),
    ],
    "so2": [
        (0.0, 40.0, 0, 50),
        (40.0, 80.0, 51, 100),
        (80.0, 380.0, 101, 200),
        (380.0, 800.0, 201, 300),
        (800.0, 1600.0, 301, 400),
        (1600.0, 2000.0, 401, 500),
    ],
    "o3": [
        (0.0, 50.0, 0, 50),
        (50.0, 100.0, 51, 100),
        (100.0, 168.0, 101, 200),
        (168.0, 208.0, 201, 300),
        (208.0, 748.0, 301, 400),
        (748.0, 1000.0, 401, 500),
    ],
    "co": [
        (0.0, 1.0, 0, 50),
        (1.0, 2.0, 51, 100),
        (2.0, 10.0, 101, 200),
        (10.0, 17.0, 201, 300),
        (17.0, 34.0, 301, 400),
        (34.0, 50.0, 401, 500),
    ],
}

AQI_CATEGORIES = [
    (0, 50, "Good"),
    (51, 100, "Satisfactory"),
    (101, 200, "Moderate"),
    (201, 300, "Poor"),
    (301, 400, "Very Poor"),
    (401, 500, "Severe"),
]


def _num(value: Any):
    try:
        if value is None:
            return None
        text = str(value).strip().lower()
        if text in {"", "none", "null", "nan"}:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any):
    if value is None:
        return None
    value = str(value).strip()
    return value if value else None


def _extract_location_from_question(question: str) -> str:
    if not question:
        return "Pune"

    clean_q = str(question).strip()

    # 1. Use the centralized universal location extractor
    try:
        from backend.services.location_extractor import extract_single_location, is_valid_location_candidate
        extracted = extract_single_location(clean_q)
        if extracted:
            return extracted
    except Exception:
        pass

    # 2. Check local Pune localities
    lower = clean_q.lower()
    for locality in sorted(LOCALITIES, key=len, reverse=True):
        if re.search(r"\b" + re.escape(locality) + r"\b", lower):
            if locality == "fc road":
                return "FC Road"
            return locality.title()

    # 3. Check location_resolver phrase
    try:
        from backend.services.location_resolver import extract_location_phrase
        cand = extract_location_phrase(clean_q)
        if cand:
            cleaned = re.sub(
                r"\b(hotspots?|pollution|air quality|aqi|weather|forecast|dbscan|shap|xgboost|today|now)\b.*$",
                "",
                cand,
                flags=re.IGNORECASE
            ).strip()
            if cleaned and cleaned.lower() not in {"the", "a", "an", "all", "what", "how", "why"}:
                return cleaned.title()
    except Exception:
        pass

    # 4. If clean_q is itself a location candidate (e.g. "Mumbai", "Nagpur", "Delhi")
    words = clean_q.split()
    if 1 <= len(words) <= 3 and not any(w.lower() in {"what", "is", "the", "aqi", "air", "pollution"} for w in words):
        return clean_q.title()

    return "Pune"


def _call_weatherapi(location: str) -> dict:
    load_dotenv(ROOT / ".env")

    api_key = os.getenv("WEATHER_API_KEY")

    if not api_key:
        return {"_error": "WEATHER_API_KEY is missing in .env"}

    loc_lower = location.lower()
    if loc_lower == "pune":
        query = "Pune, Maharashtra, India"
    elif loc_lower in LOCALITIES or any(loc_lower == p for p in LOCALITIES):
        query = f"{location}, Pune, Maharashtra, India"
    else:
        query = f"{location}, India"

    try:
        response = requests.get(
            WEATHER_URL,
            params={
                "key": api_key,
                "q": query,
                "days": 2,
                "aqi": "yes",
                "alerts": "no",
            },
            timeout=30,
        )

        if not response.ok:
            return {
                "_error": f"WeatherAPI HTTP {response.status_code}"
            }

        data = response.json()

        if data.get("error"):
            return {
                "_error": str(data["error"])
            }

        return data

    except requests.RequestException as exc:
        return {
            "_error": f"WeatherAPI request failed: {exc}"
        }


def _air_quality(block: dict) -> dict:
    aq = (block or {}).get("air_quality") or {}

    return {
        "pm2_5": _num(aq.get("pm2_5")),
        "pm10": _num(aq.get("pm10")),
        "no2": _num(aq.get("no2")),
        "so2": _num(aq.get("so2")),
        "co": _num(aq.get("co")),
        "o3": _num(aq.get("o3")),
        "us_epa_index": aq.get("us-epa-index"),
        "gb_defra_index": aq.get("gb-defra-index"),
    }


def _current(data: dict) -> dict:
    current = data.get("current") or {}

    return {
        **_air_quality(current),
        "temperature_c": _num(current.get("temp_c")),
        "feels_like_c": _num(current.get("feelslike_c")),
        "humidity": _num(current.get("humidity")),
        "rainfall_mm": _num(current.get("precip_mm")),
        "wind_speed_kph": _num(current.get("wind_kph")),
        "wind_direction": _text(current.get("wind_dir")),
        "gust_kph": _num(current.get("gust_kph")),
        "pressure_mb": _num(current.get("pressure_mb")),
        "visibility_km": _num(current.get("vis_km")),
        "uv": _num(current.get("uv")),
        "condition": _text(
            (current.get("condition") or {}).get("text")
        ),
        "last_updated": _text(current.get("last_updated")),
    }


def _daily_air_quality(data: dict) -> dict:
    result = {}

    days = (
        data.get("forecast", {})
        .get("forecastday", [])
        or []
    )

    for day in days:
        aq = day.get("air_quality") or {}

        result[day.get("date")] = {
            "pm2_5": _num(aq.get("pm2_5")),
            "pm10": _num(aq.get("pm10")),
            "no2": _num(aq.get("no2")),
            "so2": _num(aq.get("so2")),
            "co": _num(aq.get("co")),
            "o3": _num(aq.get("o3")),
            "us_epa_index": aq.get("us-epa-index"),
            "gb_defra_index": aq.get("gb-defra-index"),
        }

    return result


def _calc_subindex(param: str, val: float) -> int | None:
    if val is None or param not in AQI_BP:
        return None
    try:
        val = float(val)
    except (ValueError, TypeError):
        return None

    if val <= 0:
        return 0

    bps = AQI_BP[param]
    if val >= bps[-1][1]:
        return 500

    for low, high, ilow, ihigh in bps:
        if low <= val <= high:
            return round(((ihigh - ilow) / (high - low)) * (val - low) + ilow)

    return 500


def _pm25_subindex(pm25):
    return _calc_subindex("pm2_5", pm25)


def _aqi_from_pm25(pm25):
    subindex = _pm25_subindex(pm25)

    if subindex is None:
        return {
            "value": None,
            "category": "Unavailable",
            "controlling_pollutant": "PM2.5",
        }

    category = "Severe"

    for low, high, name in AQI_CATEGORIES:
        if low <= subindex <= high:
            category = name
            break

    return {
        "value": subindex,
        "category": category,
        "controlling_pollutant": "PM2.5",
        "basis": "Indicative PM2.5-to-AQI mapping (NAAQS CPCB standard).",
    }


def _calculate_overall_aqi(current: dict) -> dict:
    subindices = {}
    if current.get("pm2_5") is not None:
        subindices["PM2.5"] = _calc_subindex("pm2_5", current["pm2_5"])
    if current.get("pm10") is not None:
        subindices["PM10"] = _calc_subindex("pm10", current["pm10"])
    if current.get("no2") is not None:
        subindices["NO2"] = _calc_subindex("no2", current["no2"])
    if current.get("so2") is not None:
        subindices["SO2"] = _calc_subindex("so2", current["so2"])
    if current.get("o3") is not None:
        subindices["O3"] = _calc_subindex("o3", current["o3"])
    if current.get("co") is not None:
        co_mg = current["co"] / 1000.0 if current["co"] > 50 else current["co"]
        subindices["CO"] = _calc_subindex("co", co_mg)

    valid = {k: v for k, v in subindices.items() if v is not None}
    if not valid:
        return {
            "value": None,
            "category": "Unavailable",
            "controlling_pollutant": "Unavailable",
            "pollutant": "Unavailable",
            "basis": "No valid pollutant data available.",
        }

    controlling = max(valid, key=valid.get)
    max_subindex = valid[controlling]

    category = "Severe"
    for low, high, name in AQI_CATEGORIES:
        if low <= max_subindex <= high:
            category = name
            break

    return {
        "value": max_subindex,
        "category": category,
        "controlling_pollutant": controlling,
        "pollutant": controlling,
        "subindices": valid,
        "basis": f"Indian National AQI (NAAQS CPCB standard); controlling: {controlling}.",
    }


def _estimate_hourly_pm25(baseline_pm25, row):
    if baseline_pm25 is None:
        return None

    value = float(baseline_pm25)

    wind = row.get("wind_speed_kph") or row.get("wind_kph") or 0
    humidity = row.get("humidity") or 0
    rain_probability = row.get("rain_probability") or row.get("chance_of_rain") or 0
    rainfall = row.get("rainfall_mm") or row.get("precip_mm") or 0
    condition = str(row.get("condition") or "").lower()

    if wind < 5:
        value *= 1.12
    elif wind < 10:
        value *= 1.05
    elif wind >= 25:
        value *= 0.92

    if rain_probability >= 70:
        value *= 0.90
    elif rain_probability >= 50:
        value *= 0.94
    elif rain_probability >= 30:
        value *= 0.97

    if rainfall >= 5:
        value *= 0.90
    elif rainfall >= 1:
        value *= 0.95

    if humidity >= 90:
        value *= 1.04
    elif humidity >= 80:
        value *= 1.02

    if "mist" in condition or "fog" in condition:
        value *= 1.03

    return round(max(value, 0), 1)


def _hourly_forecast(data: dict, baseline_pm25):
    rows = []

    days = (
        data.get("forecast", {})
        .get("forecastday", [])
        or []
    )

    for day in days:
        for hour in day.get("hour", []) or []:

            temp = _num(hour.get("temp_c"))
            hum = _num(hour.get("humidity"))
            precip = _num(hour.get("precip_mm"))
            rain_prob = _num(hour.get("chance_of_rain"))
            wind = _num(hour.get("wind_kph"))
            cond = _text((hour.get("condition") or {}).get("text"))

            row = {
                "time": _text(hour.get("time")),
                "temp_c": temp,
                "temperature_c": temp,
                "humidity": hum,
                "rainfall_mm": precip,
                "precip_mm": precip,
                "chance_of_rain": rain_prob,
                "rain_probability": rain_prob,
                "wind_kph": wind,
                "wind_speed_kph": wind,
                "condition": cond,
            }

            row["pm2_5_estimate"] = _estimate_hourly_pm25(
                baseline_pm25,
                row,
            )

            aqi_obj = _aqi_from_pm25(
                row["pm2_5_estimate"]
            )
            row["aqi"] = aqi_obj
            row["indicative_aqi"] = aqi_obj

            rows.append(row)

    return rows


def _recommendations(current, aqi):
    actions = []

    pm25 = current.get("pm2_5")
    pm10 = current.get("pm10")
    wind = current.get("wind_speed_kph")
    humidity = current.get("humidity") or 0
    rainfall = current.get("rainfall_mm") or 0
    temperature = current.get("temperature_c")

    aqi_value = aqi.get("value")

    if aqi_value is not None and aqi_value >= 401:
        actions.extend([
            "Severe pollution: increase monitoring frequency.",
            "Reduce prolonged outdoor exposure.",
            "Protect vulnerable groups.",
            "Review major combustion and particulate sources.",
        ])
    elif aqi_value is not None and aqi_value >= 301:
        actions.extend([
            "Very poor air quality: strengthen dust controls.",
            "Review construction and traffic pollution sources.",
            "Discourage open burning and avoidable idling.",
        ])
    elif aqi_value is not None and aqi_value >= 201:
        actions.extend([
            "Poor air quality: strengthen dust and traffic controls.",
            "Inspect construction-site pollution controls.",
        ])
    elif aqi_value is not None and aqi_value >= 101:
        actions.extend([
            "Moderate air quality: maintain preventive source controls.",
        ])
    else:
        actions.append(
            "Continue routine environmental monitoring."
        )

    if pm25 is not None and pm25 > 60:
        actions.extend([
            "Prioritize PM2.5 source-control checks.",
            "Monitor high-traffic corridors.",
        ])

    if pm10 is not None and pm10 > 100:
        actions.extend([
            "Increase road-dust suppression.",
            "Cover exposed soil and loose construction material.",
        ])

    if wind is not None and wind < 5:
        actions.extend([
            "Low wind: treat the period as weak pollutant dispersion.",
            "Minimize unnecessary idling.",
        ])

    if wind is not None and wind >= 25:
        actions.extend([
            "Strong wind: secure loose construction materials.",
            "Monitor PM10 resuspension.",
        ])

    if humidity >= 80:
        actions.append(
            "High humidity: monitor visibility and particulate persistence."
        )

    if rainfall > 0:
        actions.extend([
            "Inspect drainage after rainfall.",
            "Check roads for mud and runoff.",
            "Reassess particulate conditions after rainfall.",
        ])

    if rainfall >= 5:
        actions.append(
            "Inspect construction-site erosion and runoff controls."
        )

    if temperature is not None and temperature >= 35:
        actions.append(
            "Use heat-aware scheduling for outdoor workers."
        )

    return list(dict.fromkeys(actions))


RECOMMENDATION_LIBRARY = [
    f"{action} {condition}."
    for action in [
        "Increase monitoring",
        "Review traffic controls",
        "Review dust controls",
        "Inspect construction sites",
        "Inspect roadside conditions",
        "Review combustion sources",
        "Review waste-burning controls",
        "Increase public communication",
        "Review vulnerable-group protection",
        "Review hotspot actions",
    ]
    for condition in [
        "during low wind",
        "during moderate wind",
        "during strong wind",
        "during high humidity",
        "during dry weather",
        "during rainfall",
        "after rainfall",
        "during heavy rainfall",
        "during high temperature",
        "during low visibility",
        "during high UV",
        "when PM2.5 rises",
        "when PM10 rises",
        "when AQI rises",
    ]
]


def get_environment_for_user(question: str) -> dict:

    requested = _extract_location_from_question(
        question
    )

    data = _call_weatherapi(
        requested
    )

    # Use an independent no-key provider if WeatherAPI credentials, quota, or
    # upstream service fail. Never label modeled values as official CPCB data.
    if data.get("_error"):
        from backend.services.open_meteo_current import get_open_meteo_current
        fallback = get_open_meteo_current(requested)
        if fallback.get("status") == "ok":
            fallback["data_provenance"]["fallback_reason"] = data["_error"]
            return fallback

        return {
            "status": "degraded",
            "location": {
                "requested_location": requested,
                "weatherapi_location": requested,
            },
            "current": {},
            "current_aqi": {},
            "forecast_6_hours": [],
            "forecast_24_hours": [],
            "prediction": {
                "pm25_next_1h": None,
                "label": "Unavailable",
            },
            "policy": [
                data["_error"]
            ],
            "recommendations": [],
            "recommendation_library_size": len(
                RECOMMENDATION_LIBRARY
            ),
            "data_provenance": {
                "primary_source": "WeatherAPI",
                "location_source": "WeatherAPI",
                "air_quality_source": "WeatherAPI Air Quality",
                "forecast_source": "WeatherAPI Forecast API",
                "hourly_pm25_source": "Weather-adjusted PM2.5 estimate",
                "cpcb_role": "Optional historical/model/regulatory layer only",
                "rag_role": "Policy and knowledge retrieval only",
                "langgraph_role": "Routing and orchestration only",
            },
        }

    current = _current(data)

    daily_air = _daily_air_quality(
        data
    )

    baseline_pm25 = current.get(
        "pm2_5"
    )

    if baseline_pm25 is None:

        for day_data in daily_air.values():

            if day_data.get("pm2_5") is not None:
                baseline_pm25 = day_data["pm2_5"]
                break

    all_hourly = _hourly_forecast(
        data,
        baseline_pm25,
    )

    location = data.get("location") or {}
    local_time_text = location.get("localtime")
    local_now = None

    if local_time_text:
        try:
            local_now = datetime.strptime(
                str(local_time_text), "%Y-%m-%d %H:%M"
            )
        except ValueError:
            local_now = None

    # Parse provider timestamps and exclude hours already in the past.
    parsed_hours = []
    for row in all_hourly:
        try:
            hour_dt = datetime.strptime(
                str(row.get("time")), "%Y-%m-%d %H:%M"
            )
        except (TypeError, ValueError):
            continue
        parsed_hours.append((hour_dt, row))

    if local_now is not None:
        future_hours = [
            (dt, row) for dt, row in parsed_hours if dt > local_now
        ]
        tomorrow_date = (local_now + timedelta(days=1)).date()
    else:
        # If provider local time is missing, avoid inventing a time.
        future_hours = parsed_hours
        tomorrow_date = (
            parsed_hours[0][0].date() + timedelta(days=1)
            if parsed_hours else None
        )

    is_tomorrow_request = "tomorrow" in question.lower()

    if is_tomorrow_request and tomorrow_date is not None:
        selected_hours = [
            row for dt, row in future_hours
            if dt.date() == tomorrow_date
        ][:24]
        forecast_period = "tomorrow"
    else:
        selected_hours = [
            row for _, row in future_hours
        ][:24]
        forecast_period = "upcoming_24_hours"

    # The next-hour estimate always comes from the next future hour,
    # regardless of whether the user asks to see tomorrow's forecast.
    next_hour = future_hours[0][1] if future_hours else {}
    next_pm25 = next_hour.get("pm2_5_estimate")

    if next_pm25 is None:
        trend = "Unavailable"
    elif current.get("pm2_5") is None:
        trend = "Weather-adjusted estimate"
    elif next_pm25 > current["pm2_5"] + 2:
        trend = "Likely increasing"
    elif next_pm25 < current["pm2_5"] - 2:
        trend = "Likely decreasing"
    else:
        trend = "Likely stable"

    location = data.get(
        "location"
    ) or {}

    current_aqi = _calculate_overall_aqi(
        current
    )

    actions = _recommendations(
        current,
        current_aqi,
    )

    return {
        "status": "ok",

        "location": {
            "requested_location": requested,
            "display_name": f"{requested} (Pune)" if requested.lower() in LOCALITIES and requested.lower() != "pune" else (requested if requested.lower() != "pune" else location.get("name", "Pune")),
            "weatherapi_location": location.get("name"),
            "region": location.get("region"),
            "country": location.get("country"),
            "latitude": location.get("lat"),
            "longitude": location.get("lon"),
            "timezone": location.get("tz_id"),
            "local_time": location.get("localtime"),
        },

        "current": current,

        "current_aqi": current_aqi,

        "daily_air_quality": daily_air,

        "forecast_6_hours": selected_hours[:6],

        "forecast_24_hours": selected_hours,

        "forecast_period": forecast_period,

        "prediction": {
            "pm25_next_1h": next_pm25,
            "label": trend,
            "source": "Weather-adjusted PM2.5 estimate",
            "is_estimate": True,
        },

        "policy": actions,

        "recommendations": actions,

        "recommendation_library_size": len(
            RECOMMENDATION_LIBRARY
        ),

        "data_provenance": {
            "primary_source": "WeatherAPI",
            "location_source": "WeatherAPI",
            "air_quality_source": "WeatherAPI Air Quality",
            "forecast_source": "WeatherAPI Forecast API",
            "hourly_weather_source": "WeatherAPI hourly forecast",
            "hourly_pm25_source": "Weather-adjusted PM2.5 estimate",
            "cpcb_role": "Optional historical/model/regulatory layer only",
            "rag_role": "Policy and knowledge retrieval only",
            "langgraph_role": "Routing and orchestration only",
        },

        "xgboost": {
            "available": False,
            "reason": "Kept separate from the live WeatherAPI route.",
        },
    }
