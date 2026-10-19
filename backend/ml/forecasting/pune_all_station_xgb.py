from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor


ROOT = Path(__file__).resolve().parents[3]

DATA_PATH = ROOT / "data" / "processed" / "pune_cpcb_cleaned_hourly.csv"
MODEL_PATH = ROOT / "models" / "forecasting" / "pune_all_station_xgb.pkl"
FEATURES_PATH = ROOT / "models" / "forecasting" / "pune_all_station_xgb_features.pkl"
MEDIANS_PATH = ROOT / "models" / "forecasting" / "pune_all_station_xgb_medians.pkl"
METRICS_PATH = ROOT / "models" / "forecasting" / "pune_all_station_xgb_metrics.json"


ALIASES = {
    "timestamp": [
        "timestamp",
        "datetime",
        "date_time",
        "date",
    ],
    "station_name": [
        "station_name",
        "station",
        "location",
    ],
    "pm25": [
        "pm25",
        "pm2_5",
        "pm2.5",
        "PM2.5 (µg/m³)",
        "PM2.5",
    ],
    "pm10": [
        "pm10",
        "PM10 (µg/m³)",
        "PM10",
    ],
    "no2": [
        "no2",
        "NO2 (µg/m³)",
        "NO2",
    ],
    "so2": [
        "so2",
        "SO2 (µg/m³)",
        "SO2",
    ],
    "co": [
        "co",
        "CO (mg/m³)",
        "CO (µg/m³)",
        "CO",
    ],
    "o3": [
        "o3",
        "O3 (µg/m³)",
        "O3",
    ],
    "nh3": [
        "nh3",
        "NH3 (µg/m³)",
        "NH3",
    ],
    "temperature": [
        "temperature",
        "temp",
        "AT (°C)",
        "AT",
        "temperature_c",
    ],
    "humidity": [
        "humidity",
        "RH (%)",
        "RH",
        "relative_humidity",
    ],
    "pressure": [
        "pressure",
        "BP (mmHg)",
        "pressure_mb",
        "pressure_hpa",
    ],
    "wind_speed": [
        "wind_speed",
        "WS (m/s)",
        "WS",
        "wind_kph",
    ],
    "rainfall": [
        "rainfall",
        "RF (mm)",
        "RF",
        "precip_mm",
    ],
}


def normalize_name(value: Any) -> str:
    return (
        str(value)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace(".", "")
        .replace("-", "_")
        .replace("/", "_")
    )


def find_column(df: pd.DataFrame, aliases: list[str]) -> str | None:
    normalized = {
        normalize_name(c): c
        for c in df.columns
    }

    for alias in aliases:
        key = normalize_name(alias)
        if key in normalized:
            return normalized[key]

    for column in df.columns:
        c = normalize_name(column)
        for alias in aliases:
            a = normalize_name(alias)
            if a in c or c in a:
                return column

    return None


def normalize_dataset(df: pd.DataFrame) -> pd.DataFrame:
    output = pd.DataFrame(index=df.index)

    for target, aliases in ALIASES.items():
        column = find_column(df, aliases)

        if column is None:
            output[target] = np.nan
        else:
            output[target] = df[column]

    output["timestamp"] = pd.to_datetime(
        output["timestamp"],
        errors="coerce",
    )

    output["station_name"] = (
        output["station_name"]
        .astype(str)
        .str.strip()
    )

    numeric_columns = [
        c for c in output.columns
        if c not in {"timestamp", "station_name"}
    ]

    for column in numeric_columns:
        output[column] = pd.to_numeric(
            output[column],
            errors="coerce",
        )

    # WeatherAPI-style CO is sometimes µg/m³; CPCB CO may be mg/m³.
    # For training we do not force a unit conversion unless the original
    # source clearly identifies the unit.
    return output


