import os
import requests

from dotenv import load_dotenv


# Project .env
PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".."
    )
)

ENV_FILE = os.path.join(
    PROJECT_ROOT,
    ".env"
)

load_dotenv(ENV_FILE)


BASE_URL = (
    "https://api.weatherapi.com/v1/current.json"
)


def get_current_weather(
    location="Pune"
):
    """
    Get current weather from WeatherAPI.
    """

    api_key = os.getenv(
        "WEATHER_API_KEY"
    )

    if not api_key:
        raise ValueError(
            "WEATHER_API_KEY not found in .env"
        )

    response = requests.get(
        BASE_URL,
        params={
            "key": api_key,
            "q": location,
            "aqi": "no"
        },
        timeout=15
    )

    response.raise_for_status()

    data = response.json()

    current = data["current"]

    return {
        "location": data["location"]["name"],
        "latitude": data["location"]["lat"],
        "longitude": data["location"]["lon"],
        "temperature": current["temp_c"],
        "humidity": current["humidity"],
        "wind_speed_kmh": current["wind_kph"],
        "wind_speed_ms": current["wind_kph"] / 3.6,
        "wind_direction": current["wind_degree"],
        "rainfall": current["precip_mm"],
        "pressure": current["pressure_mb"],
        "condition": current["condition"]["text"],
        "last_updated": current["last_updated"]
    }


if __name__ == "__main__":

    print(
        "\n=== REAL-TIME WEATHER TEST ==="
    )

    weather = get_current_weather(
        "Pune"
    )

    for key, value in weather.items():
        print(
            f"{key}: {value}"
        )