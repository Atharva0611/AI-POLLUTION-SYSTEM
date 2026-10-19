from backend.services.pune_locations import resolve_pune_location

tests = [
    "Pune",
    "Alandi",
    "Alandi Pune IITM",
    "Bhosari",
    "Bhumkar Nagar",
    "Dhankawadi",
    "Hadapsar",
    "Karve Road",
    "Karve Road Pune MPCB",
    "Katraj",
    "Katraj Dairy",
    "Pashan",
    "Panchawati_Pashan",
    "Revenue Colony",
    "Shivajinagar",
    "SPPU",
    "Savitribai Phule Pune University",
    "Transport Nagar",
    "Nigdi",
]

print("=" * 70)
print("PUNE LOCATION REGISTRY TEST")
print("=" * 70)

for location in tests:
    result = resolve_pune_location(location)

    if result:
        print(
            f"{location:<45} -> "
            f"{result['canonical_location']}"
        )
    else:
        print(
            f"{location:<45} -> NOT FOUND"
        )

print("=" * 70)
print("TEST COMPLETE")
print("=" * 70)
