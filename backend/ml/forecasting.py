import os
from typing import Union, Dict, Any

import joblib
import pandas as pd


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".."
    )
)

MODEL_PATH = os.path.join(
    PROJECT_ROOT,
    "models",
    "forecasting",
    "xgboost_pm25_forecasting.pkl"
)

FEATURE_NAMES_PATH = os.path.join(
    PROJECT_ROOT,
    "models",
    "forecasting",
    "feature_names.pkl"
)

FEATURE_DATA_PATH = os.path.join(
    PROJECT_ROOT,
    "data",
    "processed",
    "pune_cpcb_features.csv"
)


# ============================================================
# CACHE
# ============================================================

_model = None
_feature_names = None
_feature_data = None


# ============================================================
# LOAD MODEL
# ============================================================

def load_model():

    global _model

    if _model is None:

        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"XGBoost model not found:\n{MODEL_PATH}"
            )

        _model = joblib.load(MODEL_PATH)

    return _model


# ============================================================
# LOAD FEATURE NAMES
# ============================================================

def load_feature_names():

    global _feature_names

    if _feature_names is None:

        if not os.path.exists(FEATURE_NAMES_PATH):
            raise FileNotFoundError(
                f"Feature names file not found:\n"
                f"{FEATURE_NAMES_PATH}"
            )

        _feature_names = joblib.load(
            FEATURE_NAMES_PATH
        )

    return list(_feature_names)


# ============================================================
# LOAD DATA
# ============================================================

def load_feature_data():

    global _feature_data

    if _feature_data is None:

        if not os.path.exists(FEATURE_DATA_PATH):
            raise FileNotFoundError(
                f"Feature dataset not found:\n"
                f"{FEATURE_DATA_PATH}"
            )

        _feature_data = pd.read_csv(
            FEATURE_DATA_PATH
        )

    return _feature_data


# ============================================================
# GET LATEST STATION RECORD
# ============================================================

def get_latest_record(
    station_name: str = None
) -> pd.DataFrame:

    df = load_feature_data().copy()

    df.columns = [
        str(col).strip()
        for col in df.columns
    ]

    # --------------------------------------------------------
    # Find station column
    # --------------------------------------------------------

    station_columns = [
        col
        for col in df.columns
        if col.lower() in {
            "station_name",
            "station",
            "location",
            "location_name"
        }
    ]

    station_col = (
        station_columns[0]
        if station_columns
        else None
    )

    # --------------------------------------------------------
    # Filter requested station
    # --------------------------------------------------------

    if station_name and station_col:

        matched = df[
            df[station_col]
            .astype(str)
            .str.strip()
            .str.lower()
            == station_name.strip().lower()
        ]

        if matched.empty:

            raise ValueError(
                f"Station '{station_name}' "
                f"was not found in the dataset."
            )

        df = matched

    # --------------------------------------------------------
    # Sort by timestamp
    # --------------------------------------------------------

    timestamp_columns = [
        col
        for col in df.columns
        if col.lower() in {
            "timestamp",
            "datetime",
            "date",
            "time"
        }
    ]

    if timestamp_columns:

        timestamp_col = timestamp_columns[0]

        df[timestamp_col] = pd.to_datetime(
            df[timestamp_col],
            errors="coerce"
        )

        df = df.sort_values(
            timestamp_col
        )

    if df.empty:
        raise ValueError(
            "No records available."
        )

    # Keep latest row
    latest = df.tail(1).copy()

    # --------------------------------------------------------
    # Save actual station name for one-hot encoding
    # --------------------------------------------------------

    if station_name:
        latest["_prediction_station"] = station_name

    elif station_col:
        latest["_prediction_station"] = (
            latest[station_col]
            .astype(str)
            .iloc[0]
        )

    else:
        latest["_prediction_station"] = None

    return latest


# ============================================================
# CREATE STATION ONE-HOT FEATURES
# ============================================================

def add_station_features(
    df: pd.DataFrame,
    station_name: str = None
) -> pd.DataFrame:

    df = df.copy()

    feature_names = load_feature_names()

    # --------------------------------------------------------
    # Identify station dummy columns expected by model
    # --------------------------------------------------------

    station_dummy_columns = [
        feature
        for feature in feature_names
        if feature.startswith(
            "station_name_"
        )
    ]

    # --------------------------------------------------------
    # If no station dummy variables exist,
    # nothing needs to be done.
    # --------------------------------------------------------

    if not station_dummy_columns:
        return df

    # --------------------------------------------------------
    # Determine station
    # --------------------------------------------------------

    current_station = station_name

    if not current_station:

        if "_prediction_station" in df.columns:

            current_station = str(
                df["_prediction_station"].iloc[0]
            )

        elif "station_name" in df.columns:

            current_station = str(
                df["station_name"].iloc[0]
            )

    # --------------------------------------------------------
    # Create ALL expected dummy columns
    # --------------------------------------------------------

    for column in station_dummy_columns:

        if column not in df.columns:

            df[column] = 0

    # --------------------------------------------------------
    # Set selected station = 1
    # --------------------------------------------------------

    if current_station:

        target_column = (
            f"station_name_{current_station}"
        )

        if target_column in station_dummy_columns:

            df[target_column] = 1

        else:

            # ------------------------------------------------
            # Station does not belong to the trained
            # one-hot categories.
            # ------------------------------------------------

            raise ValueError(
                f"Station '{current_station}' does not "
                f"exist in the XGBoost training categories.\n"
                f"Expected one of:\n"
                + "\n".join(
                    f" - {col.replace('station_name_', '')}"
                    for col in station_dummy_columns
                )
            )

    return df


