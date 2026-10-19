from pathlib import Path
from datetime import datetime
import os
import requests
from dotenv import load_dotenv

ROOT = Path(r"C:\final year project\AI-POLLUTION-SYSTEM")
load_dotenv(ROOT / ".env")

API_KEY = os.getenv("WEATHER_API_KEY")

CURRENT_URL = "https://api.weatherapi.com/v1/current.json"
FORECAST_URL = "https://api.weatherapi.com/v1/forecast.json"


# ============================================================
# CPCB AQI
# ============================================================

CPCB_BREAKPOINTS = {
    "pm25": [
        (0, 30, 0, 50),
        (31, 60, 51, 100),
        (61, 90, 101, 200),
        (91, 120, 201, 300),
        (121, 250, 301, 400),
        (251, 500, 401, 500),
    ],
    "pm10": [
        (0, 50, 0, 50),
        (51, 100, 51, 100),
        (101, 250, 101, 200),
        (251, 350, 201, 300),
        (351, 430, 301, 400),
        (431, 500, 401, 500),
    ],
    "no2": [
        (0, 40, 0, 50),
        (41, 80, 51, 100),
        (81, 180, 101, 200),
        (181, 280, 201, 300),
        (281, 400, 301, 400),
        (401, 800, 401, 500),
    ],
    "so2": [
        (0, 40, 0, 50),
        (41, 80, 51, 100),
        (81, 380, 101, 200),
        (381, 800, 201, 300),
        (801, 1600, 301, 400),
        (1601, 2000, 401, 500),
    ],
    "o3": [
        (0, 50, 0, 50),
        (51, 100, 51, 100),
        (101, 168, 101, 200),
        (169, 208, 201, 300),
        (209, 748, 301, 400),
        (749, 1000, 401, 500),
    ],
    "co": [
        (0.0, 1.0, 0, 50),
        (1.1, 2.0, 51, 100),
        (2.1, 10.0, 101, 200),
        (10.1, 17.0, 201, 300),
        (17.1, 34.0, 301, 400),
        (34.1, 50.0, 401, 500),
    ],
}


def interpolate(value, low_c, high_c, low_i, high_i):
    return (
        (high_i - low_i)
        / (high_c - low_c)
        * (value - low_c)
        + low_i
    )


def pollutant_sub_index(pollutant, value):
    if value is None:
        return None

    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    if value < 0:
        return None

    breakpoints = CPCB_BREAKPOINTS.get(pollutant)

    if not breakpoints:
        return None

    for low_c, high_c, low_i, high_i in breakpoints:
        if low_c <= value <= high_c:
            return round(
                interpolate(
                    value,
                    low_c,
                    high_c,
                    low_i,
                    high_i,
                ),
                1,
            )

    return 500.0


def aqi_category(aqi):
    if aqi is None:
        return "Unavailable"

    if aqi <= 50:
        return "Good"
    if aqi <= 100:
        return "Satisfactory"
    if aqi <= 200:
        return "Moderately Polluted"
    if aqi <= 300:
        return "Poor"
    if aqi <= 400:
        return "Very Poor"

    return "Severe"


def calculate_cpcb_aqi(air_quality):
    """
    Calculates a pollutant-subindex-based CPCB-style AQI.

    IMPORTANT:
    For official CPCB AQI reporting, use the required averaging
    periods and qualifying pollutant set. A single live API
    concentration is therefore labeled indicative.
    """

    values = {
        "pm25": air_quality.get("pm2_5"),
        "pm10": air_quality.get("pm10"),
        "no2": air_quality.get("no2"),
        "so2": air_quality.get("so2"),
        "co": air_quality.get("co"),
        "o3": air_quality.get("o3"),
    }

    sub_indices = {}

    for pollutant, value in values.items():
        index = pollutant_sub_index(
            pollutant,
            value
        )

        if index is not None:
            sub_indices[pollutant] = index

    if not sub_indices:
        return {
            "aqi": None,
            "category": "Unavailable",
            "sub_indices": {},
            "basis": "No usable pollutant data",
        }

    overall = max(
        sub_indices.values()
    )

    controlling = max(
        sub_indices,
        key=sub_indices.get
    )

    return {
        "aqi": round(overall, 1),
        "category": aqi_category(overall),
        "sub_indices": sub_indices,
        "controlling_pollutant": controlling,
        "basis": (
            "Pollutant sub-index calculation from available "
            "WeatherAPI pollutant concentrations; indicative "
            "when required averaging periods are unavailable."
        ),
    }


