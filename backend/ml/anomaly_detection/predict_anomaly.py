import os
import joblib
import pandas as pd


PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)

MODEL_PATH = os.path.join(
    PROJECT_ROOT,
    "models",
    "anomaly_detection",
    "isolation_forest.pkl"
)


_model = None


def load_model():
    global _model

    if _model is None:

        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"Isolation Forest model not found:\n{MODEL_PATH}"
            )

        _model = joblib.load(MODEL_PATH)

    return _model


def detect_single(input_data):

    model = load_model()

    if isinstance(input_data, dict):
        df = pd.DataFrame([input_data])

    elif isinstance(input_data, pd.DataFrame):
        df = input_data.copy()

    else:
        raise TypeError(
            "input_data must be a dictionary or pandas DataFrame."
        )

    # Keep only numeric model inputs
    X = df.select_dtypes(include=["number"])

    if X.empty:
        raise ValueError(
            "No numeric features were provided for anomaly detection."
        )

    prediction = model.predict(X)[0]

    score = model.decision_function(X)[0]

    return {
        "anomaly_detected": prediction == -1,
        "anomaly_score": float(score),
    }