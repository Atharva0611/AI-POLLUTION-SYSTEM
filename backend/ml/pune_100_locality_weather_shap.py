from __future__ import annotations

import argparse
import json
import os
import pickle
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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

LOCATION_FILES = [
    ROOT / "data" / "processed" / "pune_100_locations_mapped.csv",
    ROOT / "data" / "processed" / "pune_100_locations.csv",
]

CPCB_FILES = [
    ROOT / "data" / "processed" / "pune_cpcb_all_stations_hourly.csv",
    ROOT / "data" / "processed" / "pune_cpcb_cleaned_hourly.csv",
]

MODEL_FILES = [
    ROOT / "models" / "forecasting" / "pune_multistation_xgboost.pkl",
    ROOT / "models" / "forecasting" / "xgboost_pm25_forecasting.pkl",
]

FEATURE_FILES = [
    ROOT / "models" / "forecasting" / "pune_multistation_features.pkl",
    ROOT / "models" / "forecasting" / "feature_names.pkl",
]

MEDIAN_FILES = [
    ROOT / "models" / "forecasting" / "pune_multistation_medians.pkl",
]

OUTPUT_DIR = (
    ROOT
    / "data"
    / "reports"
    / "pune_100_locality"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

PROCESSED_DIR = (
    ROOT
    / "data"
    / "processed"
)

load_dotenv(
    ROOT / ".env"
)


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


def find_file(
    candidates,
    description
):

    for path in candidates:

        if path.exists():
            return path

    raise FileNotFoundError(
        f"{description} not found.\n"
        + "\n".join(
            f" - {p}"
            for p in candidates
        )
    )


def find_column(
    df,
    candidates
):

    normalized = {
        norm(c): c
        for c in df.columns
    }

    # Exact match
    for candidate in candidates:

        key = norm(candidate)

        if key in normalized:
            return normalized[key]

    # Fuzzy match
    for col in df.columns:

        col_norm = norm(col)

        for candidate in candidates:

            candidate_norm = norm(
                candidate
            )

            if (
                candidate_norm in col_norm
                or
                col_norm in candidate_norm
            ):

                return col

    return None


def load_any(path):

    try:

        return joblib.load(
            path
        )

    except Exception:

        with open(
            path,
            "rb"
        ) as f:

            return pickle.load(f)


def clean_value(value):

    if pd.isna(value):
        return None

    try:

        return float(value)

    except Exception:

        return value


# ============================================================
# MODEL
# ============================================================

MODEL_PATH = find_file(
    MODEL_FILES,
    "Pune XGBoost model"
)

MODEL_OBJECT = load_any(
    MODEL_PATH
)

if isinstance(
    MODEL_OBJECT,
    dict
):

    for key in [
        "model",
        "xgb_model",
        "estimator",
        "regressor"
    ]:

        if key in MODEL_OBJECT:

            MODEL_OBJECT = MODEL_OBJECT[
                key
            ]

            break


MODEL = MODEL_OBJECT

if not hasattr(
    MODEL,
    "predict"
):

    raise RuntimeError(
        "Loaded model does not have predict()."
    )


# ============================================================
# FEATURES
# ============================================================

FEATURES = None

for path in FEATURE_FILES:

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

        booster = MODEL.get_booster()

        FEATURES = [
            str(x)
            for x in booster.feature_names
        ]


print("")
print("=" * 75)
print("PUNE 100+ LOCALITY WEATHER + XGBOOST + SHAP")
print("=" * 75)

print(
    "\nModel:",
    MODEL_PATH
)

print(
    "Feature count:",
    len(FEATURES)
)


# ============================================================
# MEDIANS
# ============================================================

MEDIANS = {}

for path in MEDIAN_FILES:

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
# LOAD 100+ LOCATION MASTER
# ============================================================

location_tables = []


for path in LOCATION_FILES:

    if not path.exists():
        continue

    try:

        temp = pd.read_csv(
            path
        )

        temp["_source_file"] = (
            path.name
        )

        location_tables.append(
            temp
        )

    except Exception as exc:

        print(
            f"Warning: could not read {path}: {exc}"
        )


if not location_tables:

    raise FileNotFoundError(
        "No Pune locality master file found."
    )


# ============================================================
# NORMALIZE EACH LOCATION FILE
# ============================================================

normalized_tables = []


for temp in location_tables:

    location_col = find_column(
        temp,
        [
            "location",
            "location_name",
            "locality",
            "name",
            "place",
            "area"
        ]
    )

    if location_col is None:
        continue


    lat_col = find_column(
        temp,
        [
            "latitude",
            "lat"
        ]
    )

    lon_col = find_column(
        temp,
        [
            "longitude",
            "lon",
            "lng"
        ]
    )

    representative_col = find_column(
        temp,
        [
            "representative_cpcb_station",
            "representative_station",
            "cpcb_station",
            "station"
        ]
    )


    out = pd.DataFrame()

    out[
        "location"
    ] = (
        temp[
            location_col
        ]
        .astype(str)
        .str.strip()
    )


    # Coordinates are OPTIONAL.
    if lat_col is not None:

        out[
            "latitude_input"
        ] = pd.to_numeric(
            temp[
                lat_col
            ],
            errors="coerce"
        )

    else:

        out[
            "latitude_input"
        ] = np.nan


    if lon_col is not None:

        out[
            "longitude_input"
        ] = pd.to_numeric(
            temp[
                lon_col
            ],
            errors="coerce"
        )

    else:

        out[
            "longitude_input"
        ] = np.nan


    if representative_col is not None:

        out[
            "representative_station"
        ] = (
            temp[
                representative_col
            ]
            .astype(str)
            .str.strip()
        )

    else:

        out[
            "representative_station"
        ] = ""


    normalized_tables.append(
        out
    )


if not normalized_tables:

    raise RuntimeError(
        "Could not find a locality/name column "
        "in the Pune location master."
    )


locations = pd.concat(
    normalized_tables,
    ignore_index=True
)


locations = locations[
    locations[
        "location"
    ].ne("")
]


locations = locations[
    ~locations[
        "location"
    ].str.lower().isin(
        [
            "nan",
            "none",
            "null"
        ]
    )
]


locations[
    "location_key"
] = (
    locations[
        "location"
    ]
    .map(norm)
)


locations = locations.drop_duplicates(
    "location_key"
).reset_index(
    drop=True
)


if len(locations) < 50:

    raise RuntimeError(
        f"Only {len(locations)} unique Pune "
        "locations were found. Need 100+."
    )


# Default to first 100+ locations.
# We process exactly 100 by default.
locations = locations.head(
    100
).copy()


print(
    "\n100-locality master loaded:"
)

print(
    "Locations:",
    len(locations)
)


print(
    "\nSample locations:"
)

for location in locations[
    "location"
].head(20):

    print(
        " -",
        location
    )


# ============================================================
# LOAD CPCB HISTORICAL DATA
# ============================================================

CPCB_PATH = find_file(
    CPCB_FILES,
    "Pune CPCB historical dataset"
)

cpcb = pd.read_csv(
    CPCB_PATH
)


cpcb_station_col = find_column(
    cpcb,
    [
        "station_name",
        "station",
        "site"
    ]
)

timestamp_col = find_column(
    cpcb,
    [
        "timestamp",
        "datetime",
        "date_time",
        "date",
        "time"
    ]
)


if cpcb_station_col is None:

    raise RuntimeError(
        "CPCB dataset has no station_name column."
    )

if timestamp_col is None:

    raise RuntimeError(
        "CPCB dataset has no timestamp column."
    )


cpcb[
    "_station"
] = (
    cpcb[
        cpcb_station_col
    ]
    .astype(str)
    .str.strip()
)


cpcb[
    "_timestamp"
] = pd.to_datetime(
    cpcb[
        timestamp_col
    ],
    errors="coerce"
)


cpcb = cpcb.dropna(
    subset=[
        "_timestamp"
    ]
).copy()


cpcb = cpcb.sort_values(
    [
        "_station",
        "_timestamp"
    ]
)


actual_stations = sorted(
    cpcb[
        "_station"
    ]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)


print(
    "\nCPCB stations:",
    len(actual_stations)
)

for station in actual_stations:

    print(
        " -",
        station
    )


# ============================================================
# RESOLVE REPRESENTATIVE CPCB STATION
# ============================================================

def match_station(
    requested
):

    requested_norm = norm(
        requested
    )


    if requested_norm in {
        "",
        "nan",
        "none"
    }:

        return None


    # Exact
    for station in actual_stations:

        if norm(
            station
        ) == requested_norm:

            return station


    # Partial
    for station in actual_stations:

        station_norm = norm(
            station
        )

        if (
            requested_norm in station_norm
            or
            station_norm in requested_norm
        ):

            return station


    return None


locations[
    "resolved_cpcb_station"
] = (
    locations[
        "representative_station"
    ]
    .map(
        match_station
    )
)


# ============================================================
# WEATHERAPI
# ============================================================

API_KEY = os.getenv(
    "WEATHER_API_KEY"
)


if not API_KEY:

    raise RuntimeError(
        "WEATHER_API_KEY is missing from .env"
    )


def weatherapi_query(
    row
):

    lat = row[
        "latitude_input"
    ]

    lon = row[
        "longitude_input"
    ]

    # If coordinates are already available,
    # use the coordinates.
    if (
        pd.notna(lat)
        and
        pd.notna(lon)
    ):

        return (
            f"{float(lat)},"
            f"{float(lon)}"
        )


    # Otherwise use a fully qualified Pune
    # locality name.
    return (
        f"{row['location']}, "
        "Pune, Maharashtra, India"
    )


def fetch_weather(
    row
):

    query = weatherapi_query(
        row
    )


    url = (
        "https://api.weatherapi.com/v1/"
        "current.json"
    )


    params = {

        "key":
            API_KEY,

        "q":
            query,

        "aqi":
            "yes"
    }


    for attempt in range(
        1,
        4
    ):

        try:

            response = requests.get(
                url,
                params=params,
                timeout=30
            )


            if response.ok:

                data = response.json()

                return {
                    "status":
                        "OK",

                    "query":
                        query,

                    "data":
                        data,

                    "error":
                        None
                }


            try:

                payload = response.json()

            except Exception:

                payload = {
                    "raw":
                        response.text
                }


            error = (
                payload.get(
                    "error",
                    {}
                )
                if isinstance(
                    payload,
                    dict
                )
                else {}
            )


            message = (
                error.get(
                    "message"
                )
                if isinstance(
                    error,
                    dict
                )
                else str(
                    payload
                )
            )


            if response.status_code in {
                429,
                500,
                502,
                503,
                504
            }:

                time.sleep(
                    attempt * 2
                )

                continue


            return {
                "status":
                    "ERROR",

                "query":
                    query,

                "data":
                    None,

                "error":
                    (
                        f"HTTP {response.status_code}: "
                        f"{message}"
                    )
            }


        except Exception as exc:

            if attempt == 3:

                return {
                    "status":
                        "ERROR",

                    "query":
                        query,

                    "data":
                        None,

                    "error":
                        str(exc)
                }


    return {
        "status":
            "ERROR",

        "query":
            query,

        "data":
            None,

        "error":
            "WeatherAPI failed after retries."
    }


# ============================================================
# FETCH ONE LOCALITY
# ============================================================

def fetch_locality(
    row
):

    response = fetch_weather(
        row
    )


    result = {

        "location":
            row[
                "location"
            ],

        "latitude_input":
            clean_value(
                row[
                    "latitude_input"
                ]
            ),

        "longitude_input":
            clean_value(
                row[
                    "longitude_input"
                ]
            ),

        "representative_cpcb_station":
            row[
                "representative_station"
            ],

        "resolved_cpcb_station":
            row[
                "resolved_cpcb_station"
            ],

        "weatherapi_query":
            response[
                "query"
            ],

        "weatherapi_status":
            response[
                "status"
            ],

        "weatherapi_error":
            response[
                "error"
            ]

    }


    if response[
        "data"
    ] is None:

        return result


    data = response[
        "data"
    ]


    location = data.get(
        "location",
        {}
    )

    current = data.get(
        "current",
        {}
    )

    air = (
        current.get(
            "air_quality",
            {}
        )
        or {}
    )


    # WeatherAPI itself gives us the
    # coordinates when the input was a name.
    result.update({

        "latitude":
            location.get(
                "lat"
            ),

        "longitude":
            location.get(
                "lon"
            ),

        "weatherapi_name":
            location.get(
                "name"
            ),

        "weatherapi_region":
            location.get(
                "region"
            ),

        "weatherapi_country":
            location.get(
                "country"
            ),

        "weatherapi_localtime":
            location.get(
                "localtime"
            ),

        "weatherapi_last_updated":
            current.get(
                "last_updated"
            ),

        # WEATHER
        "temperature_c":
            current.get(
                "temp_c"
            ),

        "feelslike_c":
            current.get(
                "feelslike_c"
            ),

        "humidity":
            current.get(
                "humidity"
            ),

        "wind_speed_kph":
            current.get(
                "wind_kph"
            ),

        "wind_direction":
            current.get(
                "wind_dir"
            ),

        "wind_degree":
            current.get(
                "wind_degree"
            ),

        "rainfall_mm":
            current.get(
                "precip_mm"
            ),

        "pressure_mb":
            current.get(
                "pressure_mb"
            ),

        "visibility_km":
            current.get(
                "vis_km"
            ),

        "uv":
            current.get(
                "uv"
            ),

        "condition":
            (
                current.get(
                    "condition",
                    {}
                )
                or {}
            ).get(
                "text"
            ),

        # AIR QUALITY
        "pm25_weatherapi":
            air.get(
                "pm2_5"
            ),

        "pm10_weatherapi":
            air.get(
                "pm10"
            ),

        "co_weatherapi":
            air.get(
                "co"
            ),

        "no2_weatherapi":
            air.get(
                "no2"
            ),

        "so2_weatherapi":
            air.get(
                "so2"
            ),

        "o3_weatherapi":
            air.get(
                "o3"
            ),

        "us_epa_index":
            air.get(
                "us-epa-index"
            ),

        "gb_defra_index":
            air.get(
                "gb-defra-index"
            )

    })


    return result


# ============================================================
# WEATHER FETCH FOR 100 LOCATIONS
# ============================================================

print("")
print(
    "Fetching live WeatherAPI data..."
)

weather_results = []


with ThreadPoolExecutor(
    max_workers=5
) as executor:

    futures = {

        executor.submit(
            fetch_locality,
            row
        ):
            idx

        for idx, row
        in locations.iterrows()
    }


    completed = 0


    for future in as_completed(
        futures
    ):

        completed += 1

        idx = futures[
            future
        ]


        try:

            result = future.result()

        except Exception as exc:

            row = locations.iloc[
                idx
            ]

            result = {

                "location":
                    row[
                        "location"
                    ],

                "representative_cpcb_station":
                    row[
                        "representative_station"
                    ],

                "resolved_cpcb_station":
                    row[
                        "resolved_cpcb_station"
                    ],

                "weatherapi_status":
                    "ERROR",

                "weatherapi_error":
                    str(exc)
            }


        weather_results.append(
            result
        )


        if (
            completed % 10 == 0
            or
            completed == len(
                locations
            )
        ):

            print(
                f"WeatherAPI: "
                f"{completed}/{len(locations)}"
            )


weather_df = pd.DataFrame(
    weather_results
)


weather_df = weather_df.sort_values(
    "location"
).reset_index(
    drop=True
)


# ============================================================
# SAVE LIVE WEATHER DATASET
# ============================================================

WEATHER_DATASET = (
    PROCESSED_DIR
    / "pune_100_locality_weather.csv"
)

weather_df.to_csv(
    WEATHER_DATASET,
    index=False
)


weather_success = int(
    weather_df[
        "weatherapi_status"
    ]
    .eq(
        "OK"
    )
    .sum()
)


print("")
print("=" * 75)
print("WEATHER DATASET COMPLETE")
print("=" * 75)

print(
    "Total localities:",
    len(weather_df)
)

print(
    "WeatherAPI successful:",
    weather_success
)

print(
    "WeatherAPI failed:",
    len(weather_df)
    -
    weather_success
)

print(
    "Dataset:",
    WEATHER_DATASET
)


# ============================================================
# CPCB FEATURE HELPERS
# ============================================================

def raw_column(
    base
):

    base_norm = norm(
        base
    )


    for column in cpcb.columns:

        if norm(column) == base_norm:

            return column


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
            "rain",
            "rf"
        ],

        "pressure": [
            "pressure",
            "bp"
        ]
    }


    for semantic, choices in aliases.items():

        if base_norm != semantic:
            continue

        for choice in choices:

            for column in cpcb.columns:

                if norm(column) == norm(
                    choice
                ):

                    return column


    return None


def get_history(
    station
):

    if (
        station is None
        or
        str(station).strip() == ""
    ):

        return pd.DataFrame()


    result = cpcb[
        cpcb[
            "_station"
        ]
        .astype(str)
        .str.lower()
        ==
        str(station)
        .lower()
    ].copy()


    return result.sort_values(
        "_timestamp"
    )


# ============================================================
# BUILD XGBOOST VECTOR
# ============================================================

def build_features(
    locality_row,
    weather_row
):

    station = (
        locality_row[
            "resolved_cpcb_station"
        ]
    )


    history = get_history(
        station
    )


    if history.empty:

        return None, (
            f"No CPCB history found for "
            f"{station}"
        )


    weather = {

        "pm25":
            weather_row.get(
                "pm25_weatherapi"
            ),

        "pm10":
            weather_row.get(
                "pm10_weatherapi"
            ),

        "co":
            weather_row.get(
                "co_weatherapi"
            ),

        "no2":
            weather_row.get(
                "no2_weatherapi"
            ),

        "so2":
            weather_row.get(
                "so2_weatherapi"
            ),

        "o3":
            weather_row.get(
                "o3_weatherapi"
            ),

        "temperature":
            weather_row.get(
                "temperature_c"
            ),

        "humidity":
            weather_row.get(
                "humidity"
            ),

        "wind_speed":
            (
                float(
                    weather_row[
                        "wind_speed_kph"
                    ]
                )
                / 3.6
                if pd.notna(
                    weather_row.get(
                        "wind_speed_kph"
                    )
                )
                else None
            ),

        "wind_speed_kph":
            weather_row.get(
                "wind_speed_kph"
            ),

        "rainfall":
            weather_row.get(
                "rainfall_mm"
            ),

        "pressure":
            weather_row.get(
                "pressure_mb"
            )
    }


    live_time = pd.to_datetime(
        weather_row.get(
            "weatherapi_localtime"
        ),
        errors="coerce"
    )


    if pd.isna(
        live_time
    ):

        live_time = history[
            "_timestamp"
        ].iloc[-1]


    values = {}


    for feature in FEATURES:

        f = norm(
            feature
        )

        value = None


        # ----------------------------------------------------
        # LIVE WEATHERAPI VARIABLES
        # ----------------------------------------------------

        if f in {
            "pm25",
            "pm2_5"
        }:

            value = weather[
                "pm25"
            ]

        elif f == "pm10":

            value = weather[
                "pm10"
            ]

        elif f == "co":

            value = weather[
                "co"
            ]

        elif f == "no2":

            value = weather[
                "no2"
            ]

        elif f == "so2":

            value = weather[
                "so2"
            ]

        elif f == "o3":

            value = weather[
                "o3"
            ]

        elif f in {
            "temperature",
            "temperature_c",
            "temp",
            "temp_c"
        }:

            value = weather[
                "temperature"
            ]

        elif f in {
            "humidity",
            "rh"
        }:

            value = weather[
                "humidity"
            ]

        elif f in {
            "wind_speed",
            "wind_speed_mps",
            "ws"
        }:

            value = weather[
                "wind_speed"
            ]

        elif f in {
            "wind_speed_kph",
            "wind_kph"
        }:

            value = weather[
                "wind_speed_kph"
            ]

        elif f in {
            "rainfall",
            "rainfall_mm",
            "rain",
            "rf"
        }:

            value = weather[
                "rainfall"
            ]

        elif f in {
            "pressure",
            "pressure_mb",
            "bp"
        }:

            value = weather[
                "pressure"
            ]


        # ----------------------------------------------------
        # STATION ONE-HOT
        # ----------------------------------------------------

        if value is None:

            for prefix in [
                "station_",
                "station_name_",
                "site_",
                "site_name_"
            ]:

                if f.startswith(
                    prefix
                ):

                    encoded = f[
                        len(prefix):
                    ]

                    value = (
                        1.0
                        if norm(
                            station
                        )
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
                        2
                        * np.pi
                        * live_time.hour
                        / 24
                    )
                )

            elif f in {
                "hour_cos",
                "cos_hour"
            }:

                value = float(
                    np.cos(
                        2
                        * np.pi
                        * live_time.hour
                        / 24
                    )
                )

            elif f in {
                "dow_sin",
                "sin_dow"
            }:

                value = float(
                    np.sin(
                        2
                        * np.pi
                        * live_time.dayofweek
                        / 7
                    )
                )

            elif f in {
                "dow_cos",
                "cos_dow"
            }:

                value = float(
                    np.cos(
                        2
                        * np.pi
                        * live_time.dayofweek
                        / 7
                    )
                )


        # ----------------------------------------------------
        # LAGS FROM REPRESENTATIVE CPCB STATION
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


            if match:

                base = match.group(1)

                lag = int(
                    match.group(2)
                )

                column = raw_column(
                    base
                )


                if column is not None:

                    series = pd.to_numeric(
                        history[
                            column
                        ],
                        errors="coerce"
                    ).dropna()


                    if len(series) >= lag:

                        value = float(
                            series.iloc[
                                -lag
                            ]
                        )


        # ----------------------------------------------------
        # ROLLING FEATURES
        # ----------------------------------------------------

        if value is None:

            match = re.match(
                r"(.+)_rolling_?(\d+)$",
                f
            )

            if match:

                base = match.group(1)

                window = int(
                    match.group(2)
                )

                column = raw_column(
                    base
                )


                if column is not None:

                    series = pd.to_numeric(
                        history[
                            column
                        ],
                        errors="coerce"
                    ).dropna()


                    if not series.empty:

                        value = float(
                            series.tail(
                                window
                            ).mean()
                        )


        # ----------------------------------------------------
        # CURRENT CPCB FALLBACK
        # ----------------------------------------------------

        if value is None:

            column = raw_column(
                feature
            )

            if column is not None:

                series = pd.to_numeric(
                    history[
                        column
                    ],
                    errors="coerce"
                ).dropna()


                if not series.empty:

                    value = float(
                        series.iloc[
                            -1
                        ]
                    )


        # ----------------------------------------------------
        # MODEL MEDIAN
        # ----------------------------------------------------

        if value is None:

            value = MEDIANS.get(
                f
            )


        if value is None:

            return None, (
                f"Could not construct "
                f"feature: {feature}"
            )


        values[
            feature
        ] = float(
            value
        )


    X = pd.DataFrame(
        [
            values
        ],
        columns=FEATURES
    )


    return X, None


