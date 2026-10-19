from pathlib import Path
import importlib.util
import json
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error
from xgboost import XGBRegressor

root = Path(__file__).resolve().parent
candidate = root / "backend/ml/forecasting/pune_multistation_xgboost.phase3_candidate.py"
output = root / "data/reports/phase3_window1_station_diagnostics.json"

spec = importlib.util.spec_from_file_location("phase3_diagnostic_model", candidate)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

raw = pd.read_csv(module.DATA_PATH, low_memory=False)
data, features, _ = module.make_features(raw, training=True)
data = data.sort_values(["timestamp", "station_name"]).reset_index(drop=True)

start = pd.Timestamp("2025-02-06 01:00:00+00:00")
end = pd.Timestamp("2025-05-26 16:00:00+00:00")
pool = data[data.timestamp < start].copy()
test = data[(data.timestamp >= start) & (data.timestamp < end)].copy()

times = sorted(pool.timestamp.unique())
val_start = times[int(len(times) * 0.80)]
train = pool[
    (pool.timestamp < val_start) &
    (pool.timestamp + pd.Timedelta(hours=1) <= val_start)
].copy()
validation = pool[pool.timestamp >= val_start].copy()

medians = train[features].median(numeric_only=True).fillna(0)
X_train = train[features].fillna(medians).fillna(0)
X_val = validation[features].fillna(medians).fillna(0)
X_test = test[features].fillna(medians).fillna(0)

model = XGBRegressor(
    n_estimators=400, learning_rate=0.03, max_depth=6,
    min_child_weight=5, subsample=0.8, colsample_bytree=0.8,
    objective="reg:squarederror", eval_metric="mae",
    random_state=42, tree_method="hist", n_jobs=4,
)
model.fit(X_train, train["target_pm25_next_1h"] - train["pm25"], verbose=False)

val_current = validation.pm25.to_numpy()
val_residual = np.maximum(0, val_current + model.predict(X_val))
val_actual = validation.target_pm25_next_1h.to_numpy()
weights = []
for w in np.arange(0, 1.001, 0.05):
    pred = (1 - w) * val_current + w * val_residual
    weights.append((mean_absolute_error(val_actual, pred), float(w)))
best_weight = min(weights)[1]

current = test.pm25.to_numpy()
actual = test.target_pm25_next_1h.to_numpy()
residual = np.maximum(0, current + model.predict(X_test))
blend = (1 - best_weight) * current + best_weight * residual

d = test[["timestamp", "station_name", "pm25"]].copy()
d["actual"] = actual
d["persistence_prediction"] = current
d["blend_prediction"] = blend
d["persistence_abs_error"] = np.abs(actual - current)
d["blend_abs_error"] = np.abs(actual - blend)
d["mae_change_blend_minus_persistence"] = (
    d["blend_abs_error"] - d["persistence_abs_error"]
)

station_rows = []
for station, g in d.groupby("station_name"):
    station_rows.append({
        "station": str(station),
        "rows": int(len(g)),
        "persistence_mae": round(float(g.persistence_abs_error.mean()), 4),
        "blend_mae": round(float(g.blend_abs_error.mean()), 4),
        "mae_change": round(float(g.mae_change_blend_minus_persistence.mean()), 4),
        "blend_worse_rows_pct": round(float(
            (g.mae_change_blend_minus_persistence > 0).mean() * 100
        ), 2),
    })

# Descriptive diagnostic only: these are Window 1 test results, not tuning data.
d["pm25_band"] = pd.cut(
    d["pm25"],
    bins=[-np.inf, 5, 15, 30, 55, 100, np.inf],
    labels=["<=5", "5-15", "15-30", "30-55", "55-100", ">100"],
    right=True,
)
band_rows = []
for (station, band), g in d.groupby(
    ["station_name", "pm25_band"], observed=True
):
    band_rows.append({
        "station": str(station),
        "current_pm25_band": str(band),
        "rows": int(len(g)),
        "persistence_mae": round(float(g.persistence_abs_error.mean()), 4),
        "blend_mae": round(float(g.blend_abs_error.mean()), 4),
        "mae_change": round(float(g.mae_change_blend_minus_persistence.mean()), 4),
    })

result = {
    "purpose": "diagnostics_only_not_for_model_selection",
    "selected_validation_weight": best_weight,
    "validation_mae": round(float(min(weights)[0]), 4),
    "window1_rows": int(len(d)),
    "overall": {
        "persistence_mae": round(float(d.persistence_abs_error.mean()), 4),
        "blend_mae": round(float(d.blend_abs_error.mean()), 4),
        "mean_mae_change": round(float(
            d.mae_change_blend_minus_persistence.mean()
        ), 4),
    },
    "by_station": sorted(
        station_rows, key=lambda x: x["mae_change"], reverse=True
    ),
    "by_station_and_pm25_band": sorted(
        band_rows, key=lambda x: x["mae_change"], reverse=True
    ),
    "production_artifacts_modified": False,
}
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(result, indent=2), encoding="utf-8")

print(json.dumps(result, indent=2))
print(f"\nDiagnostic report: {output}")
print("No production artifacts were saved or modified.")
