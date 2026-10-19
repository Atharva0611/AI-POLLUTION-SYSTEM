import os
import re
import json
import pandas as pd


ROOT = r"C:\final year project\AI-POLLUTION-SYSTEM"

LOCATION_FILE = os.path.join(
    ROOT,
    "data",
    "processed",
    "pune_100_locations.csv"
)

OUTPUT_FILE = os.path.join(
    ROOT,
    "backend",
    "services",
    "intent_matrix.json"
)


# ============================================================
# POLICY COMMAND MATRIX
# ============================================================

POLICY_COMMANDS = [

    # Definitions / knowledge
    "what is",
    "what does",
    "what do you mean",
    "stands for",
    "meaning of",
    "define",
    "definition of",
    "explain",
    "difference between",
    "role of",
    "purpose of",
    "how does",
    "why does",
    "why is",

    # CPCB / government
    "cpcb",
    "cpcb guidelines",
    "cpcb standards",
    "cpcb measures",
    "cpcb rules",
    "ncap",
    "national clean air programme",
    "government policy",
    "government measures",
    "action plan",
    "air quality standards",
    "ambient air quality standards",
    "environmental rules",
    "environmental policy",

    # Pollution control
    "pollution control",
    "pollution control measures",
    "air pollution control",
    "air pollution control measures",
    "emission control",
    "emission control measures",
    "mitigation measures",
    "pollution mitigation",
    "control measures",
    "what measures",
    "which measures",
    "measures to reduce",
    "measures for reducing",
    "how to reduce pollution",
    "how can pollution be reduced",
    "how can air pollution be controlled",
    "what should be done",
    "what should we do",
    "what action should be taken",
    "what measures should be taken",
    "what precautions should be taken",

    # Specific pollution sources
    "road dust",
    "road dust pollution",
    "dust pollution",
    "dust control",
    "construction dust",
    "construction pollution",
    "construction and demolition",
    "vehicle pollution",
    "vehicular pollution",
    "traffic pollution",
    "industrial pollution",
    "industrial emissions",
    "industrial emission control",

    # Environmental combinations
    "heavy rainfall and high pollution",
    "high pollution and heavy rainfall",
    "high pollution and high temperature",
    "high temperature and high pollution",
    "low wind and high pollution",
    "high humidity and pollution",
]


# ============================================================
# LOCATION COMMAND MATRIX
# ============================================================

LOCATION_COMMANDS = [
    # Air quality
    "aqi of",
    "aqi in",
    "aqi at",
    "air quality of",
    "air quality in",
    "air quality at",
    "pollution of",
    "pollution in",
    "pollution at",
    "current pollution in",
    "current pollution of",
    "live pollution in",
    "live pollution of",

    # PM
    "pm2.5 of",
    "pm2.5 in",
    "pm25 of",
    "pm25 in",
    "pm10 of",
    "pm10 in",

    # Weather
    "weather of",
    "weather in",
    "weather at",
    "temperature of",
    "temperature in",
    "temperature at",
    "rainfall of",
    "rainfall in",
    "rainfall at",
    "rain of",
    "rain in",
    "rain at",
    "humidity of",
    "humidity in",
    "humidity at",
    "wind speed of",
    "wind speed in",
    "wind speed at",
    "pressure of",
    "pressure in",
    "visibility of",
    "visibility in",

    # Forecast
    "forecast for",
    "forecast of",
    "forecast in",
    "forecast at",
    "predict pm2.5 for",
    "predict pm25 for",
    "pm2.5 forecast for",
    "pm25 forecast for",
    "weather forecast for",
    "rain forecast for",
    "temperature forecast for",

    # Analysis
    "anomaly in",
    "anomaly at",
    "anomaly of",
    "hotspot in",
    "hotspots in",
    "pollution hotspot in",
    "pollution hotspots in",
]


# ============================================================
# LOAD 100 LOCATIONS
# ============================================================

locations = []

if os.path.exists(
    LOCATION_FILE
):

    df = pd.read_csv(
        LOCATION_FILE
    )

    if "location_name" in df.columns:

        locations = (
            df["location_name"]
            .dropna()
            .astype(str)
            .str.strip()
            .tolist()
        )


# Add common Indian cities for location recognition
COMMON_LOCATIONS = [
    "Pune",
    "Mumbai",
    "Delhi",
    "New Delhi",
    "Bengaluru",
    "Bangalore",
    "Hyderabad",
    "Chennai",
    "Kolkata",
    "Ahmedabad",
    "Nagpur",
    "Nashik",
    "Aurangabad",
    "Thane",
    "Navi Mumbai",
    "Noida",
    "Gurugram",
    "Gurgaon",
    "Jaipur",
    "Surat",
    "Indore",
    "Bhopal",
    "Lucknow",
    "Kanpur",
    "Patna",
    "Chandigarh",
]


for location in COMMON_LOCATIONS:

    if location not in locations:

        locations.append(
            location
        )


# Sort longest names first
locations = sorted(
    set(locations),
    key=lambda x: len(x),
    reverse=True
)


# ============================================================
# BUILD MATRIX
# ============================================================

matrix = {
    "policy_commands": sorted(
        set(POLICY_COMMANDS),
        key=lambda x: len(x),
        reverse=True
    ),

    "location_commands": sorted(
        set(LOCATION_COMMANDS),
        key=lambda x: len(x),
        reverse=True
    ),

    "locations": locations,

    "location_count": len(locations),

    "routing_rules": {
        "policy_without_location": True,
        "location_queries_require_location": True,
        "known_location_overrides_generic_text": True,
        "definition_questions_are_policy": True,
        "cpcb_questions_are_policy": True,
        "control_measure_questions_are_policy": True
    }
}


with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        matrix,
        f,
        indent=2,
        ensure_ascii=False
    )


print("=" * 70)
print("INTENT MATRIX CREATED")
print("=" * 70)

print(
    "Policy commands:",
    len(
        matrix["policy_commands"]
    )
)

print(
    "Location commands:",
    len(
        matrix["location_commands"]
    )
)

print(
    "Known locations:",
    matrix["location_count"]
)

print(
    "Output:",
    OUTPUT_FILE
)
