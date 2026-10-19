
from pathlib import Path
import sys

ROOT = Path(
    r"C:\final year project\AI-POLLUTION-SYSTEM"
)

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT)
    )

from backend.services.location_resolver import (
    resolve_location
)

from backend.services.weather_intelligence import (
    get_weather_report
)


QUESTIONS = [
    "What is the weather condition in Beed?",
    "What is the current weather in Mumbai?",
    "What is the AQI of Delhi?",
    "What is rainfall in Nashik?",
    "What is the temperature in Bengaluru?",
    "What is the current weather in Hyderabad?",
    "What is the air quality in Nagpur?",
    "Give me the weather forecast for Chennai.",
    "What are the current conditions in Kolkata?",
    "What is the weather in Jaipur?",
    "What is rainfall in Guwahati?",
    "What is the current environmental condition in Ahmedabad?",
]


def main():

    total = len(
        QUESTIONS
    )

    location_ok = 0
    coordinates_ok = 0
    weather_ok = 0
    air_quality_ok = 0
    forecast_ok = 0

    print("=" * 80)
    print("HARD INDIA WEATHER / AIR QUALITY TEST")
    print("=" * 80)

    for index, question in enumerate(
        QUESTIONS,
        start=1
    ):

        print(
            f"\nTEST {index}: {question}"
        )
        print("-" * 80)

        try:

            location = resolve_location(
                question
            )

            print(
                "Resolved location:",
                location
            )

            if location:
                location_ok += 1

            report = get_weather_report(
                location
            )

            loc = report.get(
                "location",
                {}
            )

            current = report.get(
                "current",
                {}
            )

            lat = loc.get(
                "latitude"
            )

            lon = loc.get(
                "longitude"
            )

            if lat is not None and lon is not None:
                coordinates_ok += 1

            if (
                current.get(
                    "temperature_c"
                ) is not None
            ):
                weather_ok += 1

            if (
                current.get(
                    "pm2_5"
                ) is not None
                or current.get(
                    "cpcb_indicative_aqi"
                ) is not None
            ):
                air_quality_ok += 1

            hourly = report.get(
                "hourly_forecast",
                []
            )

            if hourly:
                forecast_ok += 1

            print(
                "Location:",
                loc.get("name")
            )

            print(
                "Region:",
                loc.get("region")
            )

            print(
                "Coordinates:",
                lat,
                ",",
                lon
            )

            print(
                "Temperature:",
                current.get("temperature_c")
            )

            print(
                "Rainfall:",
                current.get("precipitation_mm")
            )

            print(
                "PM2.5:",
                current.get("pm2_5")
            )

            print(
                "PM10:",
                current.get("pm10")
            )

            print(
                "Indicative AQI:",
                current.get(
                    "cpcb_indicative_aqi"
                )
            )

            print(
                "AQI Category:",
                current.get(
                    "cpcb_indicative_category"
                )
            )

            print(
                "Hourly forecast records:",
                len(hourly)
            )

        except Exception as exc:

            print(
                "ERROR:",
                type(exc).__name__,
                str(exc)
            )

    print("\n")
    print("=" * 80)
    print("FINAL RESULTS")
    print("=" * 80)

    print(
        f"Location resolution: "
        f"{location_ok}/{total} = "
        f"{location_ok / total * 100:.2f}%"
    )

    print(
        f"Coordinates: "
        f"{coordinates_ok}/{total} = "
        f"{coordinates_ok / total * 100:.2f}%"
    )

    print(
        f"Weather data: "
        f"{weather_ok}/{total} = "
        f"{weather_ok / total * 100:.2f}%"
    )

    print(
        f"Air-quality data: "
        f"{air_quality_ok}/{total} = "
        f"{air_quality_ok / total * 100:.2f}%"
    )

    print(
        f"Forecast data: "
        f"{forecast_ok}/{total} = "
        f"{forecast_ok / total * 100:.2f}%"
    )

    overall = (
        location_ok
        + coordinates_ok
        + weather_ok
        + air_quality_ok
        + forecast_ok
    )

    maximum = total * 5

    print(
        f"Overall environment integration: "
        f"{overall}/{maximum} = "
        f"{overall / maximum * 100:.2f}%"
    )

    print("=" * 80)


if __name__ == "__main__":
    main()
