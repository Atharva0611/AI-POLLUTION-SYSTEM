from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "processed" / "pune_cpcb_all_stations_hourly.csv"
OUT = ROOT / "models" / "forecasting" / "pune_pm25_24h_candidate"
HORIZONS = range(1, 25)
LAGS = [1, 2, 3, 6, 12, 24, 48, 72]

def main():
    if not DATA.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA}")

    print(f"Loading {DATA}")
    df = pd.read_csv(DATA, low_memory=False)

    required = {"station_name", "timestamp", "pm25"}
    if not required.issubset(df.columns):
        raise ValueError(f"Missing required columns: {required - set(df.columns)}")

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    df["station_name"] = df["station_name"].astype("string").str.strip()
    for col in df.columns:
        if col not in ("station_name", "timestamp"):
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["station_name", "timestamp"])
    df = df.sort_values(["station_name", "timestamp"]).reset_index(drop=True)

    if df.duplicated(["station_name", "timestamp"]).any():
        raise ValueError("Duplicate station/timestamp rows detected.")

    # Only measurements available at the forecast origin are predictors.
    feature_cols = []
    for col in [
        "pm25", "pm10", "no2", "so2", "co", "o3", "nh3",
        "temperature", "humidity", "pressure", "wind_speed",
        "wind_direction", "rainfall"
    ]:
        if col in df.columns:
            feature_cols.append(col)

    grouped = df.groupby("station_name", sort=False)
    for col in feature_cols.copy():
        for lag in LAGS:
            name = f"{col}_lag_{lag}h"
            df[name] = grouped[col].shift(lag)
            feature_cols.append(name)

    # Calendar predictors for the time being predicted, not the origin.
    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["month"] = df["timestamp"].dt.month
    df["day_of_year"] = df["timestamp"].dt.dayofyear
    feature_cols += ["hour", "day_of_week", "month", "day_of_year"]

    dummies = pd.get_dummies(df["station_name"], prefix="station", dtype=float)
    df = pd.concat([df, dummies], axis=1)
    feature_cols += dummies.columns.tolist()
    feature_cols = list(dict.fromkeys(feature_cols))

    # Exact timestamp lookup prevents treating a later row as an exact-hour target.
    index = pd.MultiIndex.from_frame(df[["station_name", "timestamp"]])
    pm25_lookup = pd.Series(df["pm25"].to_numpy(), index=index)

    times = np.sort(df["timestamp"].dropna().unique())
    if len(times) < 100:
        raise ValueError("Not enough distinct timestamps for chronological evaluation.")

    train_cut = pd.Timestamp(times[int(len(times) * 0.70)])
    val_cut = pd.Timestamp(times[int(len(times) * 0.85)])
    print(f"Stations: {df['station_name'].nunique()}")
    print(f"Train target cutoff: {train_cut}")
    print(f"Validation target cutoff: {val_cut}")

    OUT.mkdir(parents=True, exist_ok=True)
    results = []

    for horizon in HORIZONS:
        print(f"\n===== Training horizon +{horizon:02d}h =====")

        future_index = pd.MultiIndex.from_arrays([
            df["station_name"].to_numpy(),
            (df["timestamp"] + pd.Timedelta(hours=horizon)).to_numpy()
        ])
        target = pm25_lookup.reindex(future_index).to_numpy()

        # Exclude examples without a valid target or current PM2.5 baseline.
        valid = np.isfinite(target) & df["pm25"].notna().to_numpy()
        valid &= df["timestamp"].notna().to_numpy()

        data = df.loc[valid].copy()
        data["target_pm25"] = target[valid]
        data["target_timestamp"] = data["timestamp"] + pd.Timedelta(hours=horizon)

        # Calendar features must describe the time being predicted.
        target_dt = data["target_timestamp"]
        data["hour"] = target_dt.dt.hour
        data["day_of_week"] = target_dt.dt.dayofweek
        data["month"] = target_dt.dt.month
        data["day_of_year"] = target_dt.dt.dayofyear

        train = data[data["target_timestamp"] <= train_cut]
        val = data[
            (data["target_timestamp"] > train_cut) &
            (data["target_timestamp"] <= val_cut)
        ]
        test = data[data["target_timestamp"] > val_cut]

        if min(len(train), len(val), len(test)) == 0:
            raise ValueError(f"Empty chronological split at horizon +{horizon}h")

        medians = train[feature_cols].median(numeric_only=True).fillna(0)
        X_train = train[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0)
        X_val = val[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0)
        X_test = test[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0)

        model = XGBRegressor(
            n_estimators=350,
            learning_rate=0.04,
            max_depth=6,
            min_child_weight=5,
            subsample=0.8,
            colsample_bytree=0.8,
            objective="reg:squarederror",
            eval_metric="rmse",
            random_state=42,
            n_jobs=-1,
            tree_method="hist",
        )
        model.fit(
            X_train, train["target_pm25"],
            eval_set=[(X_val, val["target_pm25"])],
            verbose=False,
        )

        # Select the strategy using validation data only.
        val_pred = model.predict(X_val)
        val_actual = val["target_pm25"].to_numpy()
        val_baseline = val["pm25"].to_numpy()

        xgb_val_mae = float(mean_absolute_error(val_actual, val_pred))
        persistence_val_mae = float(mean_absolute_error(val_actual, val_baseline))
        selected_strategy = (
            "xgboost" if xgb_val_mae < persistence_val_mae else "persistence"
        )

        # Evaluate the validation-selected strategy once on the held-out test set.
        pred = model.predict(X_test)
        actual = test["target_pm25"].to_numpy()
        baseline = test["pm25"].to_numpy()
        selected_pred = pred if selected_strategy == "xgboost" else baseline

        result = {
            "horizon_hours": horizon,
            "train_rows": int(len(train)),
            "validation_rows": int(len(val)),
            "test_rows": int(len(test)),
            "selected_strategy": selected_strategy,
            "validation_xgboost_MAE": xgb_val_mae,
            "validation_persistence_MAE": persistence_val_mae,
            "selected_test_MAE": float(mean_absolute_error(actual, selected_pred)),
            "selected_test_RMSE": float(np.sqrt(mean_squared_error(actual, selected_pred))),
            "selected_test_R2": float(r2_score(actual, selected_pred)),
            "xgboost_test_MAE": float(mean_absolute_error(actual, pred)),
            "xgboost_test_RMSE": float(np.sqrt(mean_squared_error(actual, pred))),
            "xgboost_test_R2": float(r2_score(actual, pred)),
            "persistence_test_MAE": float(mean_absolute_error(actual, baseline)),
            "persistence_test_RMSE": float(np.sqrt(mean_squared_error(actual, baseline))),
        }
        results.append(result)

        joblib.dump(model, OUT / f"xgb_pm25_h{horizon:02d}.joblib")
        joblib.dump(medians.to_dict(), OUT / f"medians_h{horizon:02d}.joblib")
        print(
            f"+{horizon:02d}h | selected={selected_strategy} | "
            f"test MAE={result['selected_test_MAE']:.3f} | "
            f"XGBoost MAE={result['xgboost_test_MAE']:.3f} | "
            f"persistence MAE={result['persistence_test_MAE']:.3f}"
        )

    metrics = {
        "model": "Pune direct multi-horizon XGBoost",
        "data_source": str(DATA),
        "stations": sorted(df["station_name"].dropna().unique().tolist()),
        "feature_columns": feature_cols,
        "train_target_cutoff_utc": train_cut.isoformat(),
        "validation_target_cutoff_utc": val_cut.isoformat(),
        "horizon_metrics": results,
        "notes": [
            "Evaluation uses chronological splits based on target timestamps.",
            "Persistence baseline predicts the origin-time PM2.5 value.",
            "Predictions are not guaranteed to be accurate; inspect each horizon.",
            "Weather and pollutant values after the forecast origin are not used."
        ],
    }

    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    pd.DataFrame(results).to_csv(OUT / "horizon_metrics.csv", index=False)
    joblib.dump(feature_cols, OUT / "feature_columns.joblib")
    joblib.dump(df["station_name"].dropna().unique().tolist(), OUT / "stations.joblib")

    print("\n===== 24-HOUR TRAINING COMPLETE =====")
    print(f"Separate artifacts: {OUT}")
    print(f"Metrics: {OUT / 'horizon_metrics.csv'}")

if __name__ == "__main__":
    main()
