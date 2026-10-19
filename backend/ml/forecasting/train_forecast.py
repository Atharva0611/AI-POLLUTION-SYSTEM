import os
import warnings

warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import joblib

from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        ".."
    )
)


# ============================================================
# PATHS
# ============================================================

DATA_PATH = os.path.join(
    PROJECT_ROOT,
    "data",
    "processed",
    "pune_cpcb_features.csv"
)

MODEL_DIR = os.path.join(
    PROJECT_ROOT,
    "models",
    "forecasting"
)

MODEL_PATH = os.path.join(
    MODEL_DIR,
    "xgboost_pm25_forecasting.pkl"
)

FEATURE_PATH = os.path.join(
    MODEL_DIR,
    "feature_names.pkl"
)

PREDICTION_PATH = os.path.join(
    PROJECT_ROOT,
    "data",
    "processed",
    "xgboost_predictions.csv"
)


# ============================================================
# CREATE OUTPUT DIRECTORY
# ============================================================

os.makedirs(
    MODEL_DIR,
    exist_ok=True
)


# ============================================================
# 1. LOAD DATA
# ============================================================

print("=" * 70)
print("XGBOOST PM2.5 FORECAST TRAINING")
print("=" * 70)

print("\nLoading dataset...")

if not os.path.exists(DATA_PATH):
    raise FileNotFoundError(
        f"Dataset not found:\n{DATA_PATH}"
    )

df = pd.read_csv(
    DATA_PATH
)

print(
    "Dataset shape:",
    df.shape
)


# ============================================================
# 2. BASIC VALIDATION
# ============================================================

required_columns = [
    "timestamp",
    "station_name",
    "pm25"
]

missing_required = [
    col
    for col in required_columns
    if col not in df.columns
]

if missing_required:

    raise ValueError(
        "Required columns missing:\n"
        + "\n".join(
            f" - {col}"
            for col in missing_required
        )
    )


# ============================================================
# 3. TIMESTAMP
# ============================================================

df["timestamp"] = pd.to_datetime(
    df["timestamp"],
    errors="coerce"
)

df = df.dropna(
    subset=["timestamp"]
)

df = df.sort_values(
    [
        "station_name",
        "timestamp"
    ]
).reset_index(
    drop=True
)


# ============================================================
# 4. NEXT-HOUR TARGET
# ============================================================

print(
    "\nCreating next-hour PM2.5 target..."
)

df["target_pm25_next_1h"] = (
    df.groupby(
        "station_name"
    )["pm25"].shift(-1)
)

df = df.dropna(
    subset=[
        "target_pm25_next_1h"
    ]
).copy()


# ============================================================
# 5. REMOVE WIND-DIRECTION FEATURES
# ============================================================

REMOVE_FEATURES = [
    "wind_direction",
    "wind_direction_sin",
    "wind_direction_cos"
]

print(
    "\nRemoving these features:"
)

for feature in REMOVE_FEATURES:

    if feature in df.columns:

        print(
            " -",
            feature
        )

        df = df.drop(
            columns=[feature]
        )


# ============================================================
# 6. ONE-HOT ENCODE STATIONS
# ============================================================

print(
    "\nEncoding station names..."
)

df_model = pd.get_dummies(
    df,
    columns=["station_name"],
    dtype=int
)


# ============================================================
# 7. CREATE X AND y
# ============================================================

X = df_model.drop(
    columns=[
        "timestamp",
        "target_pm25_next_1h"
    ],
    errors="ignore"
)

y = df_model[
    "target_pm25_next_1h"
].copy()


# ============================================================
# 8. NUMERIC CONVERSION
# ============================================================

X = X.apply(
    pd.to_numeric,
    errors="coerce"
)

y = pd.to_numeric(
    y,
    errors="coerce"
)


# ============================================================
# 9. INFINITE VALUES
# ============================================================

X = X.replace(
    [np.inf, -np.inf],
    np.nan
)


# ============================================================
# 10. REMOVE EMPTY COLUMNS
# ============================================================

empty_columns = X.columns[
    X.isna().all()
].tolist()

if empty_columns:

    print(
        "\nRemoving completely empty columns:"
    )

    for col in empty_columns:

        print(
            " -",
            col
        )

    X = X.drop(
        columns=empty_columns
    )


# ============================================================
# 11. FINAL FEATURE CHECK
# ============================================================

wind_features_found = [
    col
    for col in X.columns
    if col in REMOVE_FEATURES
]