def build_features(
    df: pd.DataFrame,
    training: bool = True,
):
    data = normalize_dataset(df)

    data = data.dropna(
        subset=["timestamp", "station_name", "pm25"]
    )

    data = data.sort_values(
        ["station_name", "timestamp"]
    ).reset_index(drop=True)

    data["hour"] = data["timestamp"].dt.hour
    data["day_of_week"] = data["timestamp"].dt.dayofweek
    data["month"] = data["timestamp"].dt.month
    data["day_of_year"] = data["timestamp"].dt.dayofyear

    base_features = [
        "pm25",
        "pm10",
        "no2",
        "so2",
        "co",
        "o3",
        "nh3",
        "temperature",
        "humidity",
        "pressure",
        "wind_speed",
        "rainfall",
        "hour",
        "day_of_week",
        "month",
        "day_of_year",
    ]

    lag_columns = [
        "pm25",
        "pm10",
        "no2",
        "so2",
        "co",
        "temperature",
        "humidity",
        "wind_speed",
        "rainfall",
    ]

    lags = [1, 3, 6, 12, 24]

    grouped = data.groupby(
        "station_name",
        group_keys=False,
    )

    features = list(base_features)

    for column in lag_columns:
        for lag in lags:
            name = f"{column}_lag_{lag}"
            data[name] = grouped[column].shift(lag)
            features.append(name)

    data["target_pm25_next_1h"] = grouped["pm25"].shift(-1)

    data = data.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    if training:
        data = data.dropna(
            subset=[
                "target_pm25_next_1h",
                "pm25_lag_1",
            ]
        )

    return data, features


