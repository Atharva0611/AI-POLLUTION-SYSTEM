import os
import re
import requests
from typing import Dict, Any, Optional
from dotenv import load_dotenv


# ============================================================
# CONFIG
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

WEATHER_CURRENT_URL = (
    "https://api.weatherapi.com/v1/current.json"
)

NOMINATIM_URL = (
    "https://nominatim.openstreetmap.org/search"
)


# ============================================================
# ERROR
# ============================================================

class LiveAQIError(Exception):
    pass


# ============================================================
# HELPERS
# ============================================================

def to_float(value):

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value):

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def extract_location(question: str) -> str:

    if not question or not question.strip():

        raise LiveAQIError(
            "Please provide a location."
        )

    text = question.strip()

    patterns = [
        r"(?:live|current|real[- ]?time)?\s*aqi\s+(?:of|in|at|for)\s+(.+)",
        r"(?:live|current|real[- ]?time)?\s*air\s+quality\s+(?:of|in|at|for)\s+(.+)",
        r"(?:live|current)?\s*pollution\s+(?:of|in|at|for)\s+(.+)",
        r"(?:live|current)?\s*weather\s+(?:of|in|at|for)\s+(.+)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE
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

    # User typed only a location
    location = re.sub(
        r"[?.!]+$",
        "",
        text
    ).strip()

    if location:
        return location

    raise LiveAQIError(
        "Could not determine the location."
    )


# ============================================================
# NOMINATIM LOCATION RESOLUTION
# ============================================================

def resolve_with_nominatim(
    query: str
) -> Dict[str, Any]:

    headers = {
        "User-Agent":
            "AI-Pollution-System/1.0"
    }

    search_queries = [
        f"{query}, Pune, Maharashtra, India",
        f"{query}, Maharashtra, India",
        f"{query}, India",
        query,
    ]

    for search_query in search_queries:

        try:

            response = requests.get(
                NOMINATIM_URL,
                params={
                    "q": search_query,
                    "format": "jsonv2",
                    "limit": 10,
                    "countrycodes": "in",
                    "addressdetails": 1,
                },
                headers=headers,
                timeout=15,
            )

            response.raise_for_status()

            results = response.json()

            if not results:
                continue

            query_lower = query.lower().strip()

            # ------------------------------------------------
            # Prefer exact neighbourhood/suburb/name
            # ------------------------------------------------

            best = None
            best_score = -1

            for item in results:

                name = str(
                    item.get("name", "")
                ).lower().strip()

                display = str(
                    item.get("display_name", "")
                ).lower()

                address = item.get(
                    "address",
                    {}
                )

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

                city_district = str(
                    address.get(
                        "city_district",
                        ""
                    )
                ).lower()

                score = 0

                if name == query_lower:
                    score += 1000

                if neighbourhood == query_lower:
                    score += 900

                if suburb == query_lower:
                    score += 800

                if query_lower in name:
                    score += 300

                if query_lower in neighbourhood:
                    score += 250

                if query_lower in suburb:
                    score += 200

                if query_lower in city_district:
                    score += 150

                if query_lower in display:
                    score += 100

                # Prefer Pune-area results
                if "pune" in display:
                    score += 50

                if score > best_score:

                    best_score = score
                    best = item

            if best:

                address = best.get(
                    "address",
                    {}
                )

                latitude = to_float(
                    best.get("lat")
                )

                longitude = to_float(
                    best.get("lon")
                )

                if latitude is None or longitude is None:
                    continue

                return {
                    "requested_location": query,

                    "resolved_name": (
                        best.get("name")
                        or query
                    ),

                    "display_name": (
                        best.get(
                            "display_name"
                        )
                        or query
                    ),

                    "latitude": latitude,

                    "longitude": longitude,

                    "region": (
                        address.get(
                            "state"
                        )
                        or "Maharashtra"
                    ),

                    "country": (
                        address.get(
                            "country"
                        )
                        or "India"
                    ),

                    "source": "Nominatim",
                }

        except requests.RequestException:
            continue

    raise LiveAQIError(
        f"Could not geocode '{query}'."
    )


# ============================================================
# WEATHERAPI CURRENT AIR QUALITY
# ============================================================

def get_weatherapi_current(
    latitude: float,
    longitude: float
) -> Dict[str, Any]:

    if not WEATHER_API_KEY:

        raise LiveAQIError(
            "WEATHER_API_KEY is missing from .env"
        )

    response = requests.get(
        WEATHER_CURRENT_URL,
        params={
            "key": WEATHER_API_KEY,
            "q": f"{latitude},{longitude}",
            "aqi": "yes",
        },
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    if "error" in data:

        raise LiveAQIError(
            data.get(
                "error",
                {}
            ).get(
                "message",
                "WeatherAPI error"
            )
        )

    location_data = data.get(
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
        raise LiveAQIError(
            "WeatherAPI returned no current data."
        )

    if not air:
        raise LiveAQIError(
            "WeatherAPI returned no air-quality data."
        )

    wind_kph = to_float(
        current.get("wind_kph")
    )

    return {
        "weatherapi_name": location_data.get(
            "name"
        ),

        "weatherapi_region": location_data.get(
            "region"
        ),

        "weatherapi_country": location_data.get(
            "country"
        ),

        "latitude": to_float(
            location_data.get("lat")
        ),

        "longitude": to_float(
            location_data.get("lon")
        ),

        "pm2_5": to_float(
            air.get("pm2_5")
        ),

        "pm10": to_float(
            air.get("pm10")
        ),

        "no2": to_float(
            air.get("no2")
        ),

        "so2": to_float(
            air.get("so2")
        ),

        "co": to_float(
            air.get("co")
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

        "temperature_c": to_float(
            current.get("temp_c")
        ),

        "humidity": to_float(
            current.get("humidity")
        ),

        "wind_speed_kph": wind_kph,

        "wind_speed_ms": (
            wind_kph / 3.6
            if wind_kph is not None
            else None
        ),

        "wind_direction": current.get(
            "wind_dir"
        ),

        "wind_degree": to_float(
            current.get("wind_degree")
        ),

        "rainfall_mm": to_float(
            current.get("precip_mm")
        ),

        "last_updated": current.get(
            "last_updated"
        ),

        "last_updated_epoch": to_int(
            current.get("last_updated_epoch")
        ),

        "source": "WeatherAPI",
        "live": True,
    }


# ============================================================
# MAIN FUNCTION
# ============================================================

def get_live_air_quality(
    question_or_location: str
) -> Dict[str, Any]:

    # --------------------------------------------------------
    # User input
    # --------------------------------------------------------

    requested_location = extract_location(
        question_or_location
    )

    # --------------------------------------------------------
    # Resolve exact neighbourhood/location first
    # --------------------------------------------------------

    resolved = resolve_with_nominatim(
        requested_location
    )

    # --------------------------------------------------------
    # Query WeatherAPI using coordinates
    # --------------------------------------------------------

    live = get_weatherapi_current(
        resolved["latitude"],
        resolved["longitude"]
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Display the USER'S requested location.
    # Do not replace Kharadi with Pune just because
    # WeatherAPI's response name is Pune.
    # --------------------------------------------------------

    return {
        "requested_location": requested_location,

        "location": requested_location,

        "resolved_name": resolved[
            "resolved_name"
        ],

        "display_name": resolved[
            "display_name"
        ],

        "region": resolved[
            "region"
        ],

        "country": resolved[
            "country"
        ],

        "latitude": resolved[
            "latitude"
        ],

        "longitude": resolved[
            "longitude"
        ],

        "pm2_5": live[
            "pm2_5"
        ],

        "pm10": live[
            "pm10"
        ],

        "no2": live[
            "no2"
        ],

        "so2": live[
            "so2"
        ],

        "co": live[
            "co"
        ],

        "o3": live[
            "o3"
        ],

        "us_epa_index": live[
            "us_epa_index"
        ],

        "uk_defra_index": live[
            "uk_defra_index"
        ],

        "temperature_c": live[
            "temperature_c"
        ],

        "humidity": live[
            "humidity"
        ],

        "wind_speed_kph": live[
            "wind_speed_kph"
        ],

        "wind_speed_ms": live[
            "wind_speed_ms"
        ],

        "wind_direction": live[
            "wind_direction"
        ],

        "wind_degree": live[
            "wind_degree"
        ],

        "rainfall_mm": live[
            "rainfall_mm"
        ],

        "last_updated": live[
            "last_updated"
        ],

        "location_resolution_source": (
            resolved["source"]
        ),

        "weatherapi_location_name": live[
            "weatherapi_name"
        ],

        "source": "WeatherAPI",
        "live": True,
    }


# ============================================================
# FORMAT
# ============================================================

def format_air_quality(
    data: Dict[str, Any]
) -> str:

    return (
        f"Live air quality for "
        f"{data['requested_location']}.\n\n"

        f"Resolved location: "
        f"{data['display_name']}\n"

        f"Coordinates: "
        f"{data['latitude']}, "
        f"{data['longitude']}\n\n"

        f"PM2.5: {data['pm2_5']} µg/m³\n"
        f"PM10: {data['pm10']} µg/m³\n"
        f"NO₂: {data['no2']} µg/m³\n"
        f"SO₂: {data['so2']} µg/m³\n"
        f"CO: {data['co']} µg/m³\n"
        f"O₃: {data['o3']} µg/m³\n\n"

        f"US EPA Index: "
        f"{data['us_epa_index']}\n"

        f"UK DEFRA Index: "
        f"{data['uk_defra_index']}\n\n"

        f"Temperature: "
        f"{data['temperature_c']} °C\n"

        f"Humidity: "
        f"{data['humidity']}%\n"

        f"Wind: "
        f"{data['wind_speed_kph']} km/h\n"

        f"Rainfall: "
        f"{data['rainfall_mm']} mm\n\n"

        f"Last updated: "
        f"{data['last_updated']}\n\n"

        f"Location resolver: "
        f"{data['location_resolution_source']}\n"

        f"Air-quality source: WeatherAPI"
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    question = input(
        "Enter any location/AQI question: "
    ).strip()

    try:

        result = get_live_air_quality(
            question
        )

        print(
            "\n" + format_air_quality(
                result
            )
        )

    except Exception as exc:

        print(
            "\nERROR:",
            exc
        )
