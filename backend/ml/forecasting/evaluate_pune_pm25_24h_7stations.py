from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "processed" / "pune_cpcb_all_stations_hourly.csv"
ARTIFACTS = ROOT / "models" / "forecasting" / "pune_pm25_24h_candidate"
OUT = ROOT / "models" / "forecasting" / "pune_pm25_24h_candidate" / "seven_station_diagnostic"
LAGS = [1, 2, 3, 6, 12, 24, 48, 72]

ELIGIBLE_STATIONS = [
    "Bhumkar Nagar, Pune - IITM",
    "Katraj Dairy, Pune - MPCB",
    "Mhada Colony, Pune - IITM",
    "Panchawati_Pashan, Pune - IITM",
    "Revenue Colony-Shivajinagar, Pune - IITM",
    "Savitribai Phule Pune University, Pune - MPCB",
    "Transport Nagar-Nigdi, Pune - IITM",
]


def main():
    for path in [DATA, ARTIFACTS / "feature_columns.joblib"]:
        if not path.exists():
            raise FileNotFoundError(path)

    df = pd.read_csv(DATA, low_memory=False)
    required = {"station_name", "timestamp", "pm25"}
    if not required.issubset(df.columns):
        raise ValueError(f"Missing columns: {required - set(df.columns)}")

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df["station_name"] = df["station_name"].astype("string").str.strip()

    for col in df.columns:
        if col not in ("station_name", "timestamp"):
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["station_name", "timestamp"])
    df = df.sort_values(["station_name", "timestamp"]).reset_index(drop=True)

    if df.duplicated(["station_name", "timestamp"]).any():
        raise ValueError("Duplicate station/timestamp rows detected.")

    # Build the same lag features as the training script.
    feature_cols = joblib.load(ARTIFACTS / "feature_columns.joblib")
    base_cols = [
        c for c in [
            "pm25", "pm10", "no2", "so2", "co", "o3", "nh3",
            "temperature", "humidity", "pressure", "wind_speed",
            "wind_direction", "rainfall",
        ] if c in df.columns
    ]

    grouped = df.groupby("station_name", sort=False)
    for col in base_cols:
        for lag in LAGS:
            name = f"{col}_lag_{lag}h"
            df[name] = grouped[col].shift(lag)

    # Recreate the training script's station dummy columns.
    dummies = pd.get_dummies(df["station_name"], prefix="station", dtype=float)
    df = pd.concat([df, dummies], axis=1)

    for col in feature_cols:
        if col not in df.columns:
            df[col] = 0.0

    times = np.sort(df["timestamp"].unique())
    train_cut = pd.Timestamp(times[int(len(times) * 0.70)])
    val_cut = pd.Timestamp(times[int(len(times) * 0.85)])

    index = pd.MultiIndex.from_frame(df[["station_name", "timestamp"]])
    pm25_lookup = pd.Series(df["pm25"].to_numpy(), index=index)

    df = df[df["station_name"].isin(ELIGIBLE_STATIONS)].copy()
    results = []
    prediction_frames = []

    for horizon in range(1, 25):
        model_path = ARTIFACTS / f"xgb_pm25_h{horizon:02d}.joblib"
        if not model_path.exists():
            raise FileNotFoundError(model_path)

        model = joblib.load(model_path)
        future_index = pd.MultiIndex.from_arrays([
            df["station_name"].to_numpy(),
            (df["timestamp"] + pd.Timedelta(hours=horizon)).to_numpy(),
        ])
        target = pm25_lookup.reindex(future_index).to_numpy()

        valid = np.isfinite(target) & df["pm25"].notna().to_numpy()
        data = df.loc[valid].copy()
        data["target_pm25"] = target[valid]
        data["target_timestamp"] = (
            data["timestamp"] + pd.Timedelta(hours=horizon)
        )

        target_dt = data["target_timestamp"]
        data["hour"] = target_dt.dt.hour
        data["day_of_week"] = target_dt.dt.dayofweek
        data["month"] = target_dt.dt.month
        data["day_of_year"] = target_dt.dt.dayofyear

        test = data[data["target_timestamp"] > val_cut].copy()
        if test.empty:
            continue

        # Apply training-only imputation medians saved by the trainer.
        # The original trainer currently does not save medians per horizon.
        # Reconstructing them from the full dataset would leak information,
        # so stop rather than silently evaluate with an invalid substitute.
        medians_path = ARTIFACTS / f"medians_h{horizon:02d}.joblib"
        if not medians_path.exists():
            raise FileNotFoundError(
                f"Missing training medians: {medians_path}. "
                "A leakage-safe diagnostic needs the exact train-only medians."
            )

        medians = joblib.load(medians_path)
        X_test = (
            test[feature_cols]
            .replace([np.inf, -np.inf], np.nan)
            .fillna(medians)
            .fillna(0)
        )

        pred = model.predict(X_test)
        actual = test["target_pm25"].to_numpy()
        baseline = test["pm25"].to_numpy()

        prediction_frames.append(pd.DataFrame({
            "station_name": test["station_name"].to_numpy(),
            "origin_timestamp": test["timestamp"].to_numpy(),
            "target_timestamp": test["target_timestamp"].to_numpy(),
            "horizon_hours": horizon,
            "actual_pm25": actual,
            "xgboost_prediction": pred,
            "persistence_prediction": baseline,
        }))

        results.append({
            "horizon_hours": horizon,
            "test_rows": len(test),
            "stations": test["station_name"].nunique(),
            "xgboost_MAE": mean_absolute_error(actual, pred),
            "persistence_MAE": mean_absolute_error(actual, baseline),
            "xgboost_RMSE": np.sqrt(mean_squared_error(actual, pred)),
            "persistence_RMSE": np.sqrt(mean_squared_error(actual, baseline)),
            "xgboost_R2": r2_score(actual, pred),
        })

    OUT.mkdir(parents=True, exist_ok=True)
    result_df = pd.DataFrame(results)
    result_df.to_csv(OUT / "horizon_metrics.csv", index=False)

    if prediction_frames:
        predictions_df = pd.concat(prediction_frames, ignore_index=True)
        predictions_df.to_csv(OUT / "test_predictions.csv", index=False)

        predictions_df["abs_xgb_error"] = (
            predictions_df["actual_pm25"] - predictions_df["xgboost_prediction"]
        ).abs()
        predictions_df["abs_persistence_error"] = (
            predictions_df["actual_pm25"] - predictions_df["persistence_prediction"]
        ).abs()

        station_metrics = predictions_df.groupby("station_name").agg(
            test_rows=("actual_pm25", "size"),
            xgboost_MAE=("abs_xgb_error", "mean"),
            persistence_MAE=("abs_persistence_error", "mean"),
        ).reset_index()
        station_metrics.to_csv(OUT / "station_metrics.csv", index=False)

        horizon_metrics = predictions_df.groupby("horizon_hours").agg(
            test_rows=("actual_pm25", "size"),
            xgboost_MAE=("abs_xgb_error", "mean"),
            persistence_MAE=("abs_persistence_error", "mean"),
        ).reset_index()
        horizon_metrics.to_csv(OUT / "horizon_metrics_rebuilt.csv", index=False)
        print("\n=== STATION-LEVEL TEST MAE ===")
        print(station_metrics.round(3).to_string(index=False))
    print(result_df.round(3).to_string(index=False))
    print(f"\nSaved diagnostic to: {OUT}")


if __name__ == "__main__":
    main()

