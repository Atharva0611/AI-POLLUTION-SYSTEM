from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd


def load_model(model_path: str):
    """
    Load an XGBoost/sklearn model from .joblib/.pkl.
    """
    import joblib

    model = joblib.load(model_path)

    if model is None:
        raise ValueError("Model loaded as None.")

    return model


def prepare_feature_row(
    feature_row: Any,
    feature_names: list[str] | None = None,
):
    """
    Convert the prediction input into a one-row DataFrame.
    """

    if isinstance(feature_row, pd.DataFrame):
        if len(feature_row) == 0:
            raise ValueError("Feature DataFrame is empty.")

        return feature_row.iloc[[0]].copy()

    if isinstance(feature_row, pd.Series):
        return pd.DataFrame([feature_row.to_dict()])

    if isinstance(feature_row, dict):
        return pd.DataFrame([feature_row])

    array = np.asarray(feature_row)

    if array.ndim == 1:
        array = array.reshape(1, -1)

    if feature_names is None:
        feature_names = [
            f"feature_{i}"
            for i in range(array.shape[1])
        ]

    return pd.DataFrame(
        array,
        columns=feature_names,
    )


def calculate_shap(
    model,
    feature_row: Any,
    feature_names: list[str] | None = None,
):
    """
    Calculate SHAP values for one XGBoost prediction.

    IMPORTANT:
    feature_row must contain the same features and ordering
    that were used for model.predict().
    """

    import shap

    X = prepare_feature_row(
        feature_row,
        feature_names,
    )

    # TreeExplainer is appropriate for XGBoost tree models.
    explainer = shap.TreeExplainer(model)

    shap_values = explainer.shap_values(X)

    # Regression normally returns [n_samples, n_features].
    values = np.asarray(shap_values)

    if values.ndim == 2:
        values = values[0]

    if values.ndim != 1:
        raise ValueError(
            f"Unexpected SHAP output shape: {values.shape}"
        )

    names = list(X.columns)

    if len(names) != len(values):
        raise ValueError(
            f"Feature count mismatch: "
            f"{len(names)} names vs {len(values)} SHAP values."
        )

    results = []

    for name, value, feature_value in zip(
        names,
        values,
        X.iloc[0].values,
    ):
        value = float(value)

        try:
            feature_value = float(feature_value)
        except Exception:
            feature_value = str(feature_value)

        if value > 0:
            effect = "increases PM2.5 prediction"
        elif value < 0:
            effect = "decreases PM2.5 prediction"
        else:
            effect = "no effect"

        results.append({
            "feature": str(name),
            "feature_value": feature_value,
            "shap_value": float(value),
            "display_shap_value": round(value, 6),
            "absolute_impact": abs(float(value)),
            "effect": effect,
        })

    results.sort(
        key=lambda x: x["absolute_impact"],
        reverse=True,
    )

    try:
        prediction = float(
            np.asarray(model.predict(X)).reshape(-1)[0]
        )
    except Exception:
        prediction = None

    try:
        expected_value = explainer.expected_value

        if isinstance(expected_value, np.ndarray):
            expected_value = expected_value.reshape(-1)[0]

        expected_value = float(expected_value)

    except Exception:
        expected_value = None

    return {
        "available": True,
        "status": "SUCCESS",
        "method": "SHAP TreeExplainer",
        "prediction": prediction,
        "expected_value": expected_value,
        "feature_count": len(results),
        "features": results,
    }


def get_top_shap_features(
    shap_result: dict,
    top_n: int = 10,
):
    """
    Return the most influential features.
    """

    if not shap_result:
        return []

    features = shap_result.get("features", [])

    if not isinstance(features, list):
        return []

    return features[:top_n]


def format_shap_report(
    shap_result: dict,
    top_n: int = 10,
):
    """
    Generate a clean text SHAP report.
    """

    if not shap_result:
        return "SHAP: No result."

    if not shap_result.get("available"):
        return (
            f"SHAP unavailable: "
            f"{shap_result.get('message', 'Unknown error')}"
        )

    lines = []

    lines.append("SHAP ANALYSIS")
    lines.append("=" * 60)

    prediction = shap_result.get("prediction")

    if prediction is not None:
        lines.append(
            f"XGBoost PM2.5 prediction: "
            f"{prediction:.2f} µg/m³"
        )

    expected = shap_result.get("expected_value")

    if expected is not None:
        lines.append(
            f"Model baseline: "
            f"{expected:.2f}"
        )

    lines.append("")
    lines.append("TOP FEATURES")
    lines.append("-" * 60)

    for item in get_top_shap_features(
        shap_result,
        top_n,
    ):
        lines.append(
            f"{item['feature']}: "
            f"SHAP={item['shap_value']:+.4f} | "
            f"value={item['feature_value']} | "
            f"{item['effect']}"
        )

    return "\n".join(lines)


def explain_xgboost_prediction(
    model,
    X,
):
    """
    One-call helper for the existing XGBoost predictor.
    """

    if isinstance(X, pd.DataFrame):
        feature_names = list(X.columns)
    else:
        feature_names = None

    result = calculate_shap(
        model=model,
        feature_row=X,
        feature_names=feature_names,
    )

    result["report"] = format_shap_report(
        result,
        top_n=10,
    )

    return result