# ============================================================
# SHAP EXPLAINER
# ============================================================

print("")
print(
    "Creating SHAP TreeExplainer..."
)

EXPLAINER = shap.TreeExplainer(
    MODEL
)


# ============================================================
# ANALYZE 100 LOCALITIES
# ============================================================

results = []


for index, locality_row in locations.iterrows():

    location = locality_row[
        "location"
    ]


    matching = weather_df[
        weather_df[
            "location"
        ]
        ==
        location
    ]


    if matching.empty:

        results.append({

            "location":
                location,

            "shap_status":
                "UNAVAILABLE",

            "reason":
                "WeatherAPI row missing"

        })

        continue


    weather_row = matching.iloc[
        0
    ]


    if (
        weather_row[
            "weatherapi_status"
        ]
        !=
        "OK"
    ):

        results.append({

            "location":
                location,

            "latitude":
                weather_row.get(
                    "latitude"
                ),

            "longitude":
                weather_row.get(
                    "longitude"
                ),

            "resolved_cpcb_station":
                locality_row[
                    "resolved_cpcb_station"
                ],

            "weatherapi_status":
                weather_row[
                    "weatherapi_status"
                ],

            "shap_status":
                "UNAVAILABLE",

            "reason":
                weather_row.get(
                    "weatherapi_error"
                )

        })

        continue


    X, error = build_features(
        locality_row,
        weather_row
    )


    if X is None:

        results.append({

            "location":
                location,

            "latitude":
                weather_row.get(
                    "latitude"
                ),

            "longitude":
                weather_row.get(
                    "longitude"
                ),

            "resolved_cpcb_station":
                locality_row[
                    "resolved_cpcb_station"
                ],

            "shap_status":
                "UNAVAILABLE",

            "reason":
                error

        })

        continue


    try:

        prediction = float(
            MODEL.predict(
                X
            )[0]
        )


        shap_values = np.asarray(
            EXPLAINER.shap_values(
                X
            )
        )


        if shap_values.ndim == 3:

            shap_values = (
                shap_values[:, :, 0]
            )


        shap_row = shap_values[
            0
        ]


        expected = float(
            np.asarray(
                EXPLAINER.expected_value
            ).reshape(-1)[0]
        )


        reconstructed = float(
            expected
            +
            shap_row.sum()
        )


        additivity_error = abs(
            prediction
            -
            reconstructed
        )


        additivity_pass = (
            additivity_error
            <=
            max(
                1e-4,
                abs(prediction) * 1e-4
            )
        )


        local = pd.DataFrame({

            "feature":
                FEATURES,

            "value":
                X.iloc[0].values,

            "shap":
                shap_row

        })


        local[
            "abs_shap"
        ] = local[
            "shap"
        ].abs()


        local = local.sort_values(
            "abs_shap",
            ascending=False
        ).reset_index(
            drop=True
        )


        result = {

            "location":
                location,

            "latitude":
                weather_row.get(
                    "latitude"
                ),

            "longitude":
                weather_row.get(
                    "longitude"
                ),

            "weatherapi_name":
                weather_row.get(
                    "weatherapi_name"
                ),

            "representative_cpcb_station":
                locality_row[
                    "representative_station"
                ],

            "resolved_cpcb_station":
                locality_row[
                    "resolved_cpcb_station"
                ],

            "weatherapi_query":
                weather_row.get(
                    "weatherapi_query"
                ),

            "weatherapi_status":
                weather_row.get(
                    "weatherapi_status"
                ),

            "weatherapi_last_updated":
                weather_row.get(
                    "weatherapi_last_updated"
                ),

            "temperature_c":
                weather_row.get(
                    "temperature_c"
                ),

            "humidity":
                weather_row.get(
                    "humidity"
                ),

            "wind_speed_kph":
                weather_row.get(
                    "wind_speed_kph"
                ),

            "rainfall_mm":
                weather_row.get(
                    "rainfall_mm"
                ),

            "weatherapi_pm25":
                weather_row.get(
                    "pm25_weatherapi"
                ),

            "weatherapi_pm10":
                weather_row.get(
                    "pm10_weatherapi"
                ),

            "weatherapi_co":
                weather_row.get(
                    "co_weatherapi"
                ),

            "weatherapi_no2":
                weather_row.get(
                    "no2_weatherapi"
                ),

            "weatherapi_so2":
                weather_row.get(
                    "so2_weatherapi"
                ),

            "weatherapi_o3":
                weather_row.get(
                    "o3_weatherapi"
                ),

            "predicted_pm25_next_1h":
                prediction,

            "expected_value":
                expected,

            "reconstructed_prediction":
                reconstructed,

            "shap_additivity_error":
                additivity_error,

            "shap_additivity_pass":
                bool(
                    additivity_pass
                ),

            "shap_status":
                "AVAILABLE"
        }


        for i in range(
            min(
                10,
                len(local)
            )
        ):

            row = local.iloc[
                i
            ]

            number = i + 1

            direction = (
                "INCREASES_PREDICTION"
                if row["shap"] > 0
                else
                "DECREASES_PREDICTION"
            )


            result[
                f"factor_{number}"
            ] = row[
                "feature"
            ]

            result[
                f"factor_{number}_value"
            ] = float(
                row[
                    "value"
                ]
            )

            result[
                f"factor_{number}_shap"
            ] = float(
                row[
                    "shap"
                ]
            )

            result[
                f"factor_{number}_direction"
            ] = direction


        results.append(
            result
        )


    except Exception as exc:

        results.append({

            "location":
                location,

            "latitude":
                weather_row.get(
                    "latitude"
                ),

            "longitude":
                weather_row.get(
                    "longitude"
                ),

            "resolved_cpcb_station":
                locality_row[
                    "resolved_cpcb_station"
                ],

            "shap_status":
                "ERROR",

            "reason":
                str(exc)

        })


    if (
        (index + 1) % 10 == 0
        or
        index == len(locations) - 1
    ):

        print(
            f"SHAP progress: "
            f"{index + 1}/{len(locations)}"
        )


