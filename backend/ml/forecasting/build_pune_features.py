from pathlib import Path
import argparse
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = ROOT / "data" / "processed" / "pune_cpcb_cleaned_hourly.csv"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "pune_cpcb_features.rebuilt.csv"
CURRENT_OUTPUT = ROOT / "data" / "processed" / "pune_cpcb_features.csv"

BASE_COLUMNS = [
    "station_name", "timestamp", "pm25", "pm10", "no2", "so2", "co",
    "ozone", "temperature", "humidity", "wind_speed", "wind_direction",
    "rainfall",
]

def build_features(source: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in ("station_name", "timestamp", "pm25") if c not in source.columns]
    if missing:
        raise ValueError(f"Input is missing required columns: {missing}")

    df = source.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["station_name", "timestamp"])
    df = df.sort_values(["station_name", "timestamp"]).reset_index(drop=True)

    for col in df.columns:
        if col not in ("station_name", "timestamp"):
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["hour"] = df["timestamp"].dt.hour
    df["day"] = df["timestamp"].dt.day
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["month"] = df["timestamp"].dt.month
    df["week_of_year"] = df["timestamp"].dt.isocalendar().week.astype(int)
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["day_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
    df["day_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)

    station_groups = df.groupby("station_name", sort=False)
    for lag in [1, 2, 3, 6, 12, 24, 48, 72]:
        df[f"pm25_lag_{lag}h"] = station_groups["pm25"].shift(lag)

    for col in ["pm10", "no2", "so2", "co", "ozone"]:
        if col in df.columns:
            df[f"{col}_lag_1h"] = df.groupby("station_name", sort=False)[col].shift(1)

    previous_pm25 = df.groupby("station_name", sort=False)["pm25"].shift(1)
    for window in [3, 6, 12, 24]:
        df[f"pm25_rolling_mean_{window}h"] = (
            previous_pm25.groupby(df["station_name"], sort=False)
            .transform(lambda s: s.rolling(window).mean())
        )

    for window in [6, 24]:
        df[f"pm25_rolling_max_{window}h"] = (
            previous_pm25.groupby(df["station_name"], sort=False)
            .transform(lambda s: s.rolling(window).max())
        )

    for lag in [1, 3, 24]:
        df[f"pm25_change_{lag}h"] = (
            df.groupby("station_name", sort=False)["pm25"].diff(lag)
        )

    if "wind_direction" in df.columns:
        df["wind_direction_sin"] = np.sin(np.deg2rad(df["wind_direction"]))
        df["wind_direction_cos"] = np.cos(np.deg2rad(df["wind_direction"]))

    if "pm10" in df.columns:
        df["pm25_pm10_ratio"] = df["pm25"] / df["pm10"].replace(0, np.nan)
    if "no2" in df.columns:
        df["pm25_no2_ratio"] = df["pm25"] / df["no2"].replace(0, np.nan)

    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna(subset=["pm25"]).reset_index(drop=True)
    df = df.dropna(subset=["pm25_lag_72h"]).reset_index(drop=True)
    return df

def main():
    parser = argparse.ArgumentParser(description="Rebuild Pune CPCB feature dataset safely.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--compare", type=Path, default=CURRENT_OUTPUT)
    args = parser.parse_args()

    if not args.input.is_file():
        raise FileNotFoundError(f"Input dataset not found: {args.input}")

    print(f"Input: {args.input}")
    raw = pd.read_csv(args.input, low_memory=False)
    print(f"Input rows: {len(raw):,}; stations: {raw['station_name'].nunique() if 'station_name' in raw else 'unknown'}")

    result = build_features(raw)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False)

    print(f"\nCandidate saved: {args.output}")
    print(f"Candidate shape: {result.shape}")
    print(f"Candidate stations: {result['station_name'].nunique()}")
    print(f"Timestamp range: {result['timestamp'].min()} -> {result['timestamp'].max()}")
    print(f"Duplicate station/timestamp keys: {result.duplicated(['station_name', 'timestamp']).sum()}")
    print(f"Missing PM2.5: {result['pm25'].isna().sum()}")

    if args.compare.is_file():
        old = pd.read_csv(args.compare, low_memory=False)
        old_cols, new_cols = list(old.columns), list(result.columns)
        print("\n=== COMPARISON WITH CURRENT DATASET ===")
        print(f"Current shape: {old.shape}")
        print(f"Candidate shape: {result.shape}")
        print(f"Same column order: {old_cols == new_cols}")
        if old_cols != new_cols:
            print("Columns only in current:", [c for c in old_cols if c not in new_cols])
            print("Columns only in candidate:", [c for c in new_cols if c not in old_cols])
        print("Current station counts:")
        print(old["station_name"].value_counts().sort_index().to_string())
        print("Candidate station counts:")
        print(result["station_name"].value_counts().sort_index().to_string())
    else:
        print(f"\nComparison file not found: {args.compare}")

if __name__ == "__main__":
    main()
