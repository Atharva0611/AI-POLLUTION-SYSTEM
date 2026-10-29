import json
import joblib
import numpy as np
import pandas as pd
import shap
from pathlib import Path
from xgboost import XGBRegressor

root = Path.cwd()
data_dir = root / "data" / "processed"
artifacts = root / "models" / "forecasting" / "pune_pm25_24h_candidate"

# 1. Inspect the authoritative station registry.
registry_path = data_dir / "cpcb_station_registry.json"
registry = json.loads(registry_path.read_text(encoding="utf-8-sig"))
print("REGISTRY TYPE:", type(registry).__name__)
print("REGISTRY ENTRIES:", len(registry))
if isinstance(registry, dict):
    for name, item in list(registry.items())[:2]:
        print("REGISTRY SAMPLE:", name, item)

# 2. Build features using the same feature builder used by training.
from backend.ml.forecasting.build_pune_features import build_features

source_path = data_dir / "pune_cpcb_all_stations_hourly.csv"
raw = pd.read_csv(source_path, low_memory=False)
features_df = build_features(raw)
feature_names = list(joblib.load(artifacts / "feature_columns.joblib"))
medians = joblib.load(artifacts / "medians_h01.joblib")
model = joblib.load(artifacts / "xgb_pm25_h01.joblib")

print("FEATURE DATASET SHAPE:", features_df.shape)
print("FEATURE SCHEMA COUNT:", len(feature_names))
print("FEATURES AVAILABLE:", sum(c in features_df.columns for c in feature_names))

missing_columns = [c for c in feature_names if c not in features_df.columns]
if missing_columns:
    raise RuntimeError(
        f"Feature builder does not produce all trained features: {missing_columns}"
    )

# Choose a real row with a valid target and at least some measured data.
valid = features_df.loc[features_df["pm25"].notna()].copy()
if valid.empty:
    raise RuntimeError("No valid PM2.5 rows are available.")

row = valid.iloc[-1]
X = pd.DataFrame([row[feature_names].to_dict()], columns=feature_names)
X = X.replace([np.inf, -np.inf], np.nan).apply(
    pd.to_numeric, errors="coerce"
).fillna(pd.Series(medians)).fillna(0.0)
X = X.astype(float)

if X.shape != (1, 133):
    raise RuntimeError(f"Unexpected SHAP input shape: {X.shape}")
if not np.isfinite(X.to_numpy()).all():
    raise RuntimeError("SHAP input contains non-finite values.")

# 3. Compute and validate real SHAP values for the candidate model.
explainer = shap.TreeExplainer(model)
explanation = explainer(X)
values = np.asarray(explanation.values).reshape(-1)
base = float(np.asarray(explanation.base_values).reshape(-1)[0])
prediction = float(np.asarray(model.predict(X)).reshape(-1)[0])

if len(values) != len(feature_names):
    raise RuntimeError(
        f"SHAP contribution count {len(values)} != {len(feature_names)} features"
    )

reconstructed = base + float(values.sum())
if not np.isclose(reconstructed, prediction, rtol=1e-3, atol=1e-2):
    raise RuntimeError(
        f"SHAP additivity check failed: base + contributions={reconstructed:.4f}, "
        f"prediction={prediction:.4f}"
    )

out_dir = data_dir / "shap"
out_dir.mkdir(parents=True, exist_ok=True)
result = pd.DataFrame({
    "feature": feature_names,
    "feature_value": X.iloc[0].to_numpy(),
    "shap_value": values,
    "absolute_impact": np.abs(values),
    "direction": np.where(values >= 0, "increases_prediction", "decreases_prediction"),
}).sort_values("absolute_impact", ascending=False)

out_file = out_dir / "pm25_h01_shap_diagnostic.csv"
result.to_csv(out_file, index=False)

print("\nSHAP DIAGNOSTIC PASS")
print("Station:", row["station_name"])
print("Timestamp:", row["timestamp"])
print("Prediction:", round(prediction, 4))
print("Base value:", round(base, 4))
print("Contribution count:", len(values))
print("Additivity difference:", round(prediction - reconstructed, 8))
print("Top 10 features:")
print(result.head(10).to_string(index=False))
print("Saved:", out_file)