# ============================================================
# WEATHERAPI
# ============================================================

def _request(url, params):
    if not API_KEY:
        raise RuntimeError(
            "WEATHER_API_KEY is missing from .env"
        )

    params = dict(params)
    params["key"] = API_KEY

    response = requests.get(
        url,
        params=params,
        timeout=20,
    )

    response.raise_for_status()

    return response.json()


def get_weather_report(location, days=3):
    """
    Google-style environmental report:
    current conditions + hourly forecast + daily forecast +
    air quality + CPCB-style indicative AQI.
    """

    current_data = _request(
        CURRENT_URL,
        {
            "q": location,
            "aqi": "yes",
            "alerts": "yes",
        }
    )

    forecast_data = _request(
        FORECAST_URL,
        {
            "q": location,
            "days": days,
            "aqi": "yes",
            "alerts": "yes",
        }
    )

    current = current_data.get(
        "current",
        {}
    )

    current_aq = current.get(
        "air_quality",
        {}
    ) or {}

    location_data = current_data.get(
        "location",
        {}
    )

    aqi_result = calculate_cpcb_aqi(
        current_aq
    )

    current_report = {
        "last_updated": current.get(
            "last_updated"
        ),
        "temperature_c": current.get(
            "temp_c"
        ),
        "feels_like_c": current.get(
            "feelslike_c"
        ),
        "humidity": current.get(
            "humidity"
        ),
        "cloud": current.get(
            "cloud"
        ),
        "pressure_mb": current.get(
            "pressure_mb"
        ),
        "precipitation_mm": current.get(
            "precip_mm"
        ),
        "wind_kph": current.get(
            "wind_kph"
        ),
        "wind_degree": current.get(
            "wind_degree"
        ),
        "wind_direction": current.get(
            "wind_dir"
        ),
        "gust_kph": current.get(
            "gust_kph"
        ),
        "visibility_km": current.get(
            "vis_km"
        ),
        "uv": current.get(
            "uv"
        ),
        "condition": (
            current.get("condition", {})
            .get("text")
        ),
        "condition_icon": (
            current.get("condition", {})
            .get("icon")
        ),
        "is_day": current.get(
            "is_day"
        ),

        "pm2_5": current_aq.get(
            "pm2_5"
        ),
        "pm10": current_aq.get(
            "pm10"
        ),
        "no2": current_aq.get(
            "no2"
        ),
        "so2": current_aq.get(
            "so2"
        ),
        "co": current_aq.get(
            "co"
        ),
        "o3": current_aq.get(
            "o3"
        ),

        "weatherapi_us_epa_index":
            current_aq.get(
                "us-epa-index"
            ),

        "weatherapi_uk_defra_index":
            current_aq.get(
                "gb-defra-index"
            ),

        "cpcb_indicative_aqi":
            aqi_result["aqi"],

        "cpcb_indicative_category":
            aqi_result["category"],

        "aqi_controlling_pollutant":
            aqi_result.get(
                "controlling_pollutant"
            ),

        "aqi_sub_indices":
            aqi_result["sub_indices"],

        "aqi_basis":
            aqi_result["basis"],
    }

    # ========================================================
    # HOURLY FORECAST
    # ========================================================

    hourly = []

    for day in forecast_data.get(
        "forecast",
        {}
    ).get(
        "forecastday",
        []
    ):

        for hour in day.get(
            "hour",
            []
        ):

            aq = hour.get(
                "air_quality",
                {}
            ) or {}

            hourly_aqi = calculate_cpcb_aqi(
                aq
            )

            hourly.append({
                "time": hour.get(
                    "time"
                ),
                "temperature_c": hour.get(
                    "temp_c"
                ),
                "feels_like_c": hour.get(
                    "feelslike_c"
                ),
                "humidity": hour.get(
                    "humidity"
                ),
                "cloud": hour.get(
                    "cloud"
                ),
                "pressure_mb": hour.get(
                    "pressure_mb"
                ),
                "rain_probability": hour.get(
                    "chance_of_rain"
                ),
                "rain_mm": hour.get(
                    "precip_mm"
                ),
                "snow_probability": hour.get(
                    "chance_of_snow"
                ),
                "wind_kph": hour.get(
                    "wind_kph"
                ),
                "gust_kph": hour.get(
                    "gust_kph"
                ),
                "wind_direction": hour.get(
                    "wind_dir"
                ),
                "visibility_km": hour.get(
                    "vis_km"
                ),
                "uv": hour.get(
                    "uv"
                ),
                "condition": (
                    hour.get(
                        "condition",
                        {}
                    ).get(
                        "text"
                    )
                ),
                "pm2_5": aq.get(
                    "pm2_5"
                ),
                "pm10": aq.get(
                    "pm10"
                ),
                "no2": aq.get(
                    "no2"
                ),
                "so2": aq.get(
                    "so2"
                ),
                "co": aq.get(
                    "co"
                ),
                "o3": aq.get(
                    "o3"
                ),
                "cpcb_indicative_aqi":
                    hourly_aqi["aqi"],
                "cpcb_indicative_category":
                    hourly_aqi["category"],
                "weatherapi_us_epa_index":
                    aq.get(
                        "us-epa-index"
                    ),
                "weatherapi_uk_defra_index":
                    aq.get(
                        "gb-defra-index"
                    ),
            })

    # ========================================================
    # DAILY FORECAST
    # ========================================================

    daily = []

    for day_data in forecast_data.get(
        "forecast",
        {}
    ).get(
        "forecastday",
        []
    ):

        day = day_data.get(
            "day",
            {}
        )

        astro = day_data.get(
            "astro",
            {}
        )

        daily.append({
            "date": day_data.get(
                "date"
            ),
            "max_temp_c": day.get(
                "maxtemp_c"
            ),
            "min_temp_c": day.get(
                "mintemp_c"
            ),
            "avg_temp_c": day.get(
                "avgtemp_c"
            ),
            "max_wind_kph": day.get(
                "maxwind_kph"
            ),
            "total_precip_mm": day.get(
                "totalprecip_mm"
            ),
            "avg_visibility_km": day.get(
                "avgvis_km"
            ),
            "avg_humidity": day.get(
                "avghumidity"
            ),
            "chance_of_rain": day.get(
                "daily_chance_of_rain"
            ),
            "chance_of_snow": day.get(
                "daily_chance_of_snow"
            ),
            "condition": (
                day.get(
                    "condition",
                    {}
                ).get(
                    "text"
                )
            ),
            "uv": day.get(
                "uv"
            ),
            "sunrise": astro.get(
                "sunrise"
            ),
            "sunset": astro.get(
                "sunset"
            ),
            "moonrise": astro.get(
                "moonrise"
            ),
            "moonset": astro.get(
                "moonset"
            ),
            "moon_phase": astro.get(
                "moon_phase"
            ),
        })

    alerts = []

    for alert in (
        forecast_data.get(
            "alerts",
            {}
        ).get(
            "alert",
            []
        )
    ):

        alerts.append({
            "headline": alert.get(
                "headline"
            ),
            "severity": alert.get(
                "severity"
            ),
            "urgency": alert.get(
                "urgency"
            ),
            "event": alert.get(
                "event"
            ),
            "areas": alert.get(
                "areas"
            ),
            "description": alert.get(
                "desc"
            ),
            "instruction": alert.get(
                "instruction"
            ),
            "effective": alert.get(
                "effective"
            ),
            "expires": alert.get(
                "expires"
            ),
        })

    return {
        "location": {
            "name": location_data.get(
                "name"
            ),
            "region": location_data.get(
                "region"
            ),
            "country": location_data.get(
                "country"
            ),
            "latitude": location_data.get(
                "lat"
            ),
            "longitude": location_data.get(
                "lon"
            ),
            "timezone": location_data.get(
                "tz_id"
            ),
            "local_time": location_data.get(
                "localtime"
            ),
        },

        "current": current_report,

        "hourly_forecast": hourly,

        "daily_forecast": daily,

        "alerts": alerts,

        "source": "WeatherAPI",

        "generated_at":
            datetime.now().isoformat(),
    }


