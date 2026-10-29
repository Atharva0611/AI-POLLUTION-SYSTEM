from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
import shap

ROOT = Path.cwd()
DATA = ROOT / "data/processed/pune_cpcb_all_stations_hourly.csv"
MODEL_DIR = ROOT / "models/forecasting/pune_pm25_24h_candidate"
REPORT_DIR = ROOT / "reports/shap"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

required_files = [
    DATA,
    MODEL_DIR / "xgb_pm25_h24.joblib",
    MODEL_DIR / "medians_h24.joblib",
    MODEL_DIR / "feature_columns.joblib",
]
missing = [str(p) for p in required_files if not p.exists()]
if missing:
    raise FileNotFoundError(f"Required model/data artifacts missing: {missing}")

print("Loading hourly data...")
df = pd.read_csv(DATA, low_memory=False)
required = {"station_name", "timestamp", "pm25"}
if not required.issubset(df.columns):
    raise ValueError(f"Dataset missing required columns: {sorted(required - set(df.columns))}")

df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
df["station_name"] = df["station_name"].astype("string").str.strip()
for col in df.columns:
    if col not in ("station_name", "timestamp"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

df = df.dropna(subset=["station_name", "timestamp"])
df = df.sort_values(["station_name", "timestamp"]).reset_index(drop=True)
if df.duplicated(["station_name", "timestamp"]).any():
    raise ValueError("Duplicate station/timestamp records; refusing to explain ambiguous rows.")

base_cols = [
    c for c in [
        "pm25", "pm10", "no2", "so2", "co", "o3", "nh3",
        "temperature", "humidity", "pressure", "wind_speed",
        "wind_direction", "rainfall"
    ] if c in df.columns
]
lags = [1, 2, 3, 6, 12, 24, 48, 72]
features = []
grouped = df.groupby("station_name", sort=False)

for col in base_cols:
    features.append(col)
for col in base_cols:
    for lag in lags:
        name = f"{col}_lag_{lag}h"
        df[name] = grouped[col].shift(lag)
        features.append(name)

# Match training's calendar-feature definition for the +24h target.
target_dt = df["timestamp"] + pd.Timedelta(hours=24)
df["hour"] = target_dt.dt.hour
df["day_of_week"] = target_dt.dt.dayofweek
df["month"] = target_dt.dt.month
df["day_of_year"] = target_dt.dt.dayofyear
features += ["hour", "day_of_week", "month", "day_of_year"]

dummies = pd.get_dummies(df["station_name"], prefix="station", dtype=float)
df = pd.concat([df, dummies], axis=1)
features += dummies.columns.tolist()
features = list(dict.fromkeys(features))

trained_features = joblib.load(MODEL_DIR / "feature_columns.joblib")
if len(trained_features) != len(set(trained_features)):
    raise ValueError("Saved model schema contains duplicate feature names.")

missing_features = [f for f in trained_features if f not in df.columns]
if missing_features:
    raise ValueError(
        f"Cannot explain model: feature pipeline still misses {len(missing_features)} "
        f"trained features: {missing_features}"
    )

model = joblib.load(MODEL_DIR / "xgb_pm25_h24.joblib")
medians = joblib.load(MODEL_DIR / "medians_h24.joblib")
if set(trained_features) - set(medians):
    raise ValueError("Horizon-24 medians do not cover the saved feature schema.")

# Keep actual observed rows and apply exactly the saved training schema/imputation.
X = df.loc[df["pm25"].notna(), trained_features].copy()
X = X.replace([np.inf, -np.inf], np.nan)
X = X.fillna(pd.Series(medians).reindex(trained_features)).fillna(0.0)
if X.empty:
    raise ValueError("No rows available for SHAP explanation.")

# Bounded, reproducible sample for manageable memory and runtime.
sample = X.tail(min(256, len(X))).copy()
print(f"Training schema: {len(trained_features)} features")
print(f"Rows used for explanation: {len(sample)}")
print("Computing TreeSHAP values for +24h model...")

explainer = shap.TreeExplainer(model)
values = explainer.shap_values(sample, check_additivity=False)
values = np.asarray(values)
if values.ndim == 3:
    values = values[..., 0]
if values.shape != sample.shape:
    raise RuntimeError(f"Unexpected SHAP shape {values.shape}; input shape {sample.shape}")

importance = pd.DataFrame({
    "feature": trained_features,
    "mean_abs_shap": np.abs(values).mean(axis=0),
    "mean_shap": values.mean(axis=0),
}).sort_values("mean_abs_shap", ascending=False)

importance_path = REPORT_DIR / "pm25_h24_shap_feature_importance.csv"
importance.to_csv(importance_path, index=False)

row_index = len(sample) - 1
local = pd.DataFrame({
    "feature": trained_features,
    "feature_value": sample.iloc[row_index].to_numpy(),
    "shap_value": values[row_index],
})
local["abs_shap"] = local["shap_value"].abs()
local = local.sort_values("abs_shap", ascending=False)
local_path = REPORT_DIR / "pm25_h24_shap_latest_sample.csv"
local.to_csv(local_path, index=False)

prediction = float(np.asarray(model.predict(sample.iloc[[row_index]])).reshape(-1)[0])
base_value = np.asarray(explainer.expected_value).reshape(-1)
summary = {
    "model": "xgb_pm25_h24.joblib",
    "horizon_hours": 24,
    "feature_count": len(trained_features),
    "explanation_rows": len(sample),
    "sample_station": str(df.loc[sample.index[row_index], "station_name"]),
    "sample_timestamp_utc": str(df.loc[sample.index[row_index], "timestamp"]),
    "predicted_pm25": prediction,
    "shap_expected_value": float(base_value[0]),
    "top_features": importance.head(10).to_dict(orient="records"),
    "top_local_contributions": local.head(10).to_dict(orient="records"),
    "method": "shap.TreeExplainer",
}
summary_path = REPORT_DIR / "pm25_h24_shap_summary.json"
summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

print("\nSHAP SUCCESS")
print("Importance CSV:", importance_path)
print("Local explanation CSV:", local_path)
print("Summary JSON:", summary_path)
print("\nTop global features:")
print(importance.head(10).to_string(index=False))
print("\nExplained sample prediction:", round(prediction, 3), "ug/m3")
print("Note: this is a model prediction, not a measured future observation.")
