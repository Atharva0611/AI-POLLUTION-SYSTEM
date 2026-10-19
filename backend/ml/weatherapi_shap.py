from __future__ import annotations

import argparse
import json
import os
import pickle
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import requests
import shap
from dotenv import load_dotenv


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

MODEL_PATHS = [
    ROOT / "models" / "forecasting" / "pune_multistation_xgboost.pkl",
    ROOT / "models" / "forecasting" / "xgboost_pm25_forecasting.pkl",
]

FEATURE_PATHS = [
    ROOT / "models" / "forecasting" / "pune_multistation_features.pkl",
    ROOT / "models" / "forecasting" / "feature_names.pkl",
]

MEDIAN_PATHS = [
    ROOT / "models" / "forecasting" / "pune_multistation_medians.pkl",
]

DATA_PATHS = [
    ROOT / "data" / "processed" / "pune_cpcb_all_stations_hourly.csv",
    ROOT / "data" / "processed" / "pune_cpcb_cleaned_hourly.csv",
]

LOCATION_PATHS = [
    ROOT / "data" / "processed" / "pune_100_locations_mapped.csv",
    ROOT / "data" / "processed" / "pune_100_locations.csv",
]

OUT_DIR = ROOT / "data" / "reports" / "shap"
OUT_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(ROOT / ".env")


# ============================================================
# HELPERS
# ============================================================

def norm(value):
    value = str(value).strip().lower()
    value = re.sub(
        r"[^a-zA-Z0-9]+",
        "_",
        value
    )
    return re.sub(
        r"_+",
        "_",
        value
    ).strip("_")


def find_file(paths, description):

    for path in paths:

        if path.exists():
            return path

    raise FileNotFoundError(
        f"{description} not found.\n\n"
        + "\n".join(
            f" - {p}"
            for p in paths
        )
    )


def load_any(path):

    try:
        return joblib.load(path)
    except Exception:

        with open(
            path,
            "rb"
        ) as f:

            return pickle.load(f)


# ============================================================
# MODEL
# ============================================================

MODEL_PATH = find_file(
    MODEL_PATHS,
    "XGBoost model"
)

MODEL = load_any(
    MODEL_PATH
)

if isinstance(
    MODEL,
    dict
):

    for key in [
        "model",
        "xgb_model",
        "estimator",
        "regressor"
    ]:

        if key in MODEL:

            MODEL = MODEL[key]
            break


if not hasattr(
    MODEL,
    "predict"
):

    raise TypeError(
        "Loaded XGBoost object does not have predict()."
    )


# ============================================================
# FEATURES
# ============================================================

FEATURES = None
FEATURE_PATH = None

for path in FEATURE_PATHS:

    if not path.exists():
        continue

    obj = load_any(
        path
    )

    if isinstance(
        obj,
        dict
    ):

        for key in [
            "feature_names",
            "features",
            "columns"
        ]:

            if key in obj:

                obj = obj[key]
                break

    if isinstance(
        obj,
        (
            list,
            tuple,
            np.ndarray,
            pd.Index
        )
    ):

        FEATURES = [
            str(x)
            for x in obj
        ]

        FEATURE_PATH = path
        break


if FEATURES is None:

    if hasattr(
        MODEL,
        "feature_names_in_"
    ):

        FEATURES = [
            str(x)
            for x in MODEL.feature_names_in_
        ]

    else:

        try:

            booster = MODEL.get_booster()

            FEATURES = [
                str(x)
                for x in booster.feature_names
            ]

        except Exception:

            raise RuntimeError(
                "Could not determine model feature names."
            )


# ============================================================
# HISTORICAL DATA
# ============================================================

DATA_PATH = find_file(
    DATA_PATHS,
    "Pune historical CPCB dataset"
)

df = pd.read_csv(
    DATA_PATH
)

COLUMN_MAP = {
    norm(c): c
    for c in df.columns
}


# ============================================================
# TIMESTAMP
# ============================================================

timestamp_col = None

for candidate in [
    "timestamp",
    "datetime",
    "date_time",
    "date",
    "time"
]:

    if candidate in COLUMN_MAP:

        timestamp_col = COLUMN_MAP[
            candidate
        ]

        break


if timestamp_col is None:

    raise RuntimeError(
        "Historical dataset has no timestamp column."
    )


df["_timestamp"] = pd.to_datetime(
    df[timestamp_col],
    errors="coerce"
)


# ============================================================
# STATION
# ============================================================

