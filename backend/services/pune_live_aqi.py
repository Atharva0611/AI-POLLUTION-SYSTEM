import os
import pandas as pd
from dotenv import load_dotenv

from backend.services.live_aqi_service import get_live_air_quality


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".."
    )
)


# ============================================================
# FILE PATHS
# ============================================================

LOCATION_FILE = os.path.join(
    PROJECT_ROOT,
    "data",
    "processed",
    "pune_100_locations.csv"
)

OUTPUT_FILE = os.path.join(
    PROJECT_ROOT,
    "data",
    "processed",
    "pune_100_live_aqi.csv"
)


# ============================================================
# LOAD ENV
# ============================================================

load_dotenv(
    os.path.join(
        PROJECT_ROOT,
        ".env"
    )
)


# ============================================================
# LOAD LOCATIONS
# ============================================================

def load_locations():

    if not os.path.exists(LOCATION_FILE):
        raise FileNotFoundError(
            f"Location file not found:\n{LOCATION_FILE}"
        )

    df = pd.read_csv(
        LOCATION_FILE
    )

    if "location_name" not in df.columns:
        raise ValueError(
            "location_name column is missing."
        )

    return df


# ============================================================
# GET ONE LOCATION
# ============================================================

def get_one_location(location_name):

    try:

        data = get_live_air_quality(
            location_name
        )

        return {
            "requested_location": location_name,
            "location": data.get("location"),
            "region": data.get("region"),
            "country": data.get("country"),
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),

            "pm2_5": data.get("pm2_5"),
            "pm10": data.get("pm10"),
            "no2": data.get("no2"),
            "so2": data.get("so2"),
            "co": data.get("co"),
            "o3": data.get("o3"),

            "temperature_c": data.get(
                "temperature_c"
            ),

            "humidity": data.get(
                "humidity"
            ),

            "wind_speed_kph": data.get(
                "wind_speed_kph"
            ),

            "rainfall_mm": data.get(
                "rainfall_mm"
            ),

            "us_epa_index": data.get(
                "us_epa_index"
            ),

            "uk_defra_index": data.get(
                "uk_defra_index"
            ),

            "last_updated": data.get(
                "last_updated"
            ),

            "source": "WeatherAPI",
            "live": True,
            "success": True,
            "error": ""
        }

    except Exception as exc:

        return {
            "requested_location": location_name,
            "location": None,
            "region": None,
            "country": None,
            "latitude": None,
            "longitude": None,

            "pm2_5": None,
            "pm10": None,
            "no2": None,
            "so2": None,
            "co": None,
            "o3": None,

            "temperature_c": None,
            "humidity": None,
            "wind_speed_kph": None,
            "rainfall_mm": None,

            "us_epa_index": None,
            "uk_defra_index": None,

            "last_updated": None,

            "source": "WeatherAPI",
            "live": False,
            "success": False,
            "error": str(exc)
        }


# ============================================================
# GET ALL 100 LOCATIONS
# ============================================================

def get_all_locations():

    locations = load_locations()

    results = []

    total = len(
        locations
    )

    print(
        f"\nTotal locations: {total}"
    )

    print(
        "\nStarting live AQI collection...\n"
    )

    for index, row in locations.iterrows():

        location_name = str(
            row["location_name"]
        ).strip()

        print(
            f"[{index + 1}/{total}] "
            f"{location_name}"
        )

        result = get_one_location(
            location_name
        )

        results.append(
            result
        )

        if result["success"]:

            print(
                f"    PM2.5: {result['pm2_5']}"
            )

        else:

            print(
                f"    ERROR: {result['error']}"
            )

    return pd.DataFrame(
        results
    )


# ============================================================
# SAVE
# ============================================================

def save_results():

    df = get_all_locations()

    os.makedirs(
        os.path.dirname(OUTPUT_FILE),
        exist_ok=True
    )

    df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print(
        "\n=============================================="
    )

    print(
        "LIVE AQI COLLECTION COMPLETED"
    )

    print(
        "=============================================="
    )

    print(
        f"Rows saved: {len(df)}"
    )

    print(
        f"Output file:\n{OUTPUT_FILE}"
    )

    print(
        "\nSuccessful:",
        int(df["success"].sum())
    )

    print(
        "Failed:",
        int((~df["success"]).sum())
    )

    print(
        "\nFirst 10 results:"
    )

    print(
        df.head(10).to_string(
            index=False
        )
    )


# ============================================================
# TEST ONE LOCATION
# ============================================================

def test_one():

    result = get_one_location(
        "Hadapsar"
    )

    print(
        "\n=============================================="
    )

    print(
        "LIVE AQI TEST"
    )

    print(
        "=============================================="
    )

    for key, value in result.items():

        print(
            f"{key}: {value}"
        )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print(
        "1 = Test Hadapsar"
    )

    print(
        "2 = Fetch all Pune locations"
    )

    choice = input(
        "\nChoose 1 or 2: "
    ).strip()

    if choice == "1":

        test_one()

    elif choice == "2":

        save_results()

    else:

        print(
            "Invalid choice."
        )