if __name__ == "__main__":

    location = input(
        "Location: "
    ).strip()

    try:

        report = get_weather_report(
            location,
            days=3
        )

        print("\n")
        print("=" * 80)
        print("LIVE ENVIRONMENTAL REPORT")
        print("=" * 80)

        loc = report["location"]
        cur = report["current"]

        print(
            f"Location: {loc['name']}, "
            f"{loc['region']}, "
            f"{loc['country']}"
        )

        print(
            f"Local time: {loc['local_time']}"
        )

        print("\nCURRENT WEATHER")
        print("-" * 80)

        for label, key, unit in [
            ("Temperature", "temperature_c", "C"),
            ("Feels like", "feels_like_c", "C"),
            ("Humidity", "humidity", "%"),
            ("Pressure", "pressure_mb", "mb"),
            ("Rainfall", "precipitation_mm", "mm"),
            ("Wind", "wind_kph", "km/h"),
            ("Wind direction", "wind_direction", ""),
            ("Gust", "gust_kph", "km/h"),
            ("Visibility", "visibility_km", "km"),
            ("UV", "uv", ""),
            ("Condition", "condition", ""),
        ]:

            print(
                f"{label}: {cur.get(key)} {unit}".rstrip()
            )

        print("\nAIR QUALITY")
        print("-" * 80)

        for label, key in [
            ("PM2.5", "pm2_5"),
            ("PM10", "pm10"),
            ("NO2", "no2"),
            ("SO2", "so2"),
            ("CO", "co"),
            ("O3", "o3"),
        ]:

            print(
                f"{label}: {cur.get(key)} ug/m3"
            )

        print(
            f"\nCPCB indicative AQI: "
            f"{cur.get('cpcb_indicative_aqi')}"
        )

        print(
            f"CPCB category: "
            f"{cur.get('cpcb_indicative_category')}"
        )

        print(
            f"Controlling pollutant: "
            f"{cur.get('aqi_controlling_pollutant')}"
        )

        print(
            f"US EPA index: "
            f"{cur.get('weatherapi_us_epa_index')}"
        )

        print(
            f"UK DEFRA index: "
            f"{cur.get('weatherapi_uk_defra_index')}"
        )

        print(
            "\nAQI basis:",
            cur.get("aqi_basis")
        )

        print("\nNEXT 12 HOURS")
        print("-" * 80)

        for item in report[
            "hourly_forecast"
        ][:12]:

            print(
                f"{item['time']} | "
                f"{item['temperature_c']} C | "
                f"Rain {item['rain_probability']}% | "
                f"PM2.5 {item['pm2_5']} | "
                f"AQI {item['cpcb_indicative_aqi']} | "
                f"{item['condition']}"
            )

        print("\nDAILY FORECAST")
        print("-" * 80)

        for item in report[
            "daily_forecast"
        ]:

            print(
                f"{item['date']} | "
                f"{item['min_temp_c']} - "
                f"{item['max_temp_c']} C | "
                f"Rain {item['chance_of_rain']}% | "
                f"{item['condition']}"
            )

    except Exception as exc:

        print(
            f"\nERROR: {type(exc).__name__}: {exc}"
        )
