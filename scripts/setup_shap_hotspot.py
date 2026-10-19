from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import requests
from xgboost import XGBRegressor


ROOT = Path(__file__).resolve().parents[1]

DATA_ROOTS = [
    ROOT / "data" / "raw",
    ROOT / "data" / "processed",
    ROOT / "data",
]

MODEL_DIR = ROOT / "models" / "forecasting"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_DIR = ROOT / "data" / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = MODEL_DIR / "pm25_xgboost.pkl"
HOTSPOT_PATH = OUTPUT_DIR / "pune_hotspot_points.csv"
GEOCODE_CACHE = OUTPUT_DIR / "station_geocoding.json"

FEATURES = [
    "pm10",
    "no2",
    "so2",
    "co_mg_m3",
    "ozone",
    "temperature_c",
    "humidity",
    "wind_speed_ms",
    "wind_direction_deg",
    "rainfall_mm",
    "hour",
    "dayofweek",
]


def norm(value):
    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(value).lower(),
    )


def find_column(columns, aliases):
    normalized = {
        norm(c): c
        for c in columns
    }

    for alias in aliases:
        if norm(alias) in normalized:
            return normalized[norm(alias)]

    return None


def numeric(series):
    return pd.to_numeric(
        series,
        errors="coerce",
    )


def read_station_file(path):
    try:
        sample = pd.read_csv(
            path,
            nrows=3,
            low_memory=False,
        )
    except Exception:
        return None

    cols = sample.columns

    pm25_col = find_column(
        cols,
        [
            "PM2.5 (µg/m³)",
            "PM2.5",
            "PM25",
            "pm25",
            "pm2_5",
        ],
    )

    if pm25_col is None:
        return None

    mapping = {
        "pm25": pm25_col,
        "pm10": find_column(
            cols,
            [
                "PM10 (µg/m³)",
                "PM10",
                "pm10",
            ],
        ),
        "no2": find_column(
            cols,
            [
                "NO2 (µg/m³)",
                "NO2",
                "no2",
            ],
        ),
        "so2": find_column(
            cols,
            [
                "SO2 (µg/m³)",
                "SO2",
                "so2",
            ],
        ),
        "co": find_column(
            cols,
            [
                "CO (mg/m³)",
                "CO",
                "co",
            ],
        ),
        "ozone": find_column(
            cols,
            [
                "Ozone (µg/m³)",
                "Ozone",
                "O3",
                "o3",
            ],
        ),
        "temperature": find_column(
            cols,
            [
                "AT (°C)",
                "AT",
                "temperature",
                "temperature_c",
            ],
        ),
        "humidity": find_column(
            cols,
            [
                "RH (%)",
                "RH",
                "humidity",
            ],
        ),
        "wind_speed": find_column(
            cols,
            [
                "WS (m/s)",
                "WS",
                "wind_speed",
            ],
        ),
        "wind_direction": find_column(
            cols,
            [
                "WD (deg)",
                "WD",
                "wind_direction",
            ],
        ),
        "rainfall": find_column(
            cols,
            [
                "RF (mm)",
                "RF",
                "rainfall",
            ],
        ),
        "timestamp": find_column(
            cols,
            [
                "Timestamp",
                "timestamp",
                "datetime",
                "date",
            ],
        ),
        "station": find_column(
            cols,
            [
                "Station Name",
                "station_name",
                "station",
            ],
        ),
    }

    usecols = [
        x for x in mapping.values()
        if x is not None
    ]

    try:
        df = pd.read_csv(
            path,
            usecols=usecols,
            low_memory=False,
        )
    except Exception:
        return None

    rename = {}

    for logical, original in mapping.items():
        if original is not None:
            rename[original] = logical

    df = df.rename(
        columns=rename
    )

    if "station" not in df.columns:
        df["station"] = path.stem

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            errors="coerce",
        )

    numeric_columns = [
        "pm25",
        "pm10",
        "no2",
        "so2",
        "co",
        "ozone",
        "temperature",
        "humidity",
        "wind_speed",
        "wind_direction",
        "rainfall",
    ]

    for column in numeric_columns:
        if column in df.columns:
            df[column] = numeric(
                df[column]
            )

    return df


