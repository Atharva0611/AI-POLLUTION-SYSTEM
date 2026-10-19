from backend.services.india_environment import get_environment_for_user

questions = [
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

print("=" * 80)
print("CURRENT ENVIRONMENT LOCATION TEST")
print("=" * 80)

for question in questions:
    try:
        result = get_environment_for_user(question)

        location = (
            result.get("location", {})
            if isinstance(result, dict)
            else {}
        )

        print()
        print("QUESTION :", question)
        print(
            "REQUESTED:",
            location.get("requested_location")
        )
        print(
            "RESOLVED :",
            location.get("resolved_location")
        )
        print(
            "STATUS   :",
            result.get("status")
        )

    except Exception as exc:
        print()
        print("QUESTION :", question)
        print("ERROR    :", type(exc).__name__, str(exc))

print()
print("=" * 80)
print("TEST COMPLETE")
print("=" * 80)
