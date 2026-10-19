from pathlib import Path
import importlib.util
import json

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parent
CANDIDATE = ROOT / "backend/ml/forecasting/pune_multistation_xgboost.phase3_candidate.py"
REPORT = ROOT / "data/reports/phase3_window1_safe_experiment.json"

spec = importlib.util.spec_from_file_location("phase3_candidate_window1", CANDIDATE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

raw = pd.read_csv(module.DATA_PATH, low_memory=False)
data, features, stations = module.make_features(raw, training=True)
data = data.sort_values(["timestamp", "station_name"]).reset_index(drop=True)

times = pd.Series(sorted(data["timestamp"].dropna().unique()))
if len(times) < 100:
    raise SystemExit("STOP: insufficient unique timestamps.")

window1_start = pd.Timestamp("2025-02-06 01:00:00+00:00")
window1_end = pd.Timestamp("2025-05-26 16:00:00+00:00")

# Keep Window 1 completely out of training and weight selection.
train_pool = data[data["timestamp"] < window1_start].copy()
test = data[
    (data["timestamp"] >= window1_start) &
    (data["timestamp"] < window1_end)
].copy()

if len(train_pool) < 5000 or len(test) < 1000:
    raise SystemExit(
        f"STOP: unexpected split sizes: train_pool={len(train_pool)}, test={len(test)}"
    )

# Use the last 20% of the pre-window training pool for validation.
train_times = sorted(train_pool["timestamp"].unique())
val_start = train_times[int(len(train_times) * 0.80)]
train = train_pool[
    (train_pool["timestamp"] < val_start) &
    (train_pool["timestamp"] + pd.Timedelta(hours=1) <= val_start)
].copy()
validation = train_pool[train_pool["timestamp"] >= val_start].copy()

if min(len(train), len(validation)) < 1000:
    raise SystemExit("STOP: insufficient training or validation rows.")

medians = train[features].median(numeric_only=True).fillna(0)
X_train = train[features].fillna(medians).fillna(0)
X_val = validation[features].fillna(medians).fillna(0)
X_test = test[features].fillna(medians).fillna(0)

y_train_delta = train["target_pm25_next_1h"] - train["pm25"]
y_val = validation["target_pm25_next_1h"].to_numpy()
y_test = test["target_pm25_next_1h"].to_numpy()

model = XGBRegressor(
    n_estimators=400,
    learning_rate=0.03,
    max_depth=6,
    min_child_weight=5,
    subsample=0.8,
    colsample_bytree=0.8,
    objective="reg:squarederror",
    eval_metric="mae",
    random_state=42,
    tree_method="hist",
    n_jobs=4,
)
model.fit(X_train, y_train_delta, verbose=False)

val_current = validation["pm25"].to_numpy()
val_residual = np.maximum(0.0, val_current + model.predict(X_val))
val_weights = []

for weight in np.arange(0.0, 1.01, 0.05):
    pred = (1.0 - weight) * val_current + weight * val_residual
    val_weights.append((
        float(mean_absolute_error(y_val, pred)),
        float(weight),
    ))

best_val_mae, best_weight = min(val_weights, key=lambda item: item[0])

test_current = test["pm25"].to_numpy()
test_residual = np.maximum(0.0, test_current + model.predict(X_test))
test_blend = (1.0 - best_weight) * test_current + best_weight * test_residual

def metrics(actual, prediction):
    return {
        "mae": round(float(mean_absolute_error(actual, prediction)), 4),
        "rmse": round(float(np.sqrt(mean_squared_error(actual, prediction))), 4),
        "r2": round(float(r2_score(actual, prediction)), 4),
    }

scores = {
    "persistence": metrics(y_test, test_current),
    "residual_xgboost": metrics(y_test, test_residual),
    "validation_selected_blend": metrics(y_test, test_blend),
}
station_results = []
for station, group in test.assign(
    persistence=test_current,
    blend=test_blend,
).groupby("station_name"):
    station_results.append({
        "station": str(station),
        "rows": int(len(group)),
        "persistence_mae": round(float(mean_absolute_error(
            group["target_pm25_next_1h"], group["persistence"]
        )), 4),
        "blend_mae": round(float(mean_absolute_error(
            group["target_pm25_next_1h"], group["blend"]
        )), 4),
    })

result = {
    "experiment": "isolated_window1_validation_selected_blend",
    "train_rows": int(len(train)),
    "validation_rows": int(len(validation)),
    "window1_rows": int(len(test)),
    "train_end": str(train["timestamp"].max()),
    "validation_start": str(validation["timestamp"].min()),
    "window1_start": str(test["timestamp"].min()),
    "window1_end": str(test["timestamp"].max()),
    "selected_weight": best_weight,
    "validation_mae": round(best_val_mae, 4),
    "metrics": scores,
    "per_station": station_results,
    "production_artifacts_modified": False,
}

REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")

print(json.dumps(result, indent=2))
print(f"\nReport saved to: {REPORT}")
print("Temporary model only; no production model or dataset saved.")