# ============================================================
# SAVE MAIN DATASET
# ============================================================

result_df = pd.DataFrame(
    results
)


FINAL_DATASET = (
    PROCESSED_DIR
    / "pune_100_locality_environment_shap.csv"
)


FINAL_JSON = (
    OUTPUT_DIR
    / "pune_100_locality_environment_shap.json"
)


result_df.to_csv(
    FINAL_DATASET,
    index=False
)


with open(
    FINAL_JSON,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        results,
        f,
        indent=2,
        ensure_ascii=False,
        default=lambda x:
            x.item()
            if hasattr(
                x,
                "item"
            )
            else str(x)
    )


# ============================================================
# GLOBAL SHAP SUMMARY
# ============================================================

global_rows = []


for _, row in result_df.iterrows():

    for i in range(
        1,
        11
    ):

        feature = row.get(
            f"factor_{i}"
        )

        shap_value = row.get(
            f"factor_{i}_shap"
        )


        if (
            pd.notna(feature)
            and
            pd.notna(shap_value)
        ):

            global_rows.append({

                "feature":
                    feature,

                "shap":
                    float(
                        shap_value
                    ),

                "abs_shap":
                    abs(
                        float(
                            shap_value
                        )
                    )

            })


if global_rows:

    global_df = pd.DataFrame(
        global_rows
    )


    global_summary = (
        global_df
        .groupby(
            "feature"
        )
        .agg(

            mean_abs_shap=(
                "abs_shap",
                "mean"
            ),

            mean_shap=(
                "shap",
                "mean"
            ),

            locality_count=(
                "shap",
                "count"
            )

        )
        .reset_index()
        .sort_values(
            "mean_abs_shap",
            ascending=False
        )
    )


    total = global_summary[
        "mean_abs_shap"
    ].sum()


    if total > 0:

        global_summary[
            "importance_percent"
        ] = (
            global_summary[
                "mean_abs_shap"
            ]
            /
            total
            * 100
        )

    else:

        global_summary[
            "importance_percent"
        ] = 0


