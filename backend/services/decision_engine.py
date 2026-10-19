import os
import pandas as pd


ROOT = r"C:\final year project\AI-POLLUTION-SYSTEM"

HOTSPOT_FILE = os.path.join(
    ROOT,
    "data",
    "processed",
    "pune_hotspots.csv"
)

ANOMALY_FILE = os.path.join(
    ROOT,
    "data",
    "processed",
    "pune_anomaly_results.csv"
)


# ============================================================
# LOAD ANOMALY / HOTSPOT DATA
# ============================================================

def load_anomaly_data():

    if not os.path.exists(ANOMALY_FILE):
        return None

    return pd.read_csv(
        ANOMALY_FILE
    )


def load_hotspot_data():

    if not os.path.exists(HOTSPOT_FILE):
        return None

    return pd.read_csv(
        HOTSPOT_FILE
    )


# ============================================================
# NORMALIZE
# ============================================================

def normalize(value):

    return (
        str(value)
        .strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
    )


# ============================================================
# FIND REPRESENTATIVE STATION
# ============================================================

def find_station(
    location
):

    location = normalize(
        location
    )

    # Representative mapping used by your project
    mapping = {

        "alandi":
            "Alandi",

        "bhosari":
            "Bhosari",

        "bhumkar nagar":
            "Bhumkar Nagar",

        "dhankawadi":
            "Dhankawadi",

        "hadapsar":
            "Hadapsar",

        "karve road":
            "Karve Road",

        "katraj":
            "Katraj Dairy",

        "kharadi":
            "Hadapsar",

        "kothrud":
            "Karve Road",

        "aundh":
            "SPPU",

        "baner":
            "SPPU",

        "balewadi":
            "SPPU",

        "pashan":
            "Panchawati_Pashan",

        "wakad":
            "Transport Nagar-Nigdi",

        "pimpri":
            "Transport Nagar-Nigdi",

        "chinchwad":
            "Transport Nagar-Nigdi",

        "nigdi":
            "Transport Nagar-Nigdi",

        "shivajinagar":
            "Revenue Colony-Shivajinagar",

        "revenue colony":
            "Revenue Colony-Shivajinagar",

        "viman nagar":
            "Hadapsar",

        "wagholi":
            "Hadapsar",

        "kalyani nagar":
            "Hadapsar",

        "koregaon park":
            "Hadapsar",

        "magarpatta":
            "Hadapsar",

        "kondhwa":
            "Hadapsar",

        "undri":
            "Hadapsar",

        "katraj":
            "Katraj Dairy",

        "sppu":
            "SPPU",
    }

    return mapping.get(
        location
    )


# ============================================================
# ANOMALY STATUS
# ============================================================

def get_anomaly_status(
    location,
    station=None
):

    df = load_anomaly_data()

    if df is None:
        return {
            "available": False,
            "is_anomaly": None,
            "score": None,
            "reason": "Anomaly results not available."
        }

    if "station_name" not in df.columns:
        return {
            "available": False,
            "is_anomaly": None,
            "score": None,
            "reason": "station_name missing."
        }

    target = normalize(
        station or location
    )

    df["_key"] = (
        df["station_name"]
        .map(normalize)
    )

    matches = df[
        df["_key"] == target
    ]

    if matches.empty:
        return {
            "available": False,
            "is_anomaly": None,
            "score": None,
            "reason": (
                f"No anomaly record for {station or location}."
            )
        }

    latest = matches.iloc[-1]

    return {
        "available": True,
        "is_anomaly": bool(
            latest.get(
                "is_anomaly",
                False
            )
        ),
        "score": float(
            latest.get(
                "anomaly_score",
                0
            )
        )
    }


# ============================================================
# HOTSPOT STATUS
# ============================================================

