import sys
from pathlib import Path

# Add project root so "backend" can always be imported
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.india_environment import get_environment_for_user
from backend.services.intelligence_engine import build_intelligence


def main():
    question = input("\nAsk your environmental question: ").strip()

    if not question:
        question = "What is the current pollution condition in Pune?"

    print("\n" + "=" * 70)
    print("TESTING ENVIRONMENT ENGINE")
    print("=" * 70)

    environment = get_environment_for_user(question)

    if not isinstance(environment, dict):
        print("ERROR: Environment service did not return a dictionary.")
        return

    location_data = environment.get("location", {}) or {}
    location = (
        location_data.get("requested_location")
        or location_data.get("name")
        or "Pune"
    )

    print(f"Location: {location}")
    print(f"Environment keys: {list(environment.keys())}")

    print("\n" + "=" * 70)
    print("TESTING INTELLIGENCE ENGINE")
    print("=" * 70)

    intelligence = build_intelligence(
        environment=environment,
        location=location,
    )

    if not isinstance(intelligence, dict):
        print("ERROR: Intelligence engine did not return a dictionary.")
        return

    print(f"Intelligence keys: {list(intelligence.keys())}")

    print("\n--- Environmental Score ---")
    print(intelligence.get("environmental_score"))

    print("\n--- Source Indicators ---")
    print(intelligence.get("source_indicators"))

    print("\n--- Anomaly ---")
    print(intelligence.get("anomaly"))

    print("\n--- Hotspot ---")
    print(intelligence.get("hotspot"))

    print("\n--- SHAP ---")
    print(intelligence.get("shap"))

    print("\n--- Intervention Simulation ---")
    print(intelligence.get("intervention_simulation"))

    print("\n" + "=" * 70)
    print("FULL INTELLIGENCE TEST PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()