def discover_files():
    paths = []

    for root in DATA_ROOTS:
        if not root.exists():
            continue

        for path in root.rglob("*.csv"):
            if path.name.lower() in {
                "pune_hotspot_points.csv",
                "shap_training_data.csv",
                "training_data.csv",
            }:
                continue

            paths.append(path)

    return sorted(
        set(paths)
    )


def build_training_data():
    frames = []
    files = discover_files()

    print("")
    print("=" * 70)
    print("SEARCHING CPCB DATA")
    print("=" * 70)

    for path in files:
        df = read_station_file(path)

        if df is None:
            continue

        if "pm25" not in df.columns:
            continue

        df = df[
            df["pm25"].notna()
        ].copy()

        if len(df) == 0:
            continue

        print(
            f"FOUND: {path} | rows={len(df)}"
        )

        frames.append(df)

    if not frames:
        raise RuntimeError(
            "No CPCB CSV with PM2.5 was found. "
            "Put your station CSV files under "
            "data\\raw or data\\processed."
        )

    data = pd.concat(
        frames,
        ignore_index=True,
    )

    result = pd.DataFrame()

    result["pm25"] = data["pm25"]

    result["pm10"] = (
        data["pm10"]
        if "pm10" in data
        else np.nan
    )

    result["no2"] = (
        data["no2"]
        if "no2" in data
        else np.nan
    )

    result["so2"] = (
        data["so2"]
        if "so2" in data
        else np.nan
    )

    result["co_mg_m3"] = (
        data["co"]
        if "co" in data
        else np.nan
    )

    result["ozone"] = (
        data["ozone"]
        if "ozone" in data
        else np.nan
    )

    result["temperature_c"] = (
        data["temperature"]
        if "temperature" in data
        else np.nan
    )

    result["humidity"] = (
        data["humidity"]
        if "humidity" in data
        else np.nan
    )

    result["wind_speed_ms"] = (
        data["wind_speed"]
        if "wind_speed" in data
        else np.nan
    )

    result["wind_direction_deg"] = (
        data["wind_direction"]
        if "wind_direction" in data
        else np.nan
    )

    result["rainfall_mm"] = (
        data["rainfall"]
        if "rainfall" in data
        else np.nan
    )

    if "timestamp" in data.columns:
        result["timestamp"] = data[
            "timestamp"
        ]

        result["hour"] = (
            data["timestamp"]
            .dt.hour
        )

        result["dayofweek"] = (
            data["timestamp"]
            .dt.dayofweek
        )
    else:
        result["hour"] = 12
        result["dayofweek"] = 3

    for feature in FEATURES:
        if feature not in result:
            result[feature] = np.nan

    result = result[
        [
            "pm25",
            *FEATURES,
        ]
    ]

    return result