print(
    "\n======================================"
)

print(
    "FINAL FEATURE CHECK"
)

print(
    "======================================"
)

print(
    "Total features:",
    len(X.columns)
)

print(
    "Wind-direction features:",
    wind_features_found
)

if wind_features_found:

    raise RuntimeError(
        "Wind-direction features are still present!"
    )

print(
    "\nFeature preparation successful."
)


# ============================================================
# 12. TIME-BASED SPLIT
# ============================================================

split_time = df[
    "timestamp"
].quantile(
    0.80
)

train_mask = (
    df["timestamp"] <= split_time
)

test_mask = (
    df["timestamp"] > split_time
)

X_train = X.loc[
    train_mask
]

X_test = X.loc[
    test_mask
]

y_train = y.loc[
    train_mask
]

y_test = y.loc[
    test_mask
]


print(
    "\n======================================"
)

print(
    "TRAIN / TEST SPLIT"
)

print(
    "======================================"
)

print(
    "Training rows:",
    len(X_train)
)

print(
    "Testing rows :",
    len(X_test)
)

print(
    "Split time   :",
    split_time
)


# ============================================================
# 13. TRAIN XGBOOST
# ============================================================

print(
    "\n======================================"
)

print(
    "TRAINING XGBOOST"
)

print(
    "======================================"
)

model = XGBRegressor(

    n_estimators=1000,

    learning_rate=0.03,

    max_depth=8,

    min_child_weight=5,

    subsample=0.8,

    colsample_bytree=0.8,

    objective="reg:squarederror",

    eval_metric="rmse",

    random_state=42,

    n_jobs=-1,

    tree_method="hist"
)


model.fit(
    X_train,
    y_train,

    eval_set=[
        (
            X_train,
            y_train
        ),
        (
            X_test,
            y_test
        )
    ],

    verbose=False
)

print(
    "Training completed."
)


# ============================================================
# 14. PREDICTION
# ============================================================

y_pred = model.predict(
    X_test
)


# ============================================================
# 15. EVALUATION
# ============================================================

mae = mean_absolute_error(
    y_test,
    y_pred
)

rmse = np.sqrt(
    mean_squared_error(
        y_test,
        y_pred
    )
)

r2 = r2_score(
    y_test,
    y_pred
)


print(
    "\n======================================"
)

print(
    "MODEL PERFORMANCE"
)

print(
    "======================================"
)

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
    f"R2 % : {r2 * 100:.2f}%"
)


# ============================================================
# 16. SAVE MODEL
# ============================================================

joblib.dump(
    model,
    MODEL_PATH
)

print(
    "\nModel saved:"
)

print(
    MODEL_PATH
)


# ============================================================
# 17. SAVE FEATURE NAMES
# ============================================================

feature_names = X.columns.tolist()

joblib.dump(
    feature_names,
    FEATURE_PATH
)

print(
    "\nFeature names saved:"
)

print(
    FEATURE_PATH
)


# ============================================================
# 18. VERIFY SAVED FEATURES
# ============================================================

saved_features = joblib.load(
    FEATURE_PATH
)

remaining_wind_features = [
    feature
    for feature in saved_features
    if feature in REMOVE_FEATURES
]

print(
    "\n======================================"
)

print(
    "SAVED FEATURE VERIFICATION"
)

print(
    "======================================"
)

print(
    "Feature count:",
    len(saved_features)
)

print(
    "Wind-direction features:",
    remaining_wind_features
)

if remaining_wind_features:

    raise RuntimeError(
        "Saved feature file still contains "
        "wind-direction features."
    )

print(
    "Verification successful."
)


# ============================================================
# 19. SAVE PREDICTIONS
# ============================================================

predictions = df.loc[
    test_mask,
    [
        "timestamp",
        "station_name",
        "pm25"
    ]
].copy()

predictions[
    "actual_pm25_next_1h"
] = y_test.values

predictions[
    "predicted_pm25_next_1h"
] = y_pred

predictions[
    "error"
] = (
    predictions[
        "actual_pm25_next_1h"
    ]
    -
    predictions[
        "predicted_pm25_next_1h"
    ]
)

predictions.to_csv(
    PREDICTION_PATH,
    index=False
)

print(
    "\nPredictions saved:"
)

print(
    PREDICTION_PATH
)


# ============================================================
# COMPLETE
# ============================================================

print(
    "\n======================================"
)

print(
    "FORECAST TRAINING COMPLETED"
)

print(
    "======================================"
)