station_col = None

for candidate in [
    "station_name",
    "station",
    "site",
    "location"
]:

    if candidate in COLUMN_MAP:

        station_col = COLUMN_MAP[
            candidate
        ]

        break


if station_col is None:

    raise RuntimeError(
        "Historical dataset has no station column."
    )


df["_station"] = (
    df[station_col]
    .astype(str)
    .str.strip()
)

df = df.dropna(
    subset=[
        "_timestamp"
    ]
).copy()

df = df.sort_values(
    [
        "_station",
        "_timestamp"
    ]
).reset_index(
    drop=True
)


# ============================================================
# MEDIANS
# ============================================================

MEDIANS = {}

for path in MEDIAN_PATHS:

    if not path.exists():
        continue

    obj = load_any(
        path
    )

    if isinstance(
        obj,
        dict
    ):

        for key, value in obj.items():

            try:

                MEDIANS[
                    norm(key)
                ] = float(value)

            except Exception:
                pass

    break


# ============================================================
# WEATHERAPI
# ============================================================

API_KEY = os.getenv(
    "WEATHER_API_KEY"
)

if not API_KEY:

    raise RuntimeError(
        "WEATHER_API_KEY was not found in .env"
    )


def fetch_weather(location):

    url = (
        "https://api.weatherapi.com/v1/"
        "current.json"
    )

    params = {

        "key":
            API_KEY,

        "q":
            location,

        "aqi":
            "yes"

    }

    response = requests.get(
        url,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# LOCATION → REPRESENTATIVE CPCB STATION
# ============================================================

def resolve_station(
    location
):

    location_path = None

    for path in LOCATION_PATHS:

        if path.exists():

            location_path = path
            break


    if location_path is None:

        # Direct station name fallback.
        stations = sorted(
            df["_station"]
            .dropna()
            .astype(str)
            .unique()
        )

        q = norm(
            location
        )

        for station in stations:

            if norm(station) == q:

                return station

        for station in stations:

            if q in norm(station):

                return station

        return None


    locations = pd.read_csv(
        location_path
    )


    normalized = {
        norm(c): c
        for c in locations.columns
    }


    name_col = None
    station_col_location = None


    for candidate in [
        "location",
        "location_name",
        "locality",
        "name",
        "place",
        "area"
    ]:

        if candidate in normalized:

            name_col = normalized[
                candidate
            ]

            break


    for candidate in [
        "representative_cpcb_station",
        "representative_station",
        "cpcb_station",
        "station"
    ]:

        if candidate in normalized:

            station_col_location = normalized[
                candidate
            ]

            break


    if (
        name_col is None
        or
        station_col_location is None
    ):

        return None


    q = norm(
        location
    )


    # Exact match

    for _, row in locations.iterrows():

        name = str(
            row[name_col]
        ).strip()

        if norm(name) == q:

            station = str(
                row[
                    station_col_location
                ]
            ).strip()

            if station.lower() not in {
                "",
                "nan",
                "none"
            }:

                return station


    # Partial match

    matches = []

    for _, row in locations.iterrows():

        name = str(
            row[name_col]
        ).strip()

        if (
            q in norm(name)
            or
            norm(name) in q
        ):

            station = str(
                row[
                    station_col_location
                ]
            ).strip()

            if station.lower() not in {
                "",
                "nan",
                "none"
            }:

                matches.append(
                    station
                )


    if matches:

        return matches[0]


    return None


# ============================================================
# WEATHER VALUES
# ============================================================

def weather_values(data):

    current = data[
        "current"
    ]

    aq = current.get(
        "air_quality",
        {}
    ) or {}


    return {

        # pollutants
        "pm25":
            aq.get(
                "pm2_5"
            ),

        "pm2_5":
            aq.get(
                "pm2_5"
            ),

        "pm10":
            aq.get(
                "pm10"
            ),

        "co":
            aq.get(
                "co"
            ),

        "no2":
            aq.get(
                "no2"
            ),

        "so2":
            aq.get(
                "so2"
            ),

        "o3":
            aq.get(
                "o3"
            ),

        # weather
        "temperature":
            current.get(
                "temp_c"
            ),

        "temp":
            current.get(
                "temp_c"
            ),

        "humidity":
            current.get(
                "humidity"
            ),

        # CPCB historical wind is commonly m/s.
        "wind_speed":
            (
                current.get(
                    "wind_kph"
                ) / 3.6
                if current.get(
                    "wind_kph"
                ) is not None
                else None
            ),

        "wind_speed_kph":
            current.get(
                "wind_kph"
            ),

        "rainfall":
            current.get(
                "precip_mm"
            ),

        "rain":
            current.get(
                "precip_mm"
            ),

        "pressure":
            current.get(
                "pressure_mb"
            ),

        "pressure_mb":
            current.get(
                "pressure_mb"
            )

    }


# ============================================================
# MAP WEATHERAPI VALUES TO MODEL FEATURES
# ============================================================

def get_weather_feature(
    feature,
    weather
):

    f = norm(
        feature
    )


    # PM2.5

    if f in {
        "pm25",
        "pm2_5"
    }:

        return weather.get(
            "pm25"
        )


    # PM10

    if f == "pm10":

        return weather.get(
            "pm10"
        )


    # gases

    if f == "co":

        return weather.get(
            "co"
        )

    if f == "no2":

        return weather.get(
            "no2"
        )

    if f == "so2":

        return weather.get(
            "so2"
        )

    if f == "o3":

        return weather.get(
            "o3"
        )


    # weather

    if f in {
        "temperature",
        "temp",
        "temperature_c",
        "temp_c"
    }:

        return weather.get(
            "temperature"
        )


    if f in {
        "humidity",
        "relative_humidity",
        "rh"
    }:

        return weather.get(
            "humidity"
        )


    if f in {
        "wind_speed",
        "wind_speed_mps",
        "ws"
    }:

        return weather.get(
            "wind_speed"
        )


    if f in {
        "wind_speed_kph",
        "wind_kph"
    }:

        return weather.get(
            "wind_speed_kph"
        )


    if f in {
        "rainfall",
        "rainfall_mm",
        "rain",
        "precipitation",
        "precip"
    }:

        return weather.get(
            "rainfall"
        )


    if f in {
        "pressure",
        "pressure_mb",
        "bp"
    }:

        return weather.get(
            "pressure"
        )


    return None


# ============================================================
# BASE HISTORICAL FEATURE
# ============================================================

def raw_column(
    base
):

    b = norm(
        base
    )

    for c in df.columns:

        if norm(c) == b:

            return c


    aliases = {

        "pm25": [
            "pm25",
            "pm2_5",
            "pm2.5"
        ],

        "pm10": [
            "pm10"
        ],

        "no2": [
            "no2"
        ],

        "so2": [
            "so2"
        ],

        "co": [
            "co"
        ],

        "o3": [
            "o3"
        ],

        "nh3": [
            "nh3"
        ],

        "temperature": [
            "temperature",
            "temp"
        ],

        "humidity": [
            "humidity",
            "rh"
        ],

        "wind_speed": [
            "wind_speed",
            "ws"
        ],

        "rainfall": [
            "rainfall",
            "rf",
            "rain"
        ],

        "pressure": [
            "pressure",
            "bp"
        ]
    }


    for key, choices in aliases.items():

        if b != key:
            continue

        for choice in choices:

            for c in df.columns:

                if norm(c) == norm(choice):

                    return c


    return None


# ============================================================
# LIVE FEATURE VECTOR
# ============================================================

def build_live_vector(
    station,
    weather_data
):

    station_df = df[
        df["_station"].astype(str).str.lower()
        ==
        str(station).lower()
    ].copy()


    if station_df.empty:

        raise ValueError(
            f"No historical CPCB records found "
            f"for station: {station}"
        )


    station_df = station_df.sort_values(
        "_timestamp"
    )


    latest = station_df.iloc[-1]


    weather = weather_values(
        weather_data
    )


    localtime = (
        weather_data
        .get(
            "location",
            {}
        )
        .get(
            "localtime"
        )
    )


    live_time = pd.to_datetime(
        localtime,
        errors="coerce"
    )


    if pd.isna(
        live_time
    ):

        live_time = latest[
            "_timestamp"
        ]


    row = {}


    for feature in FEATURES:

        f = norm(
            feature
        )

        value = None


        # ----------------------------------------------------
        # WEATHERAPI LIVE VALUE
        # ----------------------------------------------------

        value = get_weather_feature(
            feature,
            weather
        )


        # ----------------------------------------------------
        # STATION ONE HOT
        # ----------------------------------------------------

        if value is None:

            prefixes = [
                "station_",
                "station_name_",
                "site_",
                "site_name_"
            ]

            for prefix in prefixes:

                if f.startswith(prefix):

                    encoded = (
                        f[
                            len(prefix):
                        ]
                    )

                    value = (
                        1.0
                        if norm(station)
                        ==
                        encoded
                        else 0.0
                    )

                    break


        # ----------------------------------------------------
        # TIME
        # ----------------------------------------------------

        if value is None:

            if f in {
                "hour",
                "hour_of_day"
            }:

                value = float(
                    live_time.hour
                )

            elif f in {
                "day_of_week",
                "dow"
            }:

                value = float(
                    live_time.dayofweek
                )

            elif f == "month":

                value = float(
                    live_time.month
                )

            elif f == "day_of_year":

                value = float(
                    live_time.dayofyear
                )

            elif f in {
                "is_weekend",
                "weekend"
            }:

                value = float(
                    live_time.dayofweek >= 5
                )

            elif f in {
                "hour_sin",
                "sin_hour"
            }:

                value = float(
                    np.sin(
                        2 *
                        np.pi *
                        live_time.hour /
                        24
                    )
                )

            elif f in {
                "hour_cos",
                "cos_hour"
            }:

                value = float(
                    np.cos(
                        2 *
                        np.pi *
                        live_time.hour /
                        24
                    )
                )

            elif f in {
                "dow_sin",
                "sin_dow"
            }:

                value = float(
                    np.sin(
                        2 *
                        np.pi *
                        live_time.dayofweek /
                        7
                    )
                )

            elif f in {
                "dow_cos",
                "cos_dow"
            }:

                value = float(
                    np.cos(
                        2 *
                        np.pi *
                        live_time.dayofweek /
                        7
                    )
                )


        # ----------------------------------------------------
        # LAGS FROM MOST RECENT CPCB HISTORY
        # ----------------------------------------------------

        if value is None:

            match = re.match(
                r"(.+)_lag_?(\d+)h?$",
                f
            )

            if match is None:

                match = re.match(
                    r"(.+)_l(\d+)$",
                    f
                )


            if match is not None:

                base = match.group(1)
                lag = int(
                    match.group(2)
                )

                col = raw_column(
                    base
                )

                if (
                    col is not None
                    and
                    len(station_df) >= lag
                ):

                    series = pd.to_numeric(
                        station_df[col],
                        errors="coerce"
                    ).dropna()

                    if len(series) >= lag:

                        value = float(
                            series.iloc[
                                -lag
                            ]
                        )


        # ----------------------------------------------------
        # ROLLING
        # ----------------------------------------------------

        if value is None:

            match = re.match(
                r"(.+)_rolling_?(\d+)$",
                f
            )

            if match is not None:

                base = match.group(1)
                window = int(
                    match.group(2)
                )

                col = raw_column(
                    base
                )

                if col is not None:

                    series = pd.to_numeric(
                        station_df[col],
                        errors="coerce"
                    ).dropna()

                    if not series.empty:

                        value = float(
                            series
                            .tail(window)
                            .mean()
                        )


        # ----------------------------------------------------
        # EXACT HISTORICAL CURRENT VALUE
        # ----------------------------------------------------

        if value is None:

            col = raw_column(
                feature
            )

            if col is not None:

                raw_value = latest[
                    col
                ]

                try:

                    if pd.notna(
                        raw_value
                    ):

                        value = float(
                            raw_value
                        )

                except Exception:
                    pass


        # ----------------------------------------------------
        # MEDIAN
        # ----------------------------------------------------

        if value is None:

            value = MEDIANS.get(
                f
            )


        # ----------------------------------------------------
        # FINAL SAFETY
        # ----------------------------------------------------

        if value is None:

            raise ValueError(
                f"Could not construct "
                f"model feature: {feature}"
            )


        row[
            feature
        ] = float(
            value
        )


    return pd.DataFrame(
        [row],
        columns=FEATURES
    ), weather


# ============================================================
# SHAP
# ============================================================

def explain_weather(
    location,
    station=None
):

    print("")
    print("=" * 70)
    print("WEATHERAPI → XGBOOST → SHAP")
    print("=" * 70)


    # --------------------------------------------------------
    # WeatherAPI
    # --------------------------------------------------------

    print(
        "\nFetching live WeatherAPI data..."
    )

    weather_data = fetch_weather(
        location
    )


    resolved_location = (
        weather_data
        .get(
            "location",
            {}
        )
    )


    location_name = (
        resolved_location
        .get(
            "name"
        )
    )

    country = (
        resolved_location
        .get(
            "country"
        )
    )


    print(
        "WeatherAPI location:",
        location_name,
        country
    )


    # --------------------------------------------------------
    # Station
    # --------------------------------------------------------

    if station is None:

        station = resolve_station(
            location_name
            or location
        )


    if station is None:

        raise ValueError(
            "\nNo representative CPCB station "
            "was found for this Pune locality.\n"
            "SHAP requires the trained Pune XGBoost "
            "model and therefore requires a model station."
        )


    print(
        "Representative CPCB station:",
        station
    )


    # --------------------------------------------------------
    # Feature vector
    # --------------------------------------------------------

    X, weather = build_live_vector(
        station,
        weather_data
    )


    # --------------------------------------------------------
    # Model prediction
    # --------------------------------------------------------

    prediction = float(
        MODEL.predict(
            X
        )[0]
    )


    # --------------------------------------------------------
    # SHAP
    # --------------------------------------------------------

    explainer = shap.TreeExplainer(
        MODEL
    )


    shap_values = explainer.shap_values(
        X
    )


    shap_values = np.asarray(
        shap_values
    )


    if shap_values.ndim == 3:

        shap_values = (
            shap_values[:, :, 0]
        )


    if shap_values.ndim != 2:

        raise RuntimeError(
            f"Unexpected SHAP shape: "
            f"{shap_values.shape}"
        )


    shap_row = shap_values[
        0
    ]


    expected = float(
        np.asarray(
            explainer.expected_value
        ).reshape(-1)[0]
    )


    reconstructed = float(
        expected
        +
        shap_row.sum()
    )


    error = abs(
        prediction
        -
        reconstructed
    )


    additivity_pass = (
        error
        <=
        max(
            1e-4,
            abs(prediction) * 1e-4
        )
    )


    # --------------------------------------------------------
    # ALL FEATURES
    # --------------------------------------------------------

    local = pd.DataFrame({

        "feature":
            FEATURES,

        "value":
            X.iloc[0].values,

        "shap":
            shap_row

    })


    local["abs_shap"] = (
        local["shap"]
        .abs()
    )


    local["direction"] = np.where(

        local["shap"] > 0,

        "INCREASES_PREDICTION",

        np.where(

            local["shap"] < 0,

            "DECREASES_PREDICTION",

            "NEUTRAL"
        )
    )


    local = local.sort_values(
        "abs_shap",
        ascending=False
    ).reset_index(
        drop=True
    )


    # --------------------------------------------------------
    # WEATHER-ONLY FEATURES
    # --------------------------------------------------------

    weather_feature_names = {

        "pm25",
        "pm2_5",
        "pm10",
        "co",
        "no2",
        "so2",
        "o3",

        "temperature",
        "temperature_c",
        "temp",
        "temp_c",

        "humidity",
        "rh",

        "wind_speed",
        "wind_speed_mps",
        "wind_speed_kph",

        "rainfall",
        "rainfall_mm",
        "rain",
        "precipitation",

        "pressure",
        "pressure_mb"

    }


    weather_local = local[
        local["feature"]
        .map(
            lambda x:
            norm(x)
            in weather_feature_names
        )
    ].copy()


    # --------------------------------------------------------
    # SAVE OUTPUT
    # --------------------------------------------------------

    safe_location = norm(
        location_name
        or location
    )

    report_path = (
        OUT_DIR /
        f"weatherapi_shap_{safe_location}.json"
    )

    csv_path = (
        OUT_DIR /
        f"weatherapi_shap_{safe_location}.csv"
    )


    weather_local.to_csv(
        csv_path,
        index=False
    )


    top_local = [
        {
            "feature":
                str(row["feature"]),

            "value":
                float(row["value"]),

            "shap":
                float(row["shap"]),

            "direction":
                str(row["direction"])

        }

        for _, row
        in local.head(15).iterrows()
    ]


    top_weather = [

        {

            "feature":
                str(row["feature"]),

            "weatherapi_value":
                float(row["value"]),

            "shap":
                float(row["shap"]),

            "direction":
                str(row["direction"])

        }

        for _, row
        in weather_local.head(10).iterrows()
    ]


    report = {

        "available":
            True,

        "explanation_type":
            "WeatherAPI live inputs explained through Pune XGBoost",

        "weatherapi_location":
            location_name,

        "country":
            country,

        "representative_cpcb_station":
            station,

        "latitude":
            resolved_location.get(
                "lat"
            ),

        "longitude":
            resolved_location.get(
                "lon"
            ),

        "weatherapi_last_updated":
            weather_data
            .get(
                "current",
                {}
            )
            .get(
                "last_updated"
            ),

        "predicted_next_hour_pm25":
            prediction,

        "expected_value":
            expected,

        "reconstructed_prediction":
            reconstructed,

        "additivity_error":
            float(error),

        "additivity_check":
            bool(additivity_pass),

        "top_model_factors":
            top_local,

        "top_weatherapi_factors":
            top_weather,

        "weatherapi_air_quality": {
            key:
                float(value)
                if value is not None
                else None

            for key, value
            in weather.items()
            if value is not None
        },

        "important_note":
            (
                "SHAP explains the Pune XGBoost "
                "prediction using live WeatherAPI "
                "values. It does NOT explain "
                "WeatherAPI's internal forecasting model "
                "or imply causal source apportionment."
            )
    }


    with open(
        report_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            report,
            f,
            indent=2,
            ensure_ascii=False
        )


    # --------------------------------------------------------
    # PLOT
    # --------------------------------------------------------

    try:

        import matplotlib

        matplotlib.use(
            "Agg"
        )

        import matplotlib.pyplot as plt

        plot_data = weather_local.head(
            10
        ).sort_values(
            "shap"
        )

        plt.figure(
            figsize=(10, 6)
        )

        plt.barh(
            plot_data["feature"],
            plot_data["shap"]
        )

        plt.axvline(
            0,
            linewidth=1
        )

        plt.xlabel(
            "SHAP contribution"
        )

        plt.ylabel(
            "WeatherAPI feature"
        )

        plt.title(
            "Live WeatherAPI Factors Affecting "
            "Pune XGBoost PM2.5 Prediction"
        )

        plt.tight_layout()

        plot_path = (
            OUT_DIR /
            f"weatherapi_shap_{safe_location}.png"
        )

        plt.savefig(
            plot_path,
            dpi=180,
            bbox_inches="tight"
        )

        plt.close()

    except Exception as exc:

        plot_path = None

        print(
            "\nPlot warning:",
            exc
        )


    # --------------------------------------------------------
    # TERMINAL OUTPUT
    # --------------------------------------------------------

    print("")
    print("=" * 70)
    print("WEATHERAPI SHAP COMPLETE")
    print("=" * 70)

    print(
        "\nLocation:",
        location_name
    )

    print(
        "Representative CPCB station:",
        station
    )

    print(
        "Live WeatherAPI PM2.5:",
        weather.get(
            "pm25"
        )
    )

    print(
        "XGBoost next-hour prediction:",
        round(
            prediction,
            4
        ),
        "µg/m³"
    )

    print("")
    print(
        "SHAP ADDITIVITY"
    )

    print(
        "Expected value:",
        round(
            expected,
            6
        )
    )

    print(
        "Reconstructed:",
        round(
            reconstructed,
            6
        )
    )

    print(
        "Error:",
        f"{error:.10f}"
    )

    print(
        "PASS:",
        additivity_pass
    )


    print("")
    print(
        "LIVE WEATHERAPI FACTORS"
    )

    print(
        "-" * 70
    )


    for i, row in weather_local.head(
        10
    ).iterrows():

        print(

            f"{i + 1:2d}. "
            f"{row['feature']} | "
            f"value={row['value']:.4f} | "
            f"SHAP={row['shap']:+.4f} | "
            f"{row['direction']}"
        )


    print("")
    print(
        "TOP MODEL FACTORS"
    )

    print(
        "-" * 70
    )


    for i, row in local.head(
        10
    ).iterrows():

        print(

            f"{i + 1:2d}. "
            f"{row['feature']} | "
            f"value={row['value']:.4f} | "
            f"SHAP={row['shap']:+.4f} | "
            f"{row['direction']}"
        )


    print("")
    print(
        "FILES"
    )

    print(
        report_path
    )

    print(
        csv_path
    )

    if plot_path:

        print(
            plot_path
        )


    return report


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "location",
        help=(
            "Pune locality or CPCB station "
            "such as Hadapsar or Alandi"
        )
    )

    parser.add_argument(
        "--station",
        default=None,
        help=(
            "Optional representative CPCB "
            "station override"
        )
    )

    args = parser.parse_args()


    explain_weather(
        location=args.location,
        station=args.station
    )
