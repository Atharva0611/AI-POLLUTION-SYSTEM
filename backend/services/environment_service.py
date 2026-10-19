import os
import re
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv


# ============================================================
# PROJECT CONFIG
# ============================================================

PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".."
    )
)

load_dotenv(
    os.path.join(
        PROJECT_ROOT,
        ".env"
    )
)

WEATHER_API_KEY = os.getenv(
    "WEATHER_API_KEY"
)

NOMINATIM_URL = (
    "https://nominatim.openstreetmap.org/search"
)

WEATHER_API_BASE = (
    "https://api.weatherapi.com/v1"
)

CURRENT_URL = (
    f"{WEATHER_API_BASE}/current.json"
)

FORECAST_URL = (
    f"{WEATHER_API_BASE}/forecast.json"
)


# ============================================================
# ERROR
# ============================================================

class EnvironmentServiceError(Exception):
    pass


# ============================================================
# HELPERS
# ============================================================

def to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def require_api_key():

    if not WEATHER_API_KEY:
        raise EnvironmentServiceError(
            "WEATHER_API_KEY is missing from .env"
        )


# ============================================================
# EXTRACT LOCATION FROM USER INPUT
# ============================================================

def extract_location(question: str) -> str:

    if not question or not question.strip():
        raise EnvironmentServiceError(
            "Please provide a location."
        )

    text = question.strip()

    patterns = [
        r"(?:live|current|real[- ]?time)?\s*aqi\s+"
        r"(?:of|in|at|for)\s+(.+)",

        r"(?:live|current|real[- ]?time)?\s*air\s+quality\s+"
        r"(?:of|in|at|for)\s+(.+)",

        r"(?:current|live)?\s*pollution\s+"
        r"(?:of|in|at|for)\s+(.+)",

        r"(?:current|live)?\s*weather\s+"
        r"(?:of|in|at|for)\s+(.+)",

        r"(?:temperature)\s+"
        r"(?:of|in|at|for)\s+(.+)",

        r"(?:rainfall|rain)\s+"
        r"(?:of|in|at|for)\s+(.+)",

        r"(?:forecast)\s+"
        r"(?:of|in|at|for)\s+(.+)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            location = match.group(1).strip()

            location = re.sub(
                r"[?.!]+$",
                "",
                location
            ).strip()

            if location:
                return location

    # If the user simply types:
    # Kharadi
    # Pune
    # Delhi

    text = re.sub(
        r"[?.!]+$",
        "",
        text
    ).strip()

    if text:
        return text

    raise EnvironmentServiceError(
        "Could not determine the location."
    )


# ============================================================
# NOMINATIM GEOCODING
# ============================================================

def resolve_location(
    location: str
) -> Dict[str, Any]:

    headers = {
        "User-Agent":
            "AI-Pollution-System/1.0"
    }

    queries = [
        f"{location}, Pune, Maharashtra, India",
        f"{location}, Maharashtra, India",
        f"{location}, India",
        location,
    ]

    best = None
    best_score = -1

    for query in queries:

        try:

            response = requests.get(
                NOMINATIM_URL,
                params={
                    "q": query,
                    "format": "jsonv2",
                    "limit": 10,
                    "countrycodes": "in",
                    "addressdetails": 1,
                },
                headers=headers,
                timeout=15
            )

            response.raise_for_status()

            results = response.json()

            for item in results:

                address = item.get(
                    "address",
                    {}
                )

                name = str(
                    item.get(
                        "name",
                        ""
                    )
                ).lower()

                display = str(
                    item.get(
                        "display_name",
                        ""
                    )
                ).lower()

                neighbourhood = str(
                    address.get(
                        "neighbourhood",
                        ""
                    )
                ).lower()

                suburb = str(
                    address.get(
                        "suburb",
                        ""
                    )
                ).lower()

                score = 0

                location_lower = (
                    location.lower().strip()
                )

                if name == location_lower:
                    score += 1000

                if neighbourhood == location_lower:
                    score += 950

                if suburb == location_lower:
                    score += 900

                if location_lower in name:
                    score += 500

                if location_lower in neighbourhood:
                    score += 450

                if location_lower in suburb:
                    score += 400

                if location_lower in display:
                    score += 200

                if "pune" in display:
                    score += 100

                if score > best_score:

                    best_score = score
                    best = item

        except requests.RequestException:
            continue

        if best is not None:
            break

    if best is None:
        raise EnvironmentServiceError(
            f"Could not find location '{location}'."
        )

    latitude = to_float(
        best.get("lat")
    )

    longitude = to_float(
        best.get("lon")
    )

    if latitude is None or longitude is None:
        raise EnvironmentServiceError(
            f"Location '{location}' has no valid coordinates."
        )

    address = best.get(
        "address",
        {}
    )

    return {
        "requested_location": location,

        "resolved_name": (
            best.get("name")
            or location
        ),

        "display_name": (
            best.get("display_name")
            or location
        ),

        "latitude": latitude,
        "longitude": longitude,

        "state": (
            address.get("state")
            or "Maharashtra"
        ),

        "country": (
            address.get("country")
            or "India"
        ),

        "resolver": "Nominatim",
    }


# ============================================================
# WEATHERAPI CURRENT DATA
# ============================================================

def get_current(
    latitude: float,
    longitude: float
) -> Dict[str, Any]:

    require_api_key()

    response = requests.get(
        CURRENT_URL,
        params={
            "key": WEATHER_API_KEY,
            "q": f"{latitude},{longitude}",
            "aqi": "yes",
        },
        timeout=20
    )

    response.raise_for_status()

    data = response.json()

    if "error" in data:
        raise EnvironmentServiceError(
            data["error"].get(
                "message",
                "WeatherAPI error"
            )
        )

    location = data.get(
        "location",
        {}
    )

    current = data.get(
        "current",
        {}
    )

    air = current.get(
        "air_quality",
        {}
    )

    if not current:
        raise EnvironmentServiceError(
            "WeatherAPI returned no current weather."
        )

    wind_kph = to_float(
        current.get(
            "wind_kph"
        )
    )

    return {
        "temperature_c": to_float(
            current.get("temp_c")
        ),

        "feels_like_c": to_float(
            current.get("feelslike_c")
        ),

        "windchill_c": to_float(
            current.get("windchill_c")
        ),

        "heat_index_c": to_float(
            current.get("heatindex_c")
        ),

        "dewpoint_c": to_float(
            current.get("dewpoint_c")
        ),

        "humidity": to_float(
            current.get("humidity")
        ),

        "pressure_mb": to_float(
            current.get("pressure_mb")
        ),

        "visibility_km": to_float(
            current.get("vis_km")
        ),

        "rainfall_mm": to_float(
            current.get("precip_mm")
        ),

        "wind_speed_kph": wind_kph,

        "wind_speed_ms": (
            wind_kph / 3.6
            if wind_kph is not None
            else None
        ),

        "wind_degree": to_float(
            current.get("wind_degree")
        ),

        "wind_direction": current.get(
            "wind_dir"
        ),

        "cloud": to_int(
            current.get("cloud")
        ),

        "uv": to_float(
            current.get("uv")
        ),

        "condition": (
            current
            .get("condition", {})
            .get("text")
        ),

        "is_day": current.get(
            "is_day"
        ),

        "last_updated": current.get(
            "last_updated"
        ),

        # Air quality
        "pm2_5": to_float(
            air.get("pm2_5")
        ),

        "pm10": to_float(
            air.get("pm10")
        ),

        "co": to_float(
            air.get("co")
        ),

        "no2": to_float(
            air.get("no2")
        ),

        "so2": to_float(
            air.get("so2")
        ),

        "o3": to_float(
            air.get("o3")
        ),

        "us_epa_index": to_int(
            air.get("us-epa-index")
        ),

        "uk_defra_index": to_int(
            air.get("gb-defra-index")
        ),

        "weatherapi_name": location.get(
            "name"
        ),

        "weatherapi_region": location.get(
            "region"
        ),
    }


# ============================================================
# WEATHERAPI FORECAST
# ============================================================

def get_forecast(
    latitude: float,
    longitude: float,
    days: int = 3
) -> Dict[str, Any]:

    require_api_key()

    days = max(
        1,
        min(
            int(days),
            14
        )
    )

    response = requests.get(
        FORECAST_URL,
        params={
            "key": WEATHER_API_KEY,
            "q": f"{latitude},{longitude}",
            "days": days,
            "aqi": "yes",
            "alerts": "yes",
        },
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if "error" in data:
        raise EnvironmentServiceError(
            data["error"].get(
                "message",
                "WeatherAPI forecast error"
            )
        )

    forecast_days = data.get(
        "forecast",
        {}
    ).get(
        "forecastday",
        []
    )

    hours = []

    for day in forecast_days:

        for hour in day.get(
            "hour",
            []
        ):

            air = hour.get(
                "air_quality",
                {}
            ) or {}

            hours.append({

                "time": hour.get(
                    "time"
                ),

                "temperature_c": to_float(
                    hour.get("temp_c")
                ),

                "feels_like_c": to_float(
                    hour.get("feelslike_c")
                ),

                "humidity": to_float(
                    hour.get("humidity")
                ),

                "wind_speed_kph": to_float(
                    hour.get("wind_kph")
                ),

                "wind_degree": to_float(
                    hour.get("wind_degree")
                ),

                "wind_direction": hour.get(
                    "wind_dir"
                ),

                "rainfall_mm": to_float(
                    hour.get("precip_mm")
                ),

                "rain_probability": to_int(
                    hour.get("chance_of_rain")
                ),

                "snow_probability": to_int(
                    hour.get("chance_of_snow")
                ),

                "cloud": to_int(
                    hour.get("cloud")
                ),

                "visibility_km": to_float(
                    hour.get("vis_km")
                ),

                "uv": to_float(
                    hour.get("uv")
                ),

                "condition": (
                    hour
                    .get("condition", {})
                    .get("text")
                ),

                # Forecast AQ
                "pm2_5": to_float(
                    air.get("pm2_5")
                ),

                "pm10": to_float(
                    air.get("pm10")
                ),

                "co": to_float(
                    air.get("co")
                ),

                "no2": to_float(
                    air.get("no2")
                ),

                "so2": to_float(
                    air.get("so2")
                ),

                "o3": to_float(
                    air.get("o3")
                ),

                "us_epa_index": to_int(
                    air.get(
                        "us-epa-index"
                    )
                ),

                "uk_defra_index": to_int(
                    air.get(
                        "gb-defra-index"
                    )
                ),
            })

    alerts = data.get(
        "alerts",
        {}
    ).get(
        "alert",
        []
    )

    return {
        "days": days,
        "hours": hours,
        "alerts": alerts,
    }


# ============================================================
# TAKE NEXT N HOURS
# ============================================================

def next_hours(
    forecast: Dict[str, Any],
    count: int = 6
):

    return forecast.get(
        "hours",
        []
    )[:count]


# ============================================================
# ENVIRONMENTAL CONDITION ANALYSIS
# ============================================================

def assess_conditions(
    current: Dict[str, Any]
) -> Dict[str, Any]:

    pm25 = current.get(
        "pm2_5"
    )

    pm10 = current.get(
        "pm10"
    )

    temperature = current.get(
        "temperature_c"
    )

    rainfall = current.get(
        "rainfall_mm"
    )

    humidity = current.get(
        "humidity"
    )

    wind_speed = current.get(
        "wind_speed_ms"
    )

    conditions = []
    priorities = []

    # --------------------------------------------------------
    # Pollution
    # --------------------------------------------------------

    if pm25 is not None:

        if pm25 >= 90:

            conditions.append(
                "Very high PM2.5"
            )

            priorities.append(
                "high_pollution"
            )

        elif pm25 >= 60:

            conditions.append(
                "High PM2.5"
            )

            priorities.append(
                "high_pollution"

            )

        elif pm25 >= 35:

            conditions.append(
                "Elevated PM2.5"
            )

            priorities.append(
                "elevated_pollution"
            )

    if pm10 is not None and pm10 >= 100:

        conditions.append(
            "High PM10"
        )

        priorities.append(
            "high_particle_load"
        )

    # --------------------------------------------------------
    # Temperature
    # --------------------------------------------------------

    if temperature is not None:

        if temperature >= 35:

            conditions.append(
                "High temperature"
            )

            priorities.append(
                "heat"
            )

        elif temperature <= 10:

            conditions.append(
                "Low temperature"
            )

            priorities.append(
                "cold"
            )

    # --------------------------------------------------------
    # Rain
    # --------------------------------------------------------

    if rainfall is not None and rainfall >= 10:

        conditions.append(
            "Heavy rainfall"
        )

        priorities.append(
            "rain"
        )

    elif rainfall is not None and rainfall > 0:

        conditions.append(
            "Rainfall present"
        )

    # --------------------------------------------------------
    # Humidity
    # --------------------------------------------------------

    if humidity is not None and humidity >= 80:

        conditions.append(
            "High humidity"
        )

    # --------------------------------------------------------
    # Wind
    # --------------------------------------------------------

    if (
        wind_speed is not None
        and wind_speed <= 2
    ):

        conditions.append(
            "Low wind speed"
        )

        priorities.append(
            "poor_dispersion"
        )

    return {
        "conditions": conditions,
        "priorities": list(
            dict.fromkeys(
                priorities
            )
        ),
    }


# ============================================================
# RECOMMENDED MEASURES
# ============================================================

def recommend_measures(
    current: Dict[str, Any],
    assessment: Dict[str, Any]
):

    measures = []

    priorities = assessment.get(
        "priorities",
        []
    )

    pm25 = current.get(
        "pm2_5"
    )

    temperature = current.get(
        "temperature_c"
    )

    rainfall = current.get(
        "rainfall_mm"
    )

    wind_speed = current.get(
        "wind_speed_ms"
    )

    # --------------------------------------------------------
    # High pollution
    # --------------------------------------------------------

    if "high_pollution" in priorities:

        measures.extend([
            "Increase live air-quality monitoring frequency.",
            "Inspect nearby traffic, construction and other emission sources.",
            "Prioritize control of active dust-generating activities.",
            "Recommend reducing unnecessary prolonged outdoor exposure while pollution remains elevated.",
        ])

    elif "elevated_pollution" in priorities:

        measures.append(
            "Continue close air-quality monitoring and inspect important local emission sources."
        )

    # --------------------------------------------------------
    # Low dispersion
    # --------------------------------------------------------

    if "poor_dispersion" in priorities:

        measures.append(
            "Increase hotspot surveillance because low wind can reduce pollutant dispersion."
        )

    # --------------------------------------------------------
    # Heat + pollution
    # --------------------------------------------------------

    if (
        "high_pollution" in priorities
        and "heat" in priorities
    ):

        measures.extend([
            "Treat the situation as combined pollution and heat exposure.",
            "Limit prolonged outdoor activity and maintain hydration.",
        ])

    # --------------------------------------------------------
    # Rain + pollution
    # --------------------------------------------------------

    if (
        "high_pollution" in priorities
        and "rain" in priorities
    ):

        measures.extend([
            "Recheck pollution levels after rainfall because particulate levels can change rapidly.",
            "Monitor drainage and flood-prone areas.",
        ])

    elif "rain" in priorities:

        measures.append(
            "Monitor drainage, waterlogging and traffic conditions during heavy rainfall."
        )

    # --------------------------------------------------------
    # Low temperature
    # --------------------------------------------------------

    if "cold" in priorities:

        measures.append(
            "Continue pollution monitoring during cold and potentially stagnant conditions."
        )

    # --------------------------------------------------------
    # No special condition
    # --------------------------------------------------------

    if not measures:

        measures.append(
            "Continue routine environmental monitoring."
        )

    # Remove duplicates
    return list(
        dict.fromkeys(
            measures
        )
    )


# ============================================================
# MASTER ENVIRONMENT REPORT
# ============================================================

def get_environment_report(
    question: str,
    forecast_hours: int = 6
) -> Dict[str, Any]:

    # --------------------------------------------------------
    # Location
    # --------------------------------------------------------

    location_query = extract_location(
        question
    )

    location = resolve_location(
        location_query
    )

    latitude = location[
        "latitude"
    ]

    longitude = location[
        "longitude"
    ]

    # --------------------------------------------------------
    # Current
    # --------------------------------------------------------

    current = get_current(
        latitude,
        longitude
    )

    # --------------------------------------------------------
    # Forecast
    # --------------------------------------------------------

    forecast = get_forecast(
        latitude,
        longitude,
        days=3
    )

    upcoming = next_hours(
        forecast,
        count=forecast_hours
    )

    # --------------------------------------------------------
    # Assessment
    # --------------------------------------------------------

    assessment = assess_conditions(
        current
    )

    measures = recommend_measures(
        current,
        assessment
    )

    # --------------------------------------------------------
    # Final report
    # --------------------------------------------------------

    return {
        "location": location,

        "current": current,

        "forecast": upcoming,

        "alerts": forecast.get(
            "alerts",
            []
        ),

        "assessment": assessment,

        "recommended_measures": measures,

        "source": "WeatherAPI + Nominatim",

        "live": True,
    }


# ============================================================
# FORMAT REPORT
# ============================================================

def format_environment_report(
    report: Dict[str, Any]
) -> str:

    location = report[
        "location"
    ]

    current = report[
        "current"
    ]

    assessment = report[
        "assessment"
    ]

    measures = report[
        "recommended_measures"
    ]

    upcoming = report[
        "forecast"
    ]

    lines = []

    lines.append(
        "=" * 65
    )

    lines.append(
        "ENVIRONMENTAL INTELLIGENCE REPORT"
    )

    lines.append(
        "=" * 65
    )

    lines.append(
        f"Location: {location['requested_location']}"
    )

    lines.append(
        f"Resolved: {location['display_name']}"
    )

    lines.append(
        f"Coordinates: "
        f"{location['latitude']}, "
        f"{location['longitude']}"
    )

    lines.append("")

    lines.append(
        "CURRENT CONDITIONS"
    )

    lines.append("-" * 65)

    lines.append(
        f"PM2.5: {current.get('pm2_5')} µg/m³"
    )

    lines.append(
        f"PM10: {current.get('pm10')} µg/m³"
    )

    lines.append(
        f"NO2: {current.get('no2')} µg/m³"
    )

    lines.append(
        f"SO2: {current.get('so2')} µg/m³"
    )

    lines.append(
        f"CO: {current.get('co')} µg/m³"
    )

    lines.append(
        f"O3: {current.get('o3')} µg/m³"
    )

    lines.append(
        f"Temperature: "
        f"{current.get('temperature_c')} °C"
    )

    lines.append(
        f"Feels like: "
        f"{current.get('feels_like_c')} °C"
    )

    lines.append(
        f"Humidity: "
        f"{current.get('humidity')} %"
    )

    lines.append(
        f"Rainfall: "
        f"{current.get('rainfall_mm')} mm"
    )

    lines.append(
        f"Wind: "
        f"{current.get('wind_speed_kph')} km/h"
    )

    lines.append(
        f"Pressure: "
        f"{current.get('pressure_mb')} mb"
    )

    lines.append(
        f"Visibility: "
        f"{current.get('visibility_km')} km"
    )

    lines.append(
        f"UV: "
        f"{current.get('uv')}"
    )

    lines.append(
        f"Condition: "
        f"{current.get('condition')}"
    )

    lines.append(
        f"Updated: "
        f"{current.get('last_updated')}"
    )

    lines.append("")

    lines.append(
        "WEATHER / POLLUTION FORECAST"
    )

    lines.append("-" * 65)

    for item in upcoming:

        lines.append(
            f"{item.get('time')} | "
            f"Temp {item.get('temperature_c')}°C | "
            f"Rain {item.get('rain_probability')}% | "
            f"Rainfall {item.get('rainfall_mm')} mm | "
            f"Wind {item.get('wind_speed_kph')} km/h | "
            f"PM2.5 {item.get('pm2_5')}"
        )

    lines.append("")

    lines.append(
        "DETECTED CONDITIONS"
    )

    lines.append("-" * 65)

    if assessment["conditions"]:

        for condition in assessment[
            "conditions"
        ]:

            lines.append(
                f"- {condition}"
            )

    else:

        lines.append(
            "- No special environmental condition detected."
        )

    lines.append("")

    lines.append(
        "RECOMMENDED MEASURES"
    )

    lines.append("-" * 65)

    for index, measure in enumerate(
        measures,
        start=1
    ):

        lines.append(
            f"{index}. {measure}"
        )

    lines.append("")

    lines.append(
        "AQI INDEX NOTE"
    )

    lines.append("-" * 65)

    lines.append(
        "US EPA and UK DEFRA indexes are reported exactly "
        "as supplied by WeatherAPI. They are not CPCB AQI."
    )

    lines.append("")

    lines.append(
        "Sources: Nominatim for location resolution; "
        "WeatherAPI for live and forecast weather/AQ data."
    )

    return "\n".join(lines)


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    question = input(
        "\nEnter your environmental question: "
    ).strip()

    try:

        report = get_environment_report(
            question,
            forecast_hours=6
        )

        print(
            "\n" +
            format_environment_report(
                report
            )
        )

    except Exception as exc:

        print(
            "\nENVIRONMENT ERROR:"
        )

        print(
            exc
        )
# ============================================================
# IMPROVED LOCATION EXTRACTOR
# ============================================================

def extract_location(question: str) -> str:

    if not question or not question.strip():
        raise EnvironmentServiceError(
            "Please provide a location."
        )

    text = question.strip()

    # Remove trailing punctuation
    text = re.sub(
        r"[?.!]+$",
        "",
        text
    ).strip()

    # --------------------------------------------------------
    # Natural-language patterns
    # --------------------------------------------------------

    patterns = [

        # rainfall
        r"(?:what\s+is\s+)?(?:the\s+)?rainfall"
        r"(?:\s+status|\s+situation|\s+forecast)?"
        r"\s+(?:of|in|at|for)\s+(.+)",

        # rain
        r"(?:will\s+it\s+)?rain"
        r"(?:fall)?"
        r"(?:\s+status|\s+forecast|\s+situation)?"
        r"\s+(?:of|in|at|for)\s+(.+)",

        # temperature
        r"(?:what\s+is\s+)?(?:the\s+)?temperature"
        r"(?:\s+status|\s+forecast|\s+situation)?"
        r"\s+(?:of|in|at|for)\s+(.+)",

        # weather
        r"(?:what\s+is\s+)?(?:the\s+)?weather"
        r"(?:\s+status|\s+forecast|\s+situation)?"
        r"\s+(?:of|in|at|for)\s+(.+)",

        # air quality
        r"(?:what\s+is\s+)?(?:the\s+)?air\s+quality"
        r"(?:\s+status|\s+situation|\s+forecast)?"
        r"\s+(?:of|in|at|for)\s+(.+)",

        # pollution
        r"(?:what\s+is\s+)?(?:the\s+)?pollution"
        r"(?:\s+status|\s+situation|\s+forecast)?"
        r"\s+(?:of|in|at|for)\s+(.+)",

        # AQI
        r"(?:what\s+is\s+)?(?:the\s+)?aqi"
        r"(?:\s+status|\s+situation|\s+forecast)?"
        r"\s+(?:of|in|at|for)\s+(.+)",

        # PM2.5
        r"(?:what\s+is\s+)?(?:the\s+)?pm\s*2\.?5"
        r"(?:\s+status|\s+situation|\s+forecast)?"
        r"\s+(?:of|in|at|for)\s+(.+)",

        # general forecast
        r"(?:what\s+is\s+)?(?:the\s+)?forecast"
        r"\s+(?:of|in|at|for)\s+(.+)",

        # environmental situation
        r"(?:what\s+is\s+)?(?:the\s+)?environment(?:al)?"
        r"(?:\s+status|\s+situation|\s+condition)?"
        r"\s+(?:of|in|at|for)\s+(.+)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            location = match.group(
                1
            ).strip()

            location = re.sub(
                r"[?.!]+$",
                "",
                location
            ).strip()

            if location:
                return location

    # --------------------------------------------------------
    # Patterns such as:
    #
    # "weather Wagholi"
    # "rainfall Wagholi"
    # "temperature Wagholi"
    # --------------------------------------------------------

    simple_patterns = [
        r"^(?:weather|rainfall|rain|temperature|pollution|aqi|"
        r"air\s+quality)\s+(.+)$",

        r"^(?:what\s+is\s+the\s+)?(?:weather|rainfall|rain|"
        r"temperature|pollution|aqi|air\s+quality)\s+(.+)$"
    ]

    for pattern in simple_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            location = match.group(
                1
            ).strip()

            if location:
                return location

    # --------------------------------------------------------
    # If only a location was entered
    # --------------------------------------------------------

    return text
