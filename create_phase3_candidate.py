from pathlib import Path
import py_compile

source = Path("backend/ml/forecasting/pune_multistation_xgboost.py")
candidate = source.with_name("pune_multistation_xgboost.phase3_candidate.py")

if candidate.exists():
    raise SystemExit(f"Candidate already exists: {candidate}")

text = source.read_text(encoding="utf-8")
start = text.find("def make_features(")
end = text.find("\ndef train(", start)

if start < 0 or end < 0:
    raise SystemExit("Could not locate make_features() boundaries.")

new_function = '''def make_features(
    raw: pd.DataFrame,
    training: bool = True,
):
    df = normalize(raw)
    df = df.dropna(subset=["timestamp", "station_name"]).copy()
    df["station_name"] = df["station_name"].astype(str).str.strip()
    df = df[df["station_name"].ne("") & df["station_name"].str.lower().ne("nan")]
    df = df.sort_values(["station_name", "timestamp"]).reset_index(drop=True)

    if df.duplicated(["station_name", "timestamp"]).any():
        raise ValueError("Duplicate station/timestamp keys detected.")

    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["month"] = df["timestamp"].dt.month
    df["day_of_year"] = df["timestamp"].dt.dayofyear

    base = [
        "pm25", "pm10", "no2", "so2", "co", "o3", "nh3",
        "temperature", "humidity", "pressure", "wind_speed",
        "rainfall", "hour", "day_of_week", "month", "day_of_year",
    ]
    lag_columns = [
        "pm25", "pm10", "no2", "so2", "co", "o3",
        "temperature", "humidity", "wind_speed", "rainfall",
    ]
    lags = [1, 3, 6, 12, 24]
    features = list(base)

    index = pd.MultiIndex.from_frame(df[["station_name", "timestamp"]])
    pm25_lookup = pd.Series(df["pm25"].to_numpy(), index=index)

    for column in lag_columns:
        lookup = pd.Series(df[column].to_numpy(), index=index)
        for lag in lags:
            name = f"{column}_lag_{lag}"
            query = pd.MultiIndex.from_arrays([
                df["station_name"].to_numpy(),
                (df["timestamp"] - pd.Timedelta(hours=lag)).to_numpy(),
            ])
            df[name] = lookup.reindex(query).to_numpy()
            features.append(name)

    target_query = pd.MultiIndex.from_arrays([
        df["station_name"].to_numpy(),
        (df["timestamp"] + pd.Timedelta(hours=1)).to_numpy(),
    ])
    df["target_pm25_next_1h"] = pm25_lookup.reindex(target_query).to_numpy()
    df = df.replace([np.inf, -np.inf], np.nan)

    if training:
        df = df.dropna(subset=["pm25", "target_pm25_next_1h", "pm25_lag_1"])

    features = [
        name for name in features
        if name in df and df[name].notna().any()
    ]
    stations = sorted(df["station_name"].astype(str).str.strip().unique())
    dummies = pd.get_dummies(df["station_name"], prefix="station", dtype=float)
    df = pd.concat([df.reset_index(drop=True), dummies.reset_index(drop=True)], axis=1)
    features += dummies.columns.tolist()
    return df, features, stations
'''

candidate.write_text(text[:start] + new_function + text[end:], encoding="utf-8")
py_compile.compile(str(candidate), doraise=True)

print("PASS: candidate created and Python syntax is valid.")
print(f"Candidate: {candidate}")
print(f"Candidate size: {candidate.stat().st_size:,} bytes")
print("Production source and saved model were not modified.")