else:

    global_summary = pd.DataFrame()


GLOBAL_PATH = (
    OUTPUT_DIR
    / "pune_100_locality_global_shap.csv"
)


global_summary.to_csv(
    GLOBAL_PATH,
    index=False
)


# ============================================================
# FINAL SUMMARY
# ============================================================

available = int(
    result_df[
        "shap_status"
    ]
    .eq(
        "AVAILABLE"
    )
    .sum()
)


unavailable = (
    len(result_df)
    -
    available
)


weather_success = int(
    weather_df[
        "weatherapi_status"
    ]
    .eq(
        "OK"
    )
    .sum()
)


print("")
print("=" * 75)
print("PUNE 100 LOCALITY SHAP COMPLETE")
print("=" * 75)

print(
    "\nTotal localities:",
    len(result_df)
)

print(
    "WeatherAPI successful:",
    weather_success
)

print(
    "SHAP available:",
    available
)

print(
    "SHAP unavailable/error:",
    unavailable
)


print("")
print(
    "MAIN DATASET:"
)

print(
    FINAL_DATASET
)


print("")
print(
    "JSON REPORT:"
)

print(
    FINAL_JSON
)


print("")
print(
    "GLOBAL SHAP:"
)

print(
    GLOBAL_PATH
)


print("")
print(
    "SAMPLE:"
)

columns = [

    "location",

    "latitude",

    "longitude",

    "resolved_cpcb_station",

    "weatherapi_pm25",

    "temperature_c",

    "humidity",

    "predicted_pm25_next_1h",

    "factor_1",

    "factor_1_shap",

    "factor_2",

    "factor_2_shap",

    "factor_3",

    "factor_3_shap"

]


columns = [
    c
    for c in columns
    if c in result_df.columns
]


print(
    result_df[
        columns
    ]
    .head(20)
    .to_string(
        index=False
    )
)


print("")
print("=" * 75)
print("100 PUNE LOCALITIES PROCESSED")
print("=" * 75)