def get_hotspot_status(
    station
):

    df = load_hotspot_data()

    if df is None:
        return {
            "available": False,
            "is_hotspot": None,
            "cluster": None,
            "score": None,
            "reason": "Hotspot results not available."
        }

    if "station_name" not in df.columns:
        return {
            "available": False,
            "is_hotspot": None,
            "cluster": None,
            "score": None,
            "reason": "station_name missing."
        }

    target = normalize(
        station
    )

    df["_key"] = (
        df["station_name"]
        .map(normalize)
    )

    matches = df[
        df["_key"] == target
    ]

    if matches.empty:
        return {
            "available": False,
            "is_hotspot": None,
            "cluster": None,
            "score": None,
            "reason": (
                f"No hotspot record for {station}."
            )
        }

    row = matches.iloc[0]

    return {
        "available": True,
        "is_hotspot": bool(
            row.get(
                "is_hotspot_cluster",
                False
            )
        ),
        "cluster": int(
            row.get(
                "cluster",
                -1
            )
        ),
        "score": float(
            row.get(
                "hotspot_score",
                0
            )
        )
    }


# ============================================================
# DECISION RULES
# ============================================================

def make_decision(
    current,
    xgboost=None,
    anomaly=None,
    hotspot=None
):

    pm25 = current.get(
        "pm2_5"
    )

    pm10 = current.get(
        "pm10"
    )

    temperature = current.get(
        "temperature_c"
    )

    rainfall = current.get(
        "rainfall_mm"
    )

    humidity = current.get(
        "humidity"
    )

    wind = current.get(
        "wind_speed_ms"
    )

    actions = []
    warnings = []
    priorities = []

    # --------------------------------------------------------
    # CURRENT PM2.5
    # --------------------------------------------------------

    if pm25 is not None:

        if pm25 >= 90:

            priorities.append(
                "VERY_HIGH_POLLUTION"
            )

            warnings.append(
                "PM2.5 is very high."
            )

        elif pm25 >= 60:

            priorities.append(
                "HIGH_POLLUTION"
            )

            warnings.append(
                "PM2.5 is high."
            )

        elif pm25 >= 35:

            priorities.append(
                "ELEVATED_POLLUTION"
            )

            warnings.append(
                "PM2.5 is elevated."
            )

    # --------------------------------------------------------
    # PM10
    # --------------------------------------------------------

    if pm10 is not None and pm10 >= 100:

        priorities.append(
            "HIGH_PARTICLE_LOAD"
        )

        warnings.append(
            "PM10 is elevated."
        )

    # --------------------------------------------------------
    # TEMPERATURE
    # --------------------------------------------------------

    if temperature is not None:

        if temperature >= 35:

            priorities.append(
                "HIGH_HEAT"
            )

            warnings.append(
                "High temperature detected."
            )

        elif temperature <= 10:

            priorities.append(
                "LOW_TEMPERATURE"
            )

    # --------------------------------------------------------
    # RAIN
    # --------------------------------------------------------

    if rainfall is not None:

        if rainfall >= 10:

            priorities.append(
                "HEAVY_RAIN"
            )

            warnings.append(
                "Heavy rainfall is occurring."
            )

        elif rainfall > 0:

            priorities.append(
                "RAIN"
            )

    # --------------------------------------------------------
    # WIND
    # --------------------------------------------------------

    if (
        wind is not None
        and wind <= 2
    ):

        priorities.append(
            "LOW_DISPERSION"
        )

        warnings.append(
            "Low wind speed may reduce pollutant dispersion."
        )

    # --------------------------------------------------------
    # ANOMALY
    # --------------------------------------------------------

    if anomaly:

        if anomaly.get(
            "available"
        ) and anomaly.get(
            "is_anomaly"
        ):

            priorities.append(
                "ANOMALY"
            )

            warnings.append(
                "Pollution pattern is anomalous compared with the modelled baseline."
            )

            actions.append(
                "Increase monitoring frequency and investigate local emission sources."
            )

    # --------------------------------------------------------
    # HOTSPOT
    # --------------------------------------------------------

    if hotspot:

        if hotspot.get(
            "available"
        ) and hotspot.get(
            "is_hotspot"
        ):

            priorities.append(
                "HOTSPOT"
            )

            warnings.append(
                "The representative monitoring station belongs to a detected spatial cluster."
            )

            actions.append(
                "Prioritize inspection of nearby traffic, construction and other emission sources."
            )

    # --------------------------------------------------------
    # XGBOOST FORECAST
    # --------------------------------------------------------

    predicted = None

    if xgboost:

        if xgboost.get(
            "available"
        ):

            predicted = xgboost.get(
                "predicted_pm25_next_1h"
            )

            if predicted is not None:

                if predicted >= 90:

                    warnings.append(
                        "The next-hour PM2.5 forecast is very high."
                    )

                    priorities.append(
                        "FORECAST_VERY_HIGH"
                    )

                elif predicted >= 60:

                    warnings.append(
                        "The next-hour PM2.5 forecast is high."
                    )

                    priorities.append(
                        "FORECAST_HIGH"
                    )

    # --------------------------------------------------------
    # COMBINED CONDITIONS
    # --------------------------------------------------------

    if (
        "HIGH_POLLUTION" in priorities
        or "VERY_HIGH_POLLUTION" in priorities
    ):

        actions.extend([
            "Reduce prolonged outdoor exposure while pollution remains elevated.",
            "Inspect active traffic, construction and other emission sources.",
            "Strengthen local dust and emission-control measures."
        ])

    if (
        "HIGH_POLLUTION" in priorities
        and "HIGH_HEAT" in priorities
    ):

        actions.extend([
            "Treat the situation as combined pollution and heat exposure.",
            "Maintain hydration and reduce prolonged outdoor activity."
        ])

    if (
        "HIGH_POLLUTION" in priorities
        and "HEAVY_RAIN" in priorities
    ):

        actions.append(
            "Recheck air quality after rainfall because pollutant concentrations can change rapidly."
        )

    if (
        "LOW_DISPERSION" in priorities
        and (
            "HIGH_POLLUTION" in priorities
            or "VERY_HIGH_POLLUTION" in priorities
        )
    ):

        actions.append(
            "Increase short-term monitoring because low wind can limit pollutant dispersion."
        )

    if "HEAVY_RAIN" in priorities:

        actions.append(
            "Monitor drainage, waterlogging and traffic conditions."
        )

    # --------------------------------------------------------
    # DEFAULT
    # --------------------------------------------------------

    if not actions:

        actions.append(
            "Continue routine environmental monitoring."
        )

    return {
        "priorities": list(
            dict.fromkeys(
                priorities
            )
        ),

        "warnings": list(
            dict.fromkeys(
                warnings
            )
        ),

        "recommended_actions": list(
            dict.fromkeys(
                actions
            )
        ),

        "next_hour_pm25": predicted,

        "inputs": {
            "pm25": pm25,
            "pm10": pm10,
            "temperature_c": temperature,
            "rainfall_mm": rainfall,
            "humidity": humidity,
            "wind_speed_ms": wind
        }
    }


# ============================================================
# MAIN DECISION FUNCTION
# ============================================================

def get_decision(
    location,
    current,
    xgboost=None
):

    station = find_station(
        location
    )

    anomaly = get_anomaly_status(
        location,
        station
    )

    hotspot = get_hotspot_status(
        station
    ) if station else {
        "available": False,
        "is_hotspot": None,
        "reason": "No representative station."
    }

    decision = make_decision(
        current=current,
        xgboost=xgboost,
        anomaly=anomaly,
        hotspot=hotspot
    )

    decision[
        "location"
    ] = location

    decision[
        "representative_station"
    ] = station

    decision[
        "anomaly"
    ] = anomaly

    decision[
        "hotspot"
    ] = hotspot

    return decision


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    current = {
        "pm2_5": 75,
        "pm10": 120,
        "temperature_c": 36,
        "rainfall_mm": 0,
        "humidity": 45,
        "wind_speed_ms": 1.5
    }

    xgb = {
        "available": True,
        "predicted_pm25_next_1h": 82
    }

    result = get_decision(
        "Bhosari",
        current,
        xgb
    )

    print(
        "\nDECISION ENGINE"
    )

    print("=" * 70)

    for key, value in result.items():

        print(
            f"{key}: {value}"
        )
