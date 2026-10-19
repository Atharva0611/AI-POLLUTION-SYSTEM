from backend.services.india_environment import get_environment_for_user

QUESTIONS = [
    "What is pollution status of Pune?",
    "What is pollution status of Alandi?",
    "What is pollution status of Bhosari?",
    "What is pollution status of Bhumkar Nagar?",
    "What is pollution status of Dhankawadi?",
    "What is pollution status of Hadapsar?",
    "What is pollution status of Karve Road?",
    "What is pollution status of Katraj Dairy?",
    "What is pollution status of Pashan?",
    "What is pollution status of Shivajinagar?",
    "What is pollution status of SPPU?",
    "What is pollution status of Nigdi?",
]

print("=" * 90)
print("ALL PUNE LOCATIONS - ENVIRONMENT ENGINE TEST")
print("=" * 90)

for question in QUESTIONS:
    print("\nQUESTION:", question)

    try:
        result = get_environment_for_user(question)

        location = result.get("location") or {}
        current = result.get("current") or {}

        print("Status              :", result.get("status"))
        print("Requested location  :", location.get("requested_location"))
        print("Resolved location   :", location.get("resolved_location"))
        print("Canonical location  :", location.get("canonical_location"))
        print("Location type       :", location.get("location_type"))
        print("WeatherAPI location :", location.get("weatherapi_location"))

        print("PM2.5               :", current.get("pm2_5"))
        print("PM10                :", current.get("pm10"))
        print("Temperature         :", current.get("temperature_c"))

    except Exception as exc:
        print("ERROR               :", type(exc).__name__)
        print("MESSAGE             :", str(exc))

print("\n" + "=" * 90)
print("TEST COMPLETE")
print("=" * 90)
