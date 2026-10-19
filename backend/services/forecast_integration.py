import os
import re
from typing import Optional

import pandas as pd

from backend.services.environment_service import (
    get_environment_report
)

from backend.services.forecast_service import (
    predict_single,
    get_canonical_forecast
)


ROOT = r"C:\final year project\AI-POLLUTION-SYSTEM"

LOCATION_FILE = os.path.join(
    ROOT,
    "data",
    "processed",
    "pune_100_locations.csv"
)

FEATURE_FILE = os.path.join(
    ROOT,
    "data",
    "processed",
    "pune_cpcb_features.csv"
)


# ============================================================
# ENSEMBLE CONFIG
# ============================================================
#
# These are INITIAL engineering weights.
# They should NOT be considered statistically optimal yet.
#
# Later we will tune them using a historical validation set.
# ============================================================

XGBOOST_WEIGHT = 0.70
WEATHERAPI_WEIGHT = 0.30


# ============================================================
# NORMALIZE
# ============================================================

def normalize(value):

    return re.sub(
        r"\s+",
        " ",
        str(value)
        .strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
    )


# ============================================================
# LOAD 100 LOCATION MASTER
# ============================================================

def load_locations():

    if not os.path.exists(
        LOCATION_FILE
    ):

        raise FileNotFoundError(
            f"Missing location file:\n{LOCATION_FILE}"
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
# VERIFY LOCATION
# ============================================================

def find_100_location(location):
    from difflib import get_close_matches

    df = load_locations()
    target = normalize(location)

    df["_key"] = df["location_name"].map(normalize)

    exact = df[df["_key"] == target]
    if not exact.empty:
        return exact.iloc[0]

    partial = df[df["_key"].str.contains(target, na=False)]
    if not partial.empty and target:
        return partial.iloc[0]

    # Correct common small spelling errors, e.g. "hadpsar".
    choices = df["_key"].dropna().unique().tolist()
    matches = get_close_matches(target, choices, n=1, cutoff=0.65)

    if matches:
        matched = df[df["_key"] == matches[0]]
        if not matched.empty:
            return matched.iloc[0]

    return None


# FIND REAL XGBOOST STATION
# ============================================================

def find_xgboost_station(
    location
):

    if not os.path.exists(
        FEATURE_FILE
    ):

        return None

    df = pd.read_csv(
        FEATURE_FILE,
        usecols=["station_name"]
    )

    stations = (
        df["station_name"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    target = normalize(
        location
    )

    # Exact
    for station in stations:

        if normalize(station) == target:

            return station

    # Contains
    for station in stations:

        key = normalize(
            station
        )

        if (
            target in key
            or key in target
        ):

            return station

    return None


# ============================================================
# GET WEATHERAPI FORECAST
# ============================================================

def get_weatherapi_forecast(location, hours=6):
    location_row = find_100_location(location)

    if location_row is None:
        return {
            "available": False,
            "source": "WeatherAPI",
            "location": location,
            "reason": "Location is not in the 100-location Pune master."
        }

    try:
        report = get_environment_report(
            f"weather forecast for {location}",
            forecast_hours=hours
        )

        forecast = report.get("forecast") or []
        current = report.get("current") or {}

        next_hour_pm25 = None
        selected_forecast = None

        for item in forecast:
            if not isinstance(item, dict):
                continue

            value = item.get("pm2_5")
            if value is None:
                continue

            try:
                value = float(value)
            except (TypeError, ValueError):
                continue

            if not pd.notna(value) or value < 0:
                continue

            next_hour_pm25 = value
            selected_forecast = item
            break

        if next_hour_pm25 is None:
            return {
                "available": False,
                "source": "WeatherAPI",
                "location": location,
                "reason": "No valid forecast PM2.5 value returned.",
                "current": current,
                "forecast": forecast[:hours],
                "weatherapi_location": report.get("location")
            }

        return {
            "available": True,
            "source": "WeatherAPI",
            "location": location,
            "current": current,
            "forecast": forecast[:hours],
            "next_hour_pm25": next_hour_pm25,
            "selected_forecast": selected_forecast,
            "weatherapi_location": report.get("location")
        }

    except Exception as exc:
        return {
            "available": False,
            "source": "WeatherAPI",
            "location": location,
            "reason": f"{type(exc).__name__}: {exc}"
        }


# ============================================================
# XGBOOST FORECAST
# ============================================================

def get_xgboost_prediction(location):
    location_row = find_100_location(location)

    if location_row is None:
        return {
            "available": False,
            "source": "XGBoost",
            "location": location,
            "reason": "Location could not be resolved in the location master."
        }

    resolved_location = str(location_row["location_name"])

    try:
        result = get_canonical_forecast(resolved_location)

        prediction = result.get("predicted_pm25")
        available = (
            result.get("forecast_available", False)
            and prediction is not None
        )

        return {
            "available": available,
            "source": "CPCB XGBoost canonical forecast",
            "location": location,
            "resolved_location": result.get(
                "resolved_location", resolved_location
            ),
            "model_station": (
                result.get("contributing_stations", [{}])[0].get("clean_name")
                if result.get("contributing_stations")
                else None
            ),
            "next_hour_pm25": (
                float(prediction) if available else None
            ),
            "forecast_method": result.get("forecast_method"),
            "case": result.get("case"),
            "data_quality_status": result.get("data_quality_status"),
            "contributing_stations": result.get("contributing_stations", []),
            "reason": result.get("reason"),
            "warnings": result.get("warnings", [])
        }

    except Exception as exc:
        return {
            "available": False,
            "source": "CPCB XGBoost canonical forecast",
            "location": location,
            "resolved_location": resolved_location,
            "reason": f"{type(exc).__name__}: {exc}"
        }


# ENSEMBLE
# ============================================================

def combine_predictions(
    xgb_prediction: Optional[float],
    weatherapi_prediction: Optional[float]
):

    if (
        xgb_prediction is not None
        and weatherapi_prediction is not None
    ):

        final_prediction = (
            XGBOOST_WEIGHT
            * xgb_prediction
            +
            WEATHERAPI_WEIGHT
            * weatherapi_prediction
        )

        return {
            "available": True,
            "method": "weighted_ensemble",
            "xgboost_weight": XGBOOST_WEIGHT,
            "weatherapi_weight": WEATHERAPI_WEIGHT,
            "xgboost_prediction": round(
                xgb_prediction,
                2
            ),
            "weatherapi_prediction": round(
                weatherapi_prediction,
                2
            ),
            "ensemble_prediction": round(
                final_prediction,
                2
            ),
            "unit": "µg/m³"
        }

    if xgb_prediction is not None:

        return {
            "available": True,
            "method": "xgboost_only",
            "xgboost_prediction": round(
                xgb_prediction,
                2
            ),
            "weatherapi_prediction": None,
            "ensemble_prediction": round(
                xgb_prediction,
                2
            ),
            "unit": "µg/m³"
        }

    if weatherapi_prediction is not None:

        return {
            "available": True,
            "method": "weatherapi_only",
            "xgboost_prediction": None,
            "weatherapi_prediction": round(
                weatherapi_prediction,
                2
            ),
            "ensemble_prediction": round(
                weatherapi_prediction,
                2
            ),
            "unit": "µg/m³"
        }

    return {
        "available": False,
        "method": "unavailable",
        "xgboost_prediction": None,
        "weatherapi_prediction": None,
        "ensemble_prediction": None,
        "unit": "µg/m³"
    }


# ============================================================
# MASTER ENVIRONMENT FORECAST
# ============================================================

def get_xgboost_forecast(
    location
):

    # --------------------------------------------------------
    # Get BOTH sources
    # --------------------------------------------------------

    xgb = get_xgboost_prediction(
        location
    )

    weather = get_weatherapi_forecast(
        location,
        hours=6
    )

    xgb_value = None

    weather_value = None

    if xgb.get(
        "available"
    ):

        xgb_value = xgb.get(
            "next_hour_pm25"
        )

    if weather.get(
        "available"
    ):

        weather_value = weather.get(
            "next_hour_pm25"
        )

    # --------------------------------------------------------
    # Combine
    # --------------------------------------------------------

    ensemble = combine_predictions(
        xgb_value,
        weather_value
    )

    return {

        "available":
            ensemble["available"],

        "location":
            location,

        "forecast_source":
            ensemble["method"],

        "model":
            "XGBoost + WeatherAPI ensemble",

        "xgboost":
            xgb,

        "weatherapi":
            weather,

        "ensemble":
            ensemble,

        "predicted_pm25_next_1h":
            ensemble[
                "ensemble_prediction"
            ],

        "unit":
            "µg/m³",

        "weight_note":
            (
                "Initial weights are engineering "
                "weights. Validate and tune them "
                "against historical observations "
                "before claiming improved accuracy."
            )
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    while True:

        location = input(
            "\nEnter Pune location "
            "(or exit): "
        ).strip()

        if location.lower() == "exit":

            break

        result = get_xgboost_forecast(
            location
        )

        print()
        print(
            "=" * 70
        )

        print(
            "ENSEMBLE ENVIRONMENT FORECAST"
        )

        print(
            "=" * 70
        )

        print(
            "Location:",
            result["location"]
        )

        print(
            "Method:",
            result["forecast_source"]
        )

        print(
            "Final next-hour PM2.5:",
            result[
                "predicted_pm25_next_1h"
            ],
            result["unit"]
        )

        print()

        print(
            "XGBoost:"
        )

        print(
            result["xgboost"]
        )

        print()

        print(
            "WeatherAPI:"
        )

        print(
            result["weatherapi"]
        )

        print()

        print(
            "Ensemble:"
        )

        print(
            result["ensemble"]
        )