def train():
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Missing dataset: {DATA_PATH}"
        )

    raw = pd.read_csv(DATA_PATH)

    data, features = build_features(
        raw,
        training=True,
    )

    if len(data) < 1000:
        raise RuntimeError(
            f"Only {len(data)} usable rows found. "
            "At least 1000 rows are required."
        )

    data["timestamp"] = pd.to_datetime(
        data["timestamp"]
    )

    unique_times = (
        data["timestamp"]
        .drop_duplicates()
        .sort_values()
        .reset_index(drop=True)
    )

    train_cut = unique_times.iloc[
        int(len(unique_times) * 0.70)
    ]

    validation_cut = unique_times.iloc[
        int(len(unique_times) * 0.85)
    ]

    train_df = data[
        data["timestamp"] <= train_cut
    ]

    validation_df = data[
        (data["timestamp"] > train_cut)
        & (data["timestamp"] <= validation_cut)
    ]

    test_df = data[
        data["timestamp"] > validation_cut
    ]

    medians = (
        train_df[features]
        .median(numeric_only=True)
        .fillna(0)
    )

    X_train = train_df[features].fillna(medians)
    y_train = train_df["target_pm25_next_1h"]

    X_validation = validation_df[features].fillna(medians)
    y_validation = validation_df["target_pm25_next_1h"]

    X_test = test_df[features].fillna(medians)
    y_test = test_df["target_pm25_next_1h"]

    model = XGBRegressor(
        n_estimators=500,
        learning_rate=0.03,
        max_depth=8,
        min_child_weight=5,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="reg:squarederror",
        eval_metric="rmse",
        random_state=42,
        n_jobs=-1,
        tree_method="hist",
    )

    model.fit(
        X_train,
        y_train,
        eval_set=[
            (X_validation, y_validation),
        ],
        verbose=False,
    )

    predictions = model.predict(X_test)

    rmse = float(
        np.sqrt(
            mean_squared_error(
                y_test,
                predictions,
            )
        )
    )

    metrics = {
        "model": "Pune All-Station XGBoost",
        "stations": sorted(
            data["station_name"].dropna().unique().tolist()
        ),
        "station_count": int(
            data["station_name"].nunique()
        ),
        "rows": int(len(data)),
        "train_rows": int(len(train_df)),
        "validation_rows": int(len(validation_df)),
        "test_rows": int(len(test_df)),
        "MAE": float(
            mean_absolute_error(
                y_test,
                predictions,
            )
        ),
        "RMSE": rmse,
        "R2": float(
            r2_score(
                y_test,
                predictions,
            )
        ),
        "target": "Next-hour PM2.5",
    }

    MODEL_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    joblib.dump(
        model,
        MODEL_PATH,
    )

    joblib.dump(
        features,
        FEATURES_PATH,
    )

    joblib.dump(
        medians.to_dict(),
        MEDIANS_PATH,
    )

    METRICS_PATH.write_text(
        pd.Series(metrics).to_json(
            indent=2
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 64)
    print("PUNE ALL-STATION XGBOOST TRAINED")
    print("=" * 64)
    print(f"Stations : {metrics['station_count']}")
    print(f"Rows     : {metrics['rows']:,}")
    print(f"MAE      : {metrics['MAE']:.4f}")
    print(f"RMSE     : {metrics['RMSE']:.4f}")
    print(f"R2       : {metrics['R2']:.4f}")
    print()
    print("Stations:")
    for station in metrics["stations"]:
        print(f"  - {station}")


def _live_value(
    report: dict[str, Any],
    aliases: set[str],
):
    if isinstance(report, dict):
        for key, value in report.items():
            normalized = (
                str(key)
                .lower()
                .replace(".", "")
                .replace("-", "_")
                .replace(" ", "_")
            )

            if normalized in aliases:
                return value

        for value in report.values():
            result = _live_value(
                value,
                aliases,
            )

            if result is not None:
                return result

    elif isinstance(report, list):
        for value in report:
            result = _live_value(
                value,
                aliases,
            )

            if result is not None:
                return result

    return None


def predict_latest(
    station_name: str,
    live_report: dict[str, Any] | None = None,
):
    if not MODEL_PATH.exists():
        return {
            "available": False,
            "reason": (
                "Pune all-station XGBoost model has not been trained."
            ),
        }

    raw = pd.read_csv(
        DATA_PATH,
    )

    data, features = build_features(
        raw,
        training=False,
    )

    station = station_name.strip()

    station_data = data[
        data["station_name"].str.lower() == station.lower()
    ].copy()

    if station_data.empty:
        return {
            "available": False,
            "reason": (
                f"No historical CPCB data for station '{station_name}'."
            ),
        }

    station_data = station_data.sort_values(
        "timestamp"
    )

    # We need enough history for lag features.
    if len(station_data) < 25:
        return {
            "available": False,
            "reason": (
                f"Insufficient historical rows for '{station_name}'."
            ),
        }

    row = station_data.iloc[-1].copy()

    # Overlay current WeatherAPI values when available.
    if live_report:
        replacements = {
            "pm25": {"pm25", "pm2_5", "pm25_current"},
            "pm10": {"pm10", "pm10_current"},
            "no2": {"no2"},
            "so2": {"so2"},
            "co": {"co"},
            "o3": {"o3"},
            "temperature": {"temperature", "temp_c", "temp"},
            "humidity": {"humidity"},
            "pressure": {"pressure", "pressure_mb", "pressure_hpa"},
            "wind_speed": {"wind_speed", "wind_kph", "wind_mps"},
            "rainfall": {"rainfall", "precip_mm", "precipitation"},
        }

        for feature, aliases in replacements.items():
            value = _live_value(
                live_report,
                aliases,
            )

            if value is not None:
                try:
                    row[feature] = float(value)
                except (TypeError, ValueError):
                    pass

    medians = joblib.load(
        MEDIANS_PATH,
    )

    model = joblib.load(
        MODEL_PATH,
    )

    feature_names = joblib.load(
        FEATURES_PATH,
    )

    X = pd.DataFrame(
        [
            {
                feature: row.get(
                    feature,
                    np.nan,
                )
                for feature in feature_names
            }
        ]
    )

    X = X.fillna(
        pd.Series(medians)
    ).fillna(0)

    prediction = float(
        model.predict(X)[0]
    )

    return {
        "available": True,
        "source": "Pune All-Station XGBoost",
        "station": station_name,
        "predicted_pm25_next_1h": round(
            max(0.0, prediction),
            3,
        ),
        "model_scope": "Pune CPCB multi-station",
        "note": (
            "For a locality mapped to a representative station, "
            "this is a representative-station forecast, not a direct "
            "measurement at the locality."
        ),
    }


if __name__ == "__main__":
    train()