def train_model():
    data = build_training_data()

    print("")
    print("=" * 70)
    print("PREPARING XGBOOST DATA")
    print("=" * 70)

    X = data[
        FEATURES
    ].copy()

    y = pd.to_numeric(
        data["pm25"],
        errors="coerce",
    )

    valid = y.notna()

    X = X.loc[valid]
    y = y.loc[valid]

    for feature in FEATURES:
        X[feature] = pd.to_numeric(
            X[feature],
            errors="coerce",
        )

    medians = {}

    for feature in FEATURES:
        median = X[feature].median()

        if pd.isna(median):
            median = 0.0

        medians[feature] = float(
            median
        )

        X[feature] = X[feature].fillna(
            median
        )

    valid = y.notna()

    X = X.loc[valid]
    y = y.loc[valid]

    if len(X) < 500:
        raise RuntimeError(
            f"Only {len(X)} valid rows available. "
            "At least 500 rows are recommended."
        )

    # Prevent an enormous training job.
    if len(X) > 300000:
        rng = np.random.RandomState(42)

        indices = rng.choice(
            len(X),
            size=300000,
            replace=False,
        )

        X = X.iloc[indices]
        y = y.iloc[indices]

    split = int(
        len(X) * 0.80
    )

    X_train = X.iloc[:split]
    X_test = X.iloc[split:]

    y_train = y.iloc[:split]
    y_test = y.iloc[split:]

    print(
        f"Training rows: {len(X_train)}"
    )

    print(
        f"Testing rows: {len(X_test)}"
    )

    model = XGBRegressor(
        n_estimators=350,
        max_depth=8,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.85,
        objective="reg:squarederror",
        eval_metric="rmse",
        random_state=42,
        n_jobs=4,
    )

    model.fit(
        X_train,
        y_train,
        eval_set=[
            (
                X_test,
                y_test,
            )
        ],
        verbose=False,
    )

    prediction = model.predict(
        X_test
    )

    mae = float(
        np.mean(
            np.abs(
                prediction - y_test.values
            )
        )
    )

    rmse = float(
        np.sqrt(
            np.mean(
                (
                    prediction
                    - y_test.values
                ) ** 2
            )
        )
    )

    ss_res = float(
        np.sum(
            (
                prediction
                - y_test.values
            ) ** 2
        )
    )

    ss_tot = float(
        np.sum(
            (
                y_test.values
                - y_test.mean()
            ) ** 2
        )
    )

    r2 = (
        1
        - ss_res / ss_tot
        if ss_tot != 0
        else 0.0
    )

    package = {
        "model": model,
        "feature_names": FEATURES,
        "medians": medians,
        "metrics": {
            "MAE": round(mae, 4),
            "RMSE": round(rmse, 4),
            "R2": round(r2, 4),
            "training_rows": int(
                len(X_train)
            ),
            "testing_rows": int(
                len(X_test)
            ),
        },
    }

    joblib.dump(
        package,
        MODEL_PATH,
    )

    print("")
    print("=" * 70)
    print("XGBOOST TRAINED")
    print("=" * 70)
    print(
        f"MAE  : {mae:.4f}"
    )
    print(
        f"RMSE : {rmse:.4f}"
    )
    print(
        f"R2   : {r2:.4f}"
    )
    print(
        f"MODEL: {MODEL_PATH}"
    )

    return package


def get_station_data():
    frames = []

    for path in discover_files():

        df = read_station_file(
            path
        )

        if df is None:
            continue

        if "station" not in df.columns:
            continue

        if "pm25" not in df.columns:
            continue

        columns = [
            "station",
            "pm25",
        ]

        if "timestamp" in df:
            columns.append(
                "timestamp"
            )

        data = df[
            columns
        ].copy()

        if "timestamp" in data:
            data["timestamp"] = pd.to_datetime(
                data["timestamp"],
                errors="coerce",
            )

        data["pm25"] = pd.to_numeric(
            data["pm25"],
            errors="coerce",
        )

        data = data.dropna(
            subset=[
                "station",
                "pm25",
            ]
        )

        frames.append(
            data
        )

    if not frames:
        return pd.DataFrame()

    result = pd.concat(
        frames,
        ignore_index=True,
    )

    if "timestamp" in result:

        result = result.sort_values(
            "timestamp"
        )

        result = (
            result.groupby(
                "station",
                as_index=False,
            )
            .tail(1)
        )

    else:

        result = (
            result.groupby(
                "station",
                as_index=False,
            )["pm25"]
            .mean()
        )

    return result


