import os
import math
import time
import pandas as pd
import requests

PROJECT_ROOT = r"C:\final year project\AI-POLLUTION-SYSTEM"

LOCATIONS_FILE = os.path.join(
    PROJECT_ROOT,
    "data",
    "processed",
    "pune_100_locations.csv"
)

STATIONS_FILE = os.path.join(
    PROJECT_ROOT,
    "data",
    "processed",
    "pune_cpcb_verified_stations.csv"
)

OUTPUT_FILE = os.path.join(
    PROJECT_ROOT,
    "data",
    "processed",
    "pune_100_locations_mapped.csv"
)

# Real monitoring locations used for mapping.
# Do NOT treat these as 100 CPCB stations.
stations = [
    ("Pashan", 18.5362, 73.7946),
    ("Shivajinagar", 18.5308, 73.8470),
    ("Pune Airport", 18.5793, 73.9089),
    ("Katraj", 18.4529, 73.8652),
    ("Hadapsar", 18.5018, 73.9275),
    ("Bhosari", 18.6350, 73.8291),
    ("Nigdi", 18.6635, 73.7668),
    ("Manjri", 18.5150, 73.9820),
    ("Girinagar", 18.4700, 73.6800),
    ("Alandi", 18.6770, 73.8980),
    ("Karve Road", 18.5126, 73.8397),
]

stations_df = pd.DataFrame(
    stations,
    columns=[
        "station_name",
        "latitude",
        "longitude"
    ]
)

stations_df.to_csv(
    STATIONS_FILE,
    index=False
)

if not os.path.exists(LOCATIONS_FILE):
    raise FileNotFoundError(
        f"Missing file: {LOCATIONS_FILE}"
    )

locations_df = pd.read_csv(
    LOCATIONS_FILE
)

if "location_name" not in locations_df.columns:
    raise ValueError(
        "pune_100_locations.csv does not contain "
        "'location_name'"
    )

headers = {
    "User-Agent":
        "AI-Pollution-System/1.0"
}

NOMINATIM_URL = (
    "https://nominatim.openstreetmap.org/search"
)


def geocode(name):

    queries = [
        f"{name}, Pune, Maharashtra, India",
        f"{name}, Maharashtra, India",
        f"{name}, India"
    ]

    for query in queries:

        try:

            r = requests.get(
                NOMINATIM_URL,
                params={
                    "q": query,
                    "format": "jsonv2",
                    "limit": 1,
                    "countrycodes": "in"
                },
                headers=headers,
                timeout=15
            )

            r.raise_for_status()

            results = r.json()

            if results:

                return (
                    float(results[0]["lat"]),
                    float(results[0]["lon"]),
                    results[0].get(
                        "display_name",
                        name
                    )
                )

        except Exception:
            pass

        time.sleep(1)

    return None, None, None


def distance_km(
    lat1,
    lon1,
    lat2,
    lon2
):

    radius = 6371.0

    p1 = math.radians(lat1)
    p2 = math.radians(lat2)

    dp = math.radians(
        lat2 - lat1
    )

    dl = math.radians(
        lon2 - lon1
    )

    a = (
        math.sin(dp / 2) ** 2
        +
        math.cos(p1)
        *
        math.cos(p2)
        *
        math.sin(dl / 2) ** 2
    )

    return (
        2
        * radius
        * math.asin(math.sqrt(a))
    )


results = []

total = len(locations_df)

for i, row in locations_df.iterrows():

    name = str(
        row["location_name"]
    ).strip()

    print(
        f"[{i + 1}/{total}] {name}"
    )

    lat, lon, display = geocode(
        name
    )

    record = row.to_dict()

    record["latitude"] = lat
    record["longitude"] = lon
    record["resolved_name"] = display

    if lat is None:

        record["nearest_cpcb_station"] = None
        record["distance_to_station_km"] = None

        print(
            "  WARNING: location not geocoded"
        )

    else:

        nearest_name = None
        nearest_distance = float("inf")

        for _, station in stations_df.iterrows():

            d = distance_km(
                lat,
                lon,
                station["latitude"],
                station["longitude"]
            )

            if d < nearest_distance:

                nearest_distance = d
                nearest_name = station[
                    "station_name"
                ]

        record[
            "nearest_cpcb_station"
        ] = nearest_name

        record[
            "distance_to_station_km"
        ] = round(
            nearest_distance,
            3
        )

        print(
            f"  -> {nearest_name} "
            f"({nearest_distance:.2f} km)"
        )

    results.append(
        record
    )

    time.sleep(1)


mapped_df = pd.DataFrame(
    results
)

mapped_df.to_csv(
    OUTPUT_FILE,
    index=False
)

print()
print("=" * 70)
print("MAPPING COMPLETE")
print("=" * 70)
print(
    "Total locations:",
    len(mapped_df)
)
print(
    "Mapped:",
    mapped_df[
        "nearest_cpcb_station"
    ].notna().sum()
)
print(
    "Unmapped:",
    mapped_df[
        "nearest_cpcb_station"
    ].isna().sum()
)
print()
print(
    "Created:",
    OUTPUT_FILE
)
