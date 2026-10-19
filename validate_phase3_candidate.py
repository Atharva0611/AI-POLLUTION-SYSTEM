import importlib.util
import pandas as pd
import numpy as np
from pathlib import Path

source = Path("backend/ml/forecasting/pune_multistation_xgboost.phase3_candidate.py")
dataset = Path("data/processed/pune_cpcb_all_stations_hourly.csv")

print("1/4 Loading candidate...", flush=True)
spec = importlib.util.spec_from_file_location("oriva_phase3_candidate", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

print("2/4 Building candidate features...", flush=True)
raw = pd.read_csv(dataset, low_memory=False)
built, features, stations = module.make_features(raw, training=False)

print("3/4 Checking exact-hour PM2.5 lags...", flush=True)
ref = module.normalize(raw).dropna(subset=["timestamp", "station_name"]).copy()
ref["station_name"] = ref["station_name"].astype(str).str.strip()
ref = ref[ref["station_name"].ne("") & ref["station_name"].str.lower().ne("nan")]

if ref.duplicated(["station_name", "timestamp"]).any():
    raise SystemExit("FAIL: duplicate station/timestamp keys")

lookup = pd.Series(
    ref["pm25"].to_numpy(),
    index=pd.MultiIndex.from_frame(ref[["station_name", "timestamp"]]),
)

for lag in [1, 3, 6, 12, 24]:
    query = pd.MultiIndex.from_arrays([
        built["station_name"].to_numpy(),
        (built["timestamp"] - pd.Timedelta(hours=lag)).to_numpy(),
    ])
    expected = lookup.reindex(query).to_numpy()
    actual = built[f"pm25_lag_{lag}"].to_numpy()
    valid = pd.notna(actual) & pd.notna(expected)
    mismatches = int((~np.isclose(actual[valid], expected[valid], rtol=0, atol=1e-10)).sum())
    print(f"Lag {lag:2}h: comparable={int(valid.sum()):,}; mismatches={mismatches:,}", flush=True)

print("4/4 Checking target and saved model schema...", flush=True)
query = pd.MultiIndex.from_arrays([
    built["station_name"].to_numpy(),
    (built["timestamp"] + pd.Timedelta(hours=1)).to_numpy(),
])
expected = lookup.reindex(query).to_numpy()
actual = built["target_pm25_next_1h"].to_numpy()
valid = pd.notna(actual) & pd.notna(expected)
target_mismatches = int((~np.isclose(actual[valid], expected[valid], rtol=0, atol=1e-10)).sum())

features_path = Path("models/forecasting/pune_multistation_features.pkl")
model_path = Path("models/forecasting/pune_multistation_xgboost.pkl")
import joblib
saved_features = joblib.load(features_path)
model = joblib.load(model_path)

print(f"Target: comparable={int(valid.sum()):,}; mismatches={target_mismatches:,}")
print(f"Candidate rows={len(built):,}; features={len(features)}; stations={len(stations)}")
print(f"Saved feature count={len(saved_features)}; model input count={model.n_features_in_}")
print(f"Feature names match saved schema: {features == saved_features}")
print("Read-only validation complete; no production files changed.")
