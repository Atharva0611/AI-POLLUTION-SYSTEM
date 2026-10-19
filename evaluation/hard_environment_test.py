from pathlib import Path
import sys

# Add project root to Python import path
ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.intent_router import classify_intent
from backend.services.location_resolver import resolve_location
from backend.services.india_environment import get_environment_for_user
from backend.agents.final_agent import app


QUESTIONS = [

    "What is the current weather, PM2.5, AQI and rainfall situation in Wagholi?",

    "How are temperature, humidity, wind speed and air quality behaving in Kharadi right now?",

    "What is the current PM2.5 and indicative AQI in Hadapsar, and what is the rainfall status?",

    "Is the air quality in Wakad currently poor, and what are the current PM2.5 and PM10 values?",

    "Give me the current environmental conditions in Alandi including AQI, pollutants and weather.",

    "What is happening with pollution, rainfall and wind conditions in Baner right now?",

    "For Viman Nagar, give me the current PM2.5, PM10, AQI, temperature and humidity.",

    "How are the current weather conditions affecting pollution in Hinjawadi?",

    "Give me the current environmental situation in Pashan including AQI and rainfall.",

    "For SPPU, give me the pollution conditions, indicative AQI and current weather.",

    "Is PM2.5 elevated in Kothrud right now and what is the corresponding indicative AQI?",

    "Give me a complete live environmental summary for Magarpatta including AQI and rainfall.",
]


def check():

    total = len(QUESTIONS)

    routing_ok = 0
    location_ok = 0
    environment_ok = 0
    aqi_ok = 0
    final_aqi_ok = 0

    print("=" * 80)
    print("HARD ENVIRONMENT + AQI TEST")
    print("=" * 80)

    for number, question in enumerate(QUESTIONS, start=1):

        print(f"\nTEST {number}")
        print("-" * 80)
        print(question)

        try:
            intent = classify_intent(question)
            location = resolve_location(question)

            if intent == "environment":
                routing_ok += 1

            if location:
                location_ok += 1

            environment = get_environment_for_user(
                location or question
            )

            if isinstance(environment, dict):
                environment_ok += 1

            current = environment.get(
                "current",
                {}
            )

            aqi = current.get("aqi")
            aqi_category = current.get(
                "aqi_category"
            )

            if aqi is not None and aqi_category:
                aqi_ok += 1

            graph_result = app.invoke(
                {
                    "question": question
                }
            )

            final_answer = graph_result.get(
                "final_answer",
                ""
            )

            if "AQI" in final_answer.upper():
                final_aqi_ok += 1

            print(f"Intent: {intent}")
            print(f"Location: {location}")
            print(f"AQI: {aqi}")
            print(f"AQI Category: {aqi_category}")

            print(
                "Final answer contains AQI:",
                "YES" if "AQI" in final_answer.upper()
                else "NO"
            )

        except Exception as exc:

            print(
                f"ERROR: {type(exc).__name__}: {exc}"
            )

    print("\n")
    print("=" * 80)
    print("FINAL TEST RESULTS")
    print("=" * 80)

    print(
        f"Routing accuracy: "
        f"{routing_ok}/{total} = "
        f"{routing_ok / total * 100:.2f}%"
    )

    print(
        f"Location extraction: "
        f"{location_ok}/{total} = "
        f"{location_ok / total * 100:.2f}%"
    )

    print(
        f"Environment response: "
        f"{environment_ok}/{total} = "
        f"{environment_ok / total * 100:.2f}%"
    )

    print(
        f"AQI data availability: "
        f"{aqi_ok}/{total} = "
        f"{aqi_ok / total * 100:.2f}%"
    )

    print(
        f"AQI displayed in LangGraph: "
        f"{final_aqi_ok}/{total} = "
        f"{final_aqi_ok / total * 100:.2f}%"
    )

    overall = (
        routing_ok
        + location_ok
        + environment_ok
        + aqi_ok
        + final_aqi_ok
    )

    maximum = total * 5

    print(
        f"Overall integration pass rate: "
        f"{overall}/{maximum} = "
        f"{overall / maximum * 100:.2f}%"
    )

    print("=" * 80)


if __name__ == "__main__":
    check()