# ============================================================
# PREPARE MODEL FEATURES
# ============================================================

def prepare_features(
    input_data: Union[
        Dict[str, Any],
        pd.DataFrame
    ],
    station_name: str = None
) -> pd.DataFrame:

    feature_names = load_feature_names()

    # --------------------------------------------------------
    # Convert input to DataFrame
    # --------------------------------------------------------

    if isinstance(input_data, dict):

        df = pd.DataFrame(
            [input_data]
        )

    elif isinstance(input_data, pd.DataFrame):

        df = input_data.copy()

    else:

        raise TypeError(
            "input_data must be a dictionary "
            "or pandas DataFrame."
        )

    # --------------------------------------------------------
    # Normalize column names
    # --------------------------------------------------------

    df.columns = [
        str(col).strip()
        for col in df.columns
    ]

    # --------------------------------------------------------
    # ADD STATION DUMMY VARIABLES
    # --------------------------------------------------------

    df = add_station_features(
        df,
        station_name=station_name
    )

    # --------------------------------------------------------
    # Remove internal helper column
    # --------------------------------------------------------

    if "_prediction_station" in df.columns:
        df = df.drop(
            columns=["_prediction_station"]
        )

    # --------------------------------------------------------
    # Check required features
    # --------------------------------------------------------

    missing = [
        feature
        for feature in feature_names
        if feature not in df.columns
    ]

    if missing:

        raise ValueError(
            "Required XGBoost features are missing:\n"
            + "\n".join(
                f" - {feature}"
                for feature in missing
            )
        )

    # --------------------------------------------------------
    # Exact training feature order
    # --------------------------------------------------------

    X = df[
        feature_names
    ].copy()

    # --------------------------------------------------------
    # Convert all features to numeric
    # --------------------------------------------------------

    for column in X.columns:

        X[column] = pd.to_numeric(
            X[column],
            errors="coerce"
        )

    # --------------------------------------------------------
    # Missing numeric values
    # --------------------------------------------------------

    if X.isnull().any().any():

        missing_columns = X.columns[
            X.isnull().any()
        ].tolist()

        raise ValueError(
            "Missing/non-numeric values found in "
            "forecast features:\n"
            + "\n".join(
                f" - {column}"
                for column in missing_columns
            )
        )

    return X


# ============================================================
# PREDICT SINGLE RECORD
# ============================================================

def predict_single(
    input_data=None,
    station_name: str = None
) -> float:

    model = load_model()

    # --------------------------------------------------------
    # Automatically get latest row
    # --------------------------------------------------------

    if input_data is None:

        input_data = get_latest_record(
            station_name=station_name
        )

    # --------------------------------------------------------
    # Prepare
    # --------------------------------------------------------

    X = prepare_features(
        input_data,
        station_name=station_name
    )

    # --------------------------------------------------------
    # Predict
    # --------------------------------------------------------

    prediction = model.predict(
        X
    )

    if len(prediction) == 0:

        raise RuntimeError(
            "XGBoost returned no prediction."
        )

    return float(
        prediction[0]
    )


# ============================================================
# FORECAST RESULT
# ============================================================

def get_forecast(
    station_name: str
) -> dict:

    if not station_name:
        raise ValueError(
            "station_name is required "
            "for station-specific forecasting."
        )

    latest = get_latest_record(
        station_name=station_name
    )

    prediction = predict_single(
        input_data=latest,
        station_name=station_name
    )

    return {
        "station_name": station_name,
        "predicted_pm25": prediction,
        "unit": "µg/m³",
        "forecast_horizon": "next hour",
        "model": "XGBoost",
        "success": True
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 65)
    print("XGBOOST PM2.5 FORECAST TEST")
    print("=" * 65)

    try:

        print("\nLoading model...")

        model = load_model()

        print(
            "Model:",
            type(model).__name__
        )

        print(
            "\nLoading feature names..."
        )

        features = load_feature_names()

        station_dummy_features = [
            feature
            for feature in features
            if feature.startswith(
                "station_name_"
            )
        ]

        print(
            "Total features:",
            len(features)
        )

        print(
            "Station features:"
        )

        for feature in station_dummy_features:
            print(
                " -",
                feature
            )

        print(
            "\nTesting Alandi..."
        )

        result = get_forecast(
            "Alandi"
        )

        print(
            "\nPrediction:"
        )

        print(result)

        print(
            "\nFORECAST MODULE OK"
        )

    except Exception as exc:

        print(
            "\nFORECAST ERROR:"
        )

        print(exc)