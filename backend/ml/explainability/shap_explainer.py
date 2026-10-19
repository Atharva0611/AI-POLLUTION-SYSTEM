from pathlib import Path
import pickle
import numpy as np
import pandas as pd
import shap

ROOT = Path(r"C:\final year project\AI-POLLUTION-SYSTEM")

MODEL_FILE = ROOT / "models" / "forecasting" / "xgboost_pm25_forecasting.pkl"
FEATURE_FILE = ROOT / "models" / "forecasting" / "feature_names.pkl"
DATA_FILE = ROOT / "data" / "processed" / "pune_cpcb_features.csv"

OUTPUT_DIR = ROOT / "data" / "processed" / "shap"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def normalize(text):
    return (
        str(text)
        .strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
    )


def load_model():
    with open(MODEL_FILE, "rb") as f:
        return pickle.load(f)


def load_feature_names():
    with open(FEATURE_FILE, "rb") as f:
        names = pickle.load(f)

    if hasattr(names, "tolist"):
        names = names.tolist()

    return [str(x) for x in names]


def load_data():
    return pd.read_csv(DATA_FILE)


def find_station(df, station):
    if "station_name" not in df.columns:
        raise ValueError(
            "station_name column not found in feature dataset."
        )

    target = normalize(station)

    df["_station_key"] = (
        df["station_name"]
        .astype(str)
        .map(normalize)
    )

    rows = df[
        df["_station_key"] == target
    ].copy()

    if rows.empty:
        available = sorted(
            df["station_name"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        raise ValueError(
            f"Station '{station}' not found. "
            f"Available stations: {available}"
        )

    return rows.iloc[-1]


def prepare_row(df, row, feature_names):
    X = pd.DataFrame(index=[0])

    for feature in feature_names:
        if feature in df.columns:
            X.loc[0, feature] = row[feature]
        else:
            X.loc[0, feature] = np.nan

    # Convert everything to numeric
    for col in feature_names:
        X[col] = pd.to_numeric(
            X[col],
            errors="coerce"
        )

    # Use dataset medians for missing values
    for col in feature_names:

        if X[col].isna().any():

            if col in df.columns:
                median = pd.to_numeric(
                    df[col],
                    errors="coerce"
                ).median()
            else:
                median = 0.0

            if pd.isna(median):
                median = 0.0

            X[col] = X[col].fillna(median)

    X = X.replace(
        [np.inf, -np.inf],
        np.nan
    ).fillna(0)

    return X.astype(float)


def explain_prediction(station):

    model = load_model()
    feature_names = load_feature_names()
    df = load_data()

    row = find_station(
        df,
        station
    )

    X = prepare_row(
        df,
        row,
        feature_names
    )

    prediction = float(
        model.predict(X)[0]
    )

    explainer = shap.TreeExplainer(
        model
    )

    shap_values = explainer.shap_values(
        X
    )

    values = np.asarray(
        shap_values
    ).reshape(-1)

    base_value = explainer.expected_value

    if isinstance(base_value, np.ndarray):
        base_value = float(
            base_value.reshape(-1)[0]
        )
    else:
        base_value = float(base_value)

    result = pd.DataFrame({
        "feature": feature_names,
        "feature_value": X.iloc[0].values,
        "shap_value": values,
        "absolute_impact": np.abs(values),
    })

    result["direction"] = np.where(
        result["shap_value"] >= 0,
        "increases_pm25",
        "decreases_pm25"
    )

    result = result.sort_values(
        "absolute_impact",
        ascending=False
    )

    output_file = (
        OUTPUT_DIR
        / f"{normalize(station).replace(' ', '_')}_shap.csv"
    )

    result.to_csv(
        output_file,
        index=False
    )

    top_positive = (
        result[
            result["shap_value"] > 0
        ]
        .head(5)
        .to_dict("records")
    )

    top_negative = (
        result[
            result["shap_value"] < 0
        ]
        .sort_values(
            "shap_value",
            ascending=True
        )
        .head(5)
        .to_dict("records")
    )

    return {
        "station": station,
        "prediction_pm25": prediction,
        "base_value": base_value,
        "top_features": result.head(10).to_dict(
            "records"
        ),
        "top_positive": top_positive,
        "top_negative": top_negative,
        "output_file": str(output_file),
    }


if __name__ == "__main__":

    station = input(
        "Station: "
    ).strip()

    try:

        result = explain_prediction(
            station
        )

        print("\nSHAP EXPLAINABILITY")
        print("=" * 70)

        print(
            "Station:",
            result["station"]
        )

        print(
            "Predicted PM2.5:",
            result["prediction_pm25"]
        )

        print(
            "Base value:",
            result["base_value"]
        )

        print("\nTOP FEATURES")

        for item in result["top_features"]:

            print(
                f"{item['feature']} | "
                f"value={item['feature_value']} | "
                f"SHAP={item['shap_value']:.4f} | "
                f"{item['direction']}"
            )

        print(
            "\nSaved:",
            result["output_file"]
        )

    except Exception as exc:

        print(
            f"ERROR: {type(exc).__name__}: {exc}"
        )
