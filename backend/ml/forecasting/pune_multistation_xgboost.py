from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor


ROOT = Path(__file__).resolve().parents[3]

DATA_PATH = ROOT / "data" / "processed" / "pune_cpcb_all_stations_hourly.csv"
MODEL_PATH = ROOT / "models" / "forecasting" / "pune_multistation_xgboost.pkl"
FEATURES_PATH = ROOT / "models" / "forecasting" / "pune_multistation_features.pkl"
MEDIANS_PATH = ROOT / "models" / "forecasting" / "pune_multistation_medians.pkl"
STATIONS_PATH = ROOT / "models" / "forecasting" / "pune_multistation_stations.pkl"
METRICS_PATH = ROOT / "models" / "forecasting" / "pune_multistation_metrics.json"


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
        "site",
    ],
    "pm25": [
        "pm25",
        "pm2_5",
        "pm2.5",
        "PM2.5",
        "PM2.5 (µg/m³)",
    ],
    "pm10": [
        "pm10",
        "PM10",
        "PM10 (µg/m³)",
    ],
    "no2": [
        "no2",
        "NO2",
        "NO2 (µg/m³)",
    ],
    "so2": [
        "so2",
        "SO2",
        "SO2 (µg/m³)",
    ],
    "co": [
        "co",
        "CO",
        "CO (mg/m³)",
        "CO (µg/m³)",
    ],
    "o3": [
        "o3",
        "O3",
        "O3 (µg/m³)",
    ],
    "nh3": [
        "nh3",
        "NH3",
        "NH3 (µg/m³)",
    ],
    "temperature": [
        "temperature",
        "temp",
        "AT",
        "AT (°C)",
        "temperature_c",
    ],
    "humidity": [
        "humidity",
        "RH",
        "RH (%)",
        "relative_humidity",
    ],
    "pressure": [
        "pressure",
        "BP",
        "BP (mmHg)",
        "pressure_mb",
        "pressure_hpa",
    ],
    "wind_speed": [
        "wind_speed",
        "WS",
        "WS (m/s)",
        "wind_kph",
        "wind_mps",
    ],
    "rainfall": [
        "rainfall",
        "RF",
        "RF (mm)",
        "precip_mm",
    ],
}


def norm(value: Any) -> str:
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
    lookup = {norm(c): c for c in df.columns}

    for alias in aliases:
        key = norm(alias)

        if key in lookup:
            return lookup[key]

    for column in df.columns:
        c = norm(column)

        for alias in aliases:
            a = norm(alias)

            if a in c or c in a:
                return column

    return None


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    result = pd.DataFrame(index=df.index)

    for target, aliases in ALIASES.items():
        column = find_column(df, aliases)

        if column is None:
            result[target] = np.nan
        else:
            result[target] = df[column]

    result["timestamp"] = pd.to_datetime(
        result["timestamp"],
        errors="coerce",
    )

    result["station_name"] = (
        result["station_name"]
        .astype(str)
        .str.strip()
    )

    for column in result.columns:
        if column not in {"timestamp", "station_name"}:
            result[column] = pd.to_numeric(
                result[column],
                errors="coerce",
            )

    result = result.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    return result


