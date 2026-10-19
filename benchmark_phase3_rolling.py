from pathlib import Path
import importlib.util
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

print("1/5 Loading exact-hour candidate...", flush=True)
path = Path("backend/ml/forecasting/pune_multistation_xgboost.phase3_candidate.py")
spec = importlib.util.spec_from_file_location("oriva_rolling_candidate", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

print("2/5 Building features...", flush=True)
raw = pd.read_csv("data/processed/pune_cpcb_all_stations_hourly.csv", low_memory=False)
data, features, stations = module.make_features(raw, training=True)
data = data.sort_values("timestamp").reset_index(drop=True)

times = data["timestamp"].drop_duplicates().sort_values().reset_index(drop=True)
cuts = [times.iloc[int(len(times) * p)] for p in (0.55, 0.70, 0.85)]
windows = [
    ("Window 1", cuts[0], cuts[1]),
    ("Window 2", cuts[1], cuts[2]),
    ("Window 3", cuts[2], times.iloc[-1] + pd.Timedelta(hours=1)),
]

print("Rows:", len(data), "| Features:", len(features), "| Stations:", len(stations))
print("3/5 Running corrected residual benchmarks...", flush=True)

for name, start, end in windows:
    train = data[
        (data["timestamp"] < start)
        & (data["timestamp"] + pd.Timedelta(hours=1) <= start)
    ].copy()
    test = data[
        (data["timestamp"] >= start)
        & (data["timestamp"] < end)
    ].copy()

    if len(train) < 1000 or len(test) < 100:
        print(f"{name}: SKIPPED - insufficient rows")
        continue

    medians = train[features].median(numeric_only=True).fillna(0)
    X_train = train[features].fillna(medians).fillna(0)
    X_test = test[features].fillna(medians).fillna(0)

    # Correct: predict next-hour change, not full concentration.
    residual_train = train["target_pm25_next_1h"] - train["pm25"]

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
    model.fit(X_train, residual_train, verbose=False)

    current = test["pm25"].to_numpy()
    actual = test["target_pm25_next_1h"].to_numpy()
    delta = model.predict(X_test)
    residual_prediction = np.maximum(0.0, current + delta)
    blend = 0.4 * current + 0.6 * residual_prediction

    print(f"\n{name}: {start} to {end}")
    print(f"Train rows={len(train):,}; test rows={len(test):,}")

    for label, prediction in [
        ("Persistence", current),
        ("Residual XGBoost", residual_prediction),
        ("Fixed 0.6 blend", blend),
    ]:
        print(
            f"{label}: MAE={mean_absolute_error(actual, prediction):.4f}; "
            f"RMSE={np.sqrt(mean_squared_error(actual, prediction)):.4f}; "
            f"R2={r2_score(actual, prediction):.4f}"
        )

print("\n5/5 Finished. Temporary models only; production artifacts unchanged.")
