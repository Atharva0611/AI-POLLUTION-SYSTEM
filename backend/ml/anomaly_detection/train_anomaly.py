import os
import joblib
import pandas as pd
import numpy as np

from sklearn.ensemble import IsolationForest


ROOT = r"C:\final year project\AI-POLLUTION-SYSTEM"

DATA_FILE = os.path.join(
    ROOT,
    "data",
    "processed",
    "pune_cpcb_features.csv"
)

MODEL_DIR = os.path.join(
    ROOT,
    "models",
    "anomaly_detection"
)

MODEL_FILE = os.path.join(
    MODEL_DIR,
    "isolation_forest.pkl"
)

FEATURE_FILE = os.path.join(
    MODEL_DIR,
    "anomaly_features.pkl"
)

os.makedirs(
    MODEL_DIR,
    exist_ok=True
)


# ============================================================
# LOAD DATA
# ============================================================

df = pd.read_csv(
    DATA_FILE
)

print(
    "Dataset shape:",
    df.shape
)


# ============================================================
# SELECT POLLUTION FEATURES
# ============================================================

candidate_features = [
    "pm25",
    "pm2_5",
    "pm10",
    "no2",
    "so2",
    "co",
    "o3",
    "nh3"
]

features = [
    x for x in candidate_features
    if x in df.columns
]

if not features:

    raise ValueError(
        "No pollution columns found.\n"
        f"Available columns:\n{df.columns.tolist()}"
    )


print(
    "Anomaly features:",
    features
)


# ============================================================
# CLEAN DATA
# ============================================================

X = df[features].copy()

for col in features:

    X[col] = pd.to_numeric(
        X[col],
        errors="coerce"
    )

X = X.replace(
    [np.inf, -np.inf],
    np.nan
)

# Use median imputation
X = X.fillna(
    X.median()
)

# Remove completely invalid rows
X = X.dropna(
    how="all"
)

if X.empty:

    raise ValueError(
        "No usable data remains after cleaning."
    )


# ============================================================
# TRAIN ISOLATION FOREST
# ============================================================

print(
    "\nTraining Isolation Forest..."
)

model = IsolationForest(
    n_estimators=300,
    contamination=0.02,
    random_state=42,
    n_jobs=-1
)

model.fit(
    X
)


# ============================================================
# PREDICT
# ============================================================

predictions = model.predict(
    X
)

scores = model.decision_function(
    X
)

result_df = df.loc[
    X.index
].copy()

result_df[
    "anomaly_label"
] = predictions

result_df[
    "anomaly_score"
] = scores

result_df[
    "is_anomaly"
] = (
    predictions == -1
)


# ============================================================
# SAVE
# ============================================================

joblib.dump(
    model,
    MODEL_FILE
)

joblib.dump(
    features,
    FEATURE_FILE
)

OUTPUT_FILE = os.path.join(
    ROOT,
    "data",
    "processed",
    "pune_anomaly_results.csv"
)

result_df.to_csv(
    OUTPUT_FILE,
    index=False
)


print()
print("=" * 70)
print("ISOLATION FOREST COMPLETE")
print("=" * 70)

print(
    "Features:",
    features
)

print(
    "Total records:",
    len(result_df)
)

print(
    "Anomalies:",
    int(
        result_df["is_anomaly"].sum()
    )
)

print(
    "Normal:",
    int(
        (~result_df["is_anomaly"]).sum()
    )
)

print()
print(
    "Model:",
    MODEL_FILE
)

print(
    "Features:",
    FEATURE_FILE
)

print(
    "Results:",
    OUTPUT_FILE
)