def load_geocode_cache():
    if not GEOCODE_CACHE.exists():
        return {}

    try:
        return json.loads(
            GEOCODE_CACHE.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return {}


def save_geocode_cache(cache):
    GEOCODE_CACHE.write_text(
        json.dumps(
            cache,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def geocode_station(name, cache):
    key = str(name).strip()

    if key in cache:
        return cache[key]

    query_name = re.sub(
        r"\b(IITM|MPCB|CPCB)\b",
        "",
        key,
        flags=re.IGNORECASE,
    )

    query = (
        f"{query_name}, Pune, "
        f"Maharashtra, India"
    )

    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": query,
                "format": "jsonv2",
                "limit": 1,
            },
            headers={
                "User-Agent":
                    "AI-POLLUTION-SYSTEM/1.0"
            },
            timeout=20,
        )

        response.raise_for_status()

        results = response.json()

        if results:

            item = results[0]

            value = {
                "latitude": float(
                    item["lat"]
                ),
                "longitude": float(
                    item["lon"]
                ),
                "display_name":
                    item.get(
                        "display_name",
                        query,
                    ),
            }

            cache[key] = value
            save_geocode_cache(
                cache
            )

            print(
                f"GEOCODED: {key} -> "
                f"{value['latitude']}, "
                f"{value['longitude']}"
            )

            time.sleep(1)

            return value

    except Exception as exc:

        print(
            f"GEOCODE FAILED: "
            f"{key} | {exc}"
        )

    return None


def build_hotspot_dataset():
    data = get_station_data()

    if data.empty:
        print(
            "No station data found for hotspot generation."
        )
        return None

    print("")
    print("=" * 70)
    print("BUILDING HOTSPOT DATASET")
    print("=" * 70)

    cache = load_geocode_cache()

    rows = []

    for _, row in data.iterrows():

        station = str(
            row["station"]
        ).strip()

        point = geocode_station(
            station,
            cache,
        )

        if point is None:
            continue

        rows.append({
            "station_name": station,
            "latitude":
                point["latitude"],
            "longitude":
                point["longitude"],
            "pm25":
                float(row["pm25"]),
            "timestamp":
                (
                    str(row["timestamp"])
                    if
                    "timestamp" in row
                    and pd.notna(
                        row["timestamp"]
                    )
                    else ""
                ),
        })

    hotspot = pd.DataFrame(
        rows
    )

    if hotspot.empty:
        print(
            "No station could be geocoded."
        )
        return None

    hotspot = (
        hotspot
        .drop_duplicates(
            subset=[
                "station_name",
            ]
        )
    )

    hotspot.to_csv(
        HOTSPOT_PATH,
        index=False,
    )

    print("")
    print(
        f"Stations mapped: "
        f"{len(hotspot)}"
    )

    print(
        f"FILE: {HOTSPOT_PATH}"
    )

    print("")
    print(
        hotspot[
            [
                "station_name",
                "latitude",
                "longitude",
                "pm25",
            ]
        ].to_string(
            index=False
        )
    )

    return hotspot


def main():

    package = None

    if MODEL_PATH.exists():
        try:
            existing = joblib.load(
                MODEL_PATH
            )

            if (
                isinstance(
                    existing,
                    dict,
                )
                and existing.get(
                    "model"
                ) is not None
            ):
                package = existing

                print("")
                print(
                    "EXISTING XGBOOST MODEL FOUND"
                )
                print(
                    f"MODEL: {MODEL_PATH}"
                )

        except Exception:
            package = None

    if package is None:
        package = train_model()

    hotspot = build_hotspot_dataset()

    print("")
    print("=" * 70)
    print("SETUP COMPLETE")
    print("=" * 70)

    print(
        f"XGBoost model : "
        f"{MODEL_PATH.exists()}"
    )

    print(
        f"Hotspot data  : "
        f"{HOTSPOT_PATH.exists()}"
    )

    if package:
        print(
            "Model metrics:",
            package.get(
                "metrics",
                {},
            ),
        )


if __name__ == "__main__":
    main()
