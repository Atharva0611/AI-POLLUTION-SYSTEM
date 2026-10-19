from backend.services.pune_locations import (
    resolve_pune_location,
    get_all_pune_stations,
)

print("=" * 80)
print("PUNE LOCATION REGISTRY - FULL TEST")
print("=" * 80)

tests = [
    "Pune",
    "Alandi",
    "Alandi Pune IITM",
    "Bhosari",
    "Bhosari Pune",
    "Bhumkar Nagar",
    "Dhankawadi",
    "Hadapsar",
    "Karve Road",
    "Karve Road Pune MPCB",
    "Katraj",
    "Katraj Dairy",
    "Pashan",
    "Panchawati",
    "Panchawati_Pashan",
    "Panchawati Pashan Pune",
    "Revenue Colony",
    "Revenue Colony Shivajinagar",
    "Shivajinagar",
    "SPPU",
    "Pune University",
    "Savitribai Phule Pune University",
    "Transport Nagar",
    "Transport Nagar Nigdi",
    "Nigdi",
]

failed = []

for question in tests:
    result = resolve_pune_location(question)

    if result:
        print(
            f"OK   | {question:<45} | "
            f"{result['canonical_location']:<35} | "
            f"{result['station_name']}"
        )
    else:
        print(
            f"FAIL | {question:<45} | NOT RESOLVED"
        )
        failed.append(question)

print()
print("=" * 80)
print("CANONICAL STATIONS")
print("=" * 80)

stations = get_all_pune_stations()

for station in stations:
    print(
        f"{station['canonical_location']:<35} | "
        f"{station['latitude']:<12} | "
        f"{station['longitude']:<12} | "
        f"{station['station_name']}"
    )

print()
print("=" * 80)
print(f"TOTAL CANONICAL STATIONS : {len(stations)}")
print(f"TOTAL TEST CASES         : {len(tests)}")
print(f"FAILED TESTS             : {len(failed)}")
print("=" * 80)

if failed:
    print("\nFAILED LOCATIONS:")
    for item in failed:
        print("-", item)
else:
    print("\nALL LOCATION ALIASES PASSED")

print("=" * 80)
