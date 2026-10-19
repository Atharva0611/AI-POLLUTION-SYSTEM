import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from xgboost import XGBRegressor

from backend.services.shap_service import (
    explain_xgboost_prediction,
    format_shap_report,
)


def main():

    X = pd.DataFrame({
        "pm10": [80, 100, 120, 140, 160, 180, 200, 220],
        "temperature": [20, 22, 24, 26, 28, 30, 32, 34],
        "humidity": [40, 45, 50, 55, 60, 65, 70, 75],
        "wind_speed": [15, 14, 12, 10, 8, 6, 5, 3],
        "no2": [20, 25, 30, 40, 50, 60, 70, 80],
    })

    y = pd.Series(
        [30, 34, 40, 48, 56, 66, 80, 96],
        name="pm25",
    )

    model = XGBRegressor(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.05,
        random_state=42,
        objective="reg:squarederror",
    )

    model.fit(X, y)

    X_test = X.iloc[[7]]

    result = explain_xgboost_prediction(
        model,
        X_test,
    )

    print("")
    print(result["report"])
    print("")

    if result["available"]:
        print("SHAP TEST: PASSED")
    else:
        print("SHAP TEST: FAILED")


if __name__ == "__main__":
    main()
