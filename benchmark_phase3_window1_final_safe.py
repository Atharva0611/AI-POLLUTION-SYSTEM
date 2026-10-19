from pathlib import Path
import importlib.util
import json
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

ROOT = Path.cwd()
CANDIDATE = ROOT / "backend/ml/forecasting/pune_multistation_xgboost.phase3_candidate.py"
REPORT = ROOT / "data/reports/phase3_window1_final_safe.json"

spec = importlib.util.spec_from_file_location("phase3_final_safe", CANDIDATE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

raw = pd.read_csv(module.DATA_PATH, low_memory=False)
data, features, _ = module.make_features(raw, training=True)
data = data.sort_values(["timestamp", "station_name"]).reset_index(drop=True)

start = pd.Timestamp("2025-02-06 01:00:00+00:00")
end = pd.Timestamp("2025-05-26 16:00:00+00:00")
pool = data[data.timestamp < start].copy()
test = data[(data.timestamp >= start) & (data.timestamp < end)].copy()

if len(pool) < 5000 or len(test) < 1000:
    raise SystemExit("STOP: unexpected data split; no production changes made.")

times = sorted(pool.timestamp.unique())
cut = times[int(len(times) * 0.80)]
train = pool[
    (pool.timestamp < cut) &
    (pool.timestamp + pd.Timedelta(hours=1) <= cut)
].copy()
val = pool[pool.timestamp >= cut].copy()

if len(train) < 1000 or len(val) < 1000:
    raise SystemExit("STOP: insufficient training/validation rows.")

medians = train[features].median(numeric_only=True).fillna(0)
X_train = train[features].fillna(medians).fillna(0)
X_val = val[features].fillna(medians).fillna(0)
X_test = test[features].fillna(medians).fillna(0)

model = XGBRegressor(
    n_estimators=400, learning_rate=0.03, max_depth=6,
    min_child_weight=5, subsample=0.8, colsample_bytree=0.8,
    objective="reg:squarederror", eval_metric="mae",
    random_state=42, tree_method="hist", n_jobs=4
)
model.fit(X_train, train["target_pm25_next_1h"] - train["pm25"], verbose=False)

val_current = val.pm25.to_numpy()
val_actual = val.target_pm25_next_1h.to_numpy()
val_ml = np.maximum(0, val_current + model.predict(X_val))
test_current = test.pm25.to_numpy()
test_actual = test.target_pm25_next_1h.to_numpy()
test_ml = np.maximum(0, test_current + model.predict(X_test))

# Conservative per-station weights: choose only from small weights.
# Require >=200 validation rows and >=2% validation MAE improvement.
weights = [0.0, 0.05, 0.10, 0.20]
station_weights = {}
validation_summary = []

for station in sorted(set(val.station_name) | set(test.station_name)):
    mask = val.station_name.to_numpy() == station
    n = int(mask.sum())
    selected = 0.0
    base_mae = None
    best_mae = None

    if n >= 200:
        base_mae = float(mean_absolute_error(val_actual[mask], val_current[mask]))
        candidates = []
        for w in weights:
            pred = (1 - w) * val_current[mask] + w * val_ml[mask]
            candidates.append((float(mean_absolute_error(val_actual[mask], pred)), w))
        best_mae, best_w = min(candidates, key=lambda x: x[0])
        if base_mae > 0 and best_mae <= base_mae * 0.98:
            selected = best_w

    station_weights[str(station)] = selected
    validation_summary.append({
        "station": str(station),
        "validation_rows": n,
        "persistence_validation_mae": None if base_mae is None else round(base_mae, 4),
        "best_candidate_validation_mae": None if best_mae is None else round(best_mae, 4),
        "selected_weight": selected
    })

weights_for_test = test.station_name.map(station_weights).fillna(0).to_numpy()
station_blend = (1 - weights_for_test) * test_current + weights_for_test * test_ml
global_blend = 0.95 * test_current + 0.05 * test_ml

def score(actual, pred):
    return {
        "mae": round(float(mean_absolute_error(actual, pred)), 4),
        "rmse": round(float(np.sqrt(mean_squared_error(actual, pred))), 4),
        "r2": round(float(r2_score(actual, pred)), 4)
    }

per_station = []
for station, g in test.assign(
    persistence=test_current,
    global_005=global_blend,
    station_blend=station_blend
).groupby("station_name"):
    per_station.append({
        "station": str(station),
        "rows": int(len(g)),
        "persistence_mae": round(float(mean_absolute_error(g.target_pm25_next_1h, g.persistence)), 4),
        "global_005_mae": round(float(mean_absolute_error(g.target_pm25_next_1h, g.global_005)), 4),
        "station_blend_mae": round(float(mean_absolute_error(g.target_pm25_next_1h, g.station_blend)), 4),
        "selected_weight": station_weights.get(str(station), 0.0)
    })

result = {
    "purpose": "non_production_experiment",
    "window1_rows": int(len(test)),
    "training_rows": int(len(train)),
    "validation_rows": int(len(val)),
    "validation_cut": str(cut),
    "metrics": {
        "persistence": score(test_actual, test_current),
        "global_005_blend": score(test_actual, global_blend),
        "validation_selected_station_blend": score(test_actual, station_blend)
    },
    "validation_weight_selection": validation_summary,
    "window1_station_diagnostics": per_station,
    "decision": "NO PRODUCTION PROMOTION: Window 1 has already been examined; independent later evaluation is required.",
    "production_artifacts_modified": False
}

REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
print(f"\nReport saved: {REPORT}")
print("Production model, feature files, medians, metrics, and dataset were not saved or modified.")
