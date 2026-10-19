import importlib.util
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

print("1/5 Loading corrected candidate...", flush=True)
path = Path("backend/ml/forecasting/pune_multistation_xgboost.phase3_candidate.py")
spec = importlib.util.spec_from_file_location("oriva_candidate_benchmark", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

print("2/5 Building exact-hour features...", flush=True)
raw = pd.read_csv("data/processed/pune_cpcb_all_stations_hourly.csv", low_memory=False)
data, features, stations = module.make_features(raw, training=True)
data = data.sort_values("timestamp").reset_index(drop=True)

times = data["timestamp"].drop_duplicates().sort_values().reset_index(drop=True)
train_cut = times.iloc[int(len(times) * 0.70)]
val_cut = times.iloc[int(len(times) * 0.85)]

# Keep training targets within the training period to avoid boundary leakage.
train = data[
    (data["timestamp"] < train_cut)
    & (data["timestamp"] + pd.Timedelta(hours=1) <= train_cut)
].copy()
validation = data[
    (data["timestamp"] >= train_cut)
    & (data["timestamp"] < val_cut)
    & (data["timestamp"] + pd.Timedelta(hours=1) <= val_cut)
].copy()
test = data[data["timestamp"] >= val_cut].copy()

if min(len(train), len(validation), len(test)) == 0:
    raise SystemExit("STOP: chronological split produced an empty partition.")

print(
    f"Rows: train={len(train):,}, validation={len(validation):,}, "
    f"test={len(test):,}; features={len(features)}; stations={len(stations)}",
    flush=True,
)

medians = train[features].median(numeric_only=True).fillna(0)
X_train = train[features].fillna(medians).fillna(0)
X_val = validation[features].fillna(medians).fillna(0)
X_test = test[features].fillna(medians).fillna(0)
y_train = train["target_pm25_next_1h"]
y_val = validation["target_pm25_next_1h"]
y_test = test["target_pm25_next_1h"]

print("3/5 Training residual XGBoost in memory...", flush=True)

# Learn the next-hour change instead of the full PM2.5 concentration.
residual_train = y_train - train["pm25"]
residual_val = y_val - validation["pm25"]

model = XGBRegressor(
    n_estimators=400,
    learning_rate=0.03,
    max_depth=6,
    min_child_weight=5,
    subsample=0.8,
    colsample_bytree=0.8,
    objective="reg:squarederror",
    random_state=42,
    tree_method="hist",
    n_jobs=4,
)
model.fit(
    X_train,
    residual_train,
    eval_set=[(X_val, residual_val)],
    verbose=False,
)


print("4/5 Selecting blend using validation only...", flush=True)

# Validation predictions: choose the weight without looking at test outcomes.
val_delta = model.predict(X_val)
val_residual = np.maximum(0.0, validation["pm25"].to_numpy() + val_delta)
val_baseline = validation["pm25"].to_numpy()
val_actual = y_val.to_numpy()

weights = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
scores = []
for weight in weights:
    blended = (1.0 - weight) * val_baseline + weight * val_residual
    scores.append((mean_absolute_error(val_actual, blended), weight))

best_mae, best_weight = min(scores)
print(f"Selected residual weight={best_weight:.1f}; validation MAE={best_mae:.4f}", flush=True)

print("5/5 Evaluating selected blend on test set...", flush=True)
test_delta = model.predict(X_test)
test_residual = np.maximum(0.0, test["pm25"].to_numpy() + test_delta)
test_baseline = test["pm25"].to_numpy()
test_actual = y_test.to_numpy()
test_blend = (1.0 - best_weight) * test_baseline + best_weight * test_residual

def report(name, predicted):
    print(
        f"{name}: MAE={mean_absolute_error(test_actual, predicted):.4f}; "
        f"RMSE={np.sqrt(mean_squared_error(test_actual, predicted)):.4f}; "
        f"R2={r2_score(test_actual, predicted):.4f}"
    )

report("Persistence baseline", test_baseline)
report("Selected validation blend", test_blend)
print("No model or dataset files were saved or changed.")
print("5/5 Finished. Model was not saved; production artifacts unchanged.")