def make_features(
    raw: pd.DataFrame,
    training: bool = True,
):
    df = normalize(raw)

    df = df.dropna(
        subset=[
            "timestamp",
            "station_name",
            "pm25",
        ]
    )

    df = df[
        df["station_name"].astype(str).str.lower()
        .ne("nan")
    ]

    df = df.sort_values(
        ["station_name", "timestamp"]
    ).reset_index(drop=True)

    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["month"] = df["timestamp"].dt.month
    df["day_of_year"] = df["timestamp"].dt.dayofyear

    base = [
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
        "o3",
        "temperature",
        "humidity",
        "wind_speed",
        "rainfall",
    ]

    lags = [1, 3, 6, 12, 24]

    grouped = df.groupby(
        "station_name",
        group_keys=False,
    )

    features = list(base)

    for column in lag_columns:
        for lag in lags:
            name = f"{column}_lag_{lag}"

            df[name] = grouped[column].shift(lag)

            features.append(name)

    df["target_pm25_next_1h"] = (
        grouped["pm25"].shift(-1)
    )

    df = df.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    if training:
        df = df.dropna(
            subset=[
                "target_pm25_next_1h",
                "pm25_lag_1",
            ]
        )

    # Keep only useful features; completely empty features are removed.
    usable = []

    for feature in features:
        if feature not in df:
            continue

        non_null = df[feature].notna().sum()

        if non_null > 0:
            usable.append(feature)

    features = usable

    # One-hot station encoding.
    stations = sorted(
        df["station_name"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
        .tolist()
    )

    station_dummies = pd.get_dummies(
        df["station_name"],
        prefix="station",
        dtype=float,
    )

    df = pd.concat(
        [
            df.reset_index(drop=True),
            station_dummies.reset_index(drop=True),
        ],
        axis=1,
    )

    station_features = station_dummies.columns.tolist()

    features += station_features

    return df, features, stations


def train():
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found:\n{DATA_PATH}"
        )

    print("Loading:")
    print(DATA_PATH)

    raw = pd.read_csv(
        DATA_PATH,
        low_memory=False,
    )

    print(f"Raw rows: {len(raw):,}")

    data, features, stations = make_features(
        raw,
        training=True,
    )

    print(f"Usable rows: {len(data):,}")
    print(f"Station count: {len(stations)}")
    print()

    print("Stations used for training:")

    for station in stations:
        print(f"  - {station}")

    if len(stations) < 6:
        raise RuntimeError(
            f"Only {len(stations)} stations were found in "
            f"{DATA_PATH.name}.\n"
            "The old five-station feature file must NOT be used.\n"
            "This model requires the full cleaned hourly dataset "
            "to contain the available Pune stations."
        )

    data["timestamp"] = pd.to_datetime(
        data["timestamp"]
    )

    times = (
        data["timestamp"]
        .drop_duplicates()
        .sort_values()
        .reset_index(drop=True)
    )

    train_cut = times.iloc[
        int(len(times) * 0.70)
    ]

    validation_cut = times.iloc[
        int(len(times) * 0.85)
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

    X_validation = (
        validation_df[features]
        .fillna(medians)
    )
    y_validation = (
        validation_df["target_pm25_next_1h"]
    )

    X_test = (
        test_df[features]
        .fillna(medians)
    )
    y_test = (
        test_df["target_pm25_next_1h"]
    )

    model = XGBRegressor(
        n_estimators=800,
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

    prediction = model.predict(
        X_test
    )

    rmse = float(
        np.sqrt(
            mean_squared_error(
                y_test,
                prediction,
            )
        )
    )

    metrics = {
        "model": "Pune Multi-Station XGBoost",
        "station_count": len(stations),
        "stations": stations,
        "rows": len(data),
        "train_rows": len(train_df),
        "validation_rows": len(validation_df),
        "test_rows": len(test_df),
        "MAE": float(
            mean_absolute_error(
                y_test,
                prediction,
            )
        ),
        "RMSE": rmse,
        "R2": float(
            r2_score(
                y_test,
                prediction,
            )
        ),
        "target": "CPCB PM2.5 next hour",
        "data_source": str(DATA_PATH),
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

    joblib.dump(
        stations,
        STATIONS_PATH,
    )

    METRICS_PATH.write_text(
        pd.Series(metrics).to_json(
            indent=2
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 70)
    print("PUNE MULTI-STATION XGBOOST TRAINING COMPLETE")
    print("=" * 70)
    print(f"Stations : {len(stations)}")
    print(f"Rows     : {len(data):,}")
    print(f"MAE      : {metrics['MAE']:.4f}")
    print(f"RMSE     : {metrics['RMSE']:.4f}")
    print(f"R2       : {metrics['R2']:.4f}")
    print("=" * 70)


def recursive_value(
    report: Any,
    aliases: set[str],
):
    if isinstance(report, dict):
        for key, value in report.items():
            k = norm(key)

            if k in aliases:
                return value

        for value in report.values():
            result = recursive_value(
                value,
                aliases,
            )

            if result is not None:
                return result

    elif isinstance(report, list):
        for value in report:
            result = recursive_value(
                value,
                aliases,
            )

            if result is not None:
                return result

    return None


def predict_station(
    station_name: str,
    live_report: dict | None = None,
):
    if not MODEL_PATH.exists():
        return {
            "available": False,
            "reason": (
                "Pune Multi-Station XGBoost has not been trained."
            ),
        }

    stations = joblib.load(
        STATIONS_PATH,
    )

    station_match = next(
        (
            s for s in stations
            if str(s).lower()
            == station_name.strip().lower()
        ),
        None,
    )

    if station_match is None:
        return {
            "available": False,
            "reason": (
                f"Station '{station_name}' is not present "
                "in the Pune multi-station training data."
            ),
        }

    raw = pd.read_csv(
        DATA_PATH,
        low_memory=False,
    )

    data, features, _ = make_features(
        raw,
        training=False,
    )

    station_data = data[
        data["station_name"].astype(str).str.lower()
        == station_match.lower()
    ].copy()

    if len(station_data) < 25:
        return {
            "available": False,
            "reason": (
                f"Not enough historical rows for "
                f"station '{station_match}'."
            ),
        }

    station_data = station_data.sort_values(
        "timestamp"
    ).reset_index(drop=True)

    row = station_data.iloc[-1].copy()

    # Current weather from WeatherAPI can update meteorological inputs.
    # Pollution lag values remain CPCB-based to avoid directly replacing
    # the CPCB training distribution with provider air-quality values.
    if live_report:

        replacements = {
            "temperature": {
                "temperature",
                "temp_c",
                "temp",
            },
            "humidity": {
                "humidity",
            },
            "pressure": {
                "pressure",
                "pressure_mb",
                "pressure_hpa",
            },
            "wind_speed": {
                "wind_speed",
                "wind_kph",
                "wind_mph",
                "wind_mps",
            },
            "rainfall": {
                "rainfall",
                "precip_mm",
                "precipitation",
            },
        }

        for feature, aliases in replacements.items():

            value = recursive_value(
                live_report,
                aliases,
            )

            if value is not None:

                try:
                    row[feature] = float(
                        value
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    pass

    medians = joblib.load(
        MEDIANS_PATH,
    )

    model = joblib.load(
        MODEL_PATH,
    )

    # Current station one-hot value.
    for feature in features:

        if feature.startswith(
            "station_"
        ):
            row[feature] = (
                1.0
                if feature
                == f"station_{station_match}"
                else 0.0
            )

    X = pd.DataFrame(
        [
            {
                feature: row.get(
                    feature,
                    np.nan,
                )
                for feature in features
            }
        ]
    )

    X = X.fillna(
        pd.Series(medians)
    ).fillna(0)

    prediction = float(
        model.predict(X)[0]
    )

    # XGBoost per-row contributions.
    contributions = []

    try:
        import xgboost as xgb

        booster = model.get_booster()

        dmatrix = xgb.DMatrix(
            X,
        )

        contrib = booster.predict(
            dmatrix,
            pred_contribs=True,
        )[0]

        pairs = []

        for feature, contribution in zip(
            features,
            contrib[:-1],
        ):
            if feature.startswith("station_"):
                continue

            pairs.append(
                (
                    feature,
                    float(contribution),
                )
            )

        pairs.sort(
            key=lambda item: abs(item[1]),
            reverse=True,
        )

        friendly = {
            "pm25": "Current PM2.5",
            "pm10": "Current PM10",
            "no2": "Current NO2",
            "so2": "Current SO2",
            "co": "Current CO",
            "o3": "Current O3",
            "temperature": "Temperature",
            "humidity": "Humidity",
            "pressure": "Pressure",
            "wind_speed": "Wind speed",
            "rainfall": "Rainfall",
        }

        for feature, contribution in pairs[:8]:

            base = feature

            if "_lag_" in feature:

                col, lag = feature.rsplit(
                    "_lag_",
                    1,
                )

                label = (
                    f"{friendly.get(col, col)} "
                    f"{lag}h lag"
                )

            else:

                label = friendly.get(
                    feature,
                    feature,
                )

            contributions.append(
                {
                    "feature": label,
                    "raw_feature": feature,
                    "contribution": round(
                        contribution,
                        4,
                    ),
                    "direction": (
                        "increases prediction"
                        if contribution > 0
                        else "reduces prediction"
                    ),
                }
            )

    except Exception as exc:

        contributions = [
            {
                "feature": "Model contributions unavailable",
                "contribution": None,
                "direction": "unknown",
                "reason": str(exc),
            }
        ]

    return {
        "available": True,
        "source": "Pune Multi-Station XGBoost",
        "station": station_match,
        "predicted_pm25_next_1h": round(
            max(
                0.0,
                prediction,
            ),
            3,
        ),
        "trained_station_count": len(
            stations
        ),
        "trained_stations": stations,
        "model_scope": (
            "All available Pune CPCB stations "
            "in cleaned hourly dataset"
        ),
        "top_model_factors": contributions,
        "note": (
            "For a locality mapped to a representative CPCB "
            "station, this is a representative-station forecast."
        ),
    }


if __name__ == "__main__":
    train()
