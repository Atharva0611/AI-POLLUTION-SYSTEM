import os
import joblib
import numpy as np
import pandas as pd
import shap


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

PROJECT_ROOT = os.path.abspath(
    os.path.join(CURRENT_DIR, "..", "..")
)

MODEL_PATH = os.path.join(
    PROJECT_ROOT,
    "models",
    "forecasting",
    "xgboost_pm25_forecasting.pkl"
)

FEATURE_PATH = os.path.join(
    PROJECT_ROOT,
    "models",
    "forecasting",
    "feature_names.pkl"
)


def load_model():

    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"Model not found:\n{MODEL_PATH}"
        )

    return joblib.load(MODEL_PATH)


def load_features():

    if not os.path.exists(FEATURE_PATH):
        raise FileNotFoundError(
            f"Feature names not found:\n{FEATURE_PATH}"
        )

    return joblib.load(FEATURE_PATH)


def prepare_features(data):

    if not isinstance(data, pd.DataFrame):
        data = pd.DataFrame(data)

    X = data.copy()

    for col in ["timestamp", "target_pm25_next_1h"]:
        if col in X.columns:
            X = X.drop(columns=[col])

    if "station_name" in X.columns:

        X = pd.get_dummies(
            X,
            columns=["station_name"],
            dtype=int
        )

    X = X.apply(
        pd.to_numeric,
        errors="coerce"
    )

    X = X.replace(
        [np.inf, -np.inf],
        np.nan
    )

    feature_names = load_features()

    X = X.reindex(
        columns=feature_names
    )

    # For SHAP, use median values for missing features
    X = X.fillna(
        X.median(numeric_only=True)
    )

    return X


def explain_prediction(data):

    model = load_model()

    X = prepare_features(data)

    explainer = shap.TreeExplainer(
        model
    )

    shap_values = explainer(
        X
    )

    values = shap_values.values[0]

    explanation = pd.DataFrame({
        "feature": X.columns,
        "shap_value": values,
        "abs_shap": np.abs(values),
        "feature_value": X.iloc[0].values
    })

    explanation = explanation.sort_values(
        "abs_shap",
        ascending=False
    ).reset_index(drop=True)

    return explanation


def top_features(data, n=10):

    explanation = explain_prediction(data)

    return explanation.head(n)


def global_feature_importance(
    data,
    n=20
):

    model = load_model()

    X = prepare_features(data)

    explainer = shap.TreeExplainer(
        model
    )

    shap_values = explainer(
        X
    )

    importance = pd.DataFrame({
        "feature": X.columns,
        "mean_abs_shap": np.abs(
            shap_values.values
        ).mean(axis=0)
    })

    importance = importance.sort_values(
        "mean_abs_shap",
        ascending=False
    )

    return importance.head(n).reset_index(
        drop=True
    )


if __name__ == "__main__":

    print(
        "SHAP explainer loaded successfully."
    )