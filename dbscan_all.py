import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN
from pathlib import Path

INPUT_FILE = "data/processed/pune_cpcb_combined.csv"

OUTPUT_DIR = Path("data/processed")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(INPUT_FILE)

df.columns = df.columns.str.strip().str.lower()

rename = {
    "station": "station_name",
    "stationname": "station_name",
    "pm2.5": "pm25",
    "pm2.5 (µg/m³)": "pm25",
    "lat": "latitude",
    "lon": "longitude",
    "lng": "longitude"
}

df.rename(columns=rename, inplace=True)

print("\nOriginal rows:", len(df))
print("Columns:", df.columns.tolist())

required = ["station_name", "latitude", "longitude", "pm25"]

missing = [c for c in required if c not in df.columns]

if missing:
    raise ValueError(f"Missing columns: {missing}")

for col in ["latitude", "longitude", "pm25"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

df.dropna(subset=required, inplace=True)

print("Valid rows:", len(df))
print("Unique stations:", df["station_name"].nunique())

stations = (
    df.groupby(
        ["station_name", "latitude", "longitude"],
        as_index=False
    )
    .agg(pm25=("pm25", "mean"))
)

print("\nStations entering DBSCAN:", len(stations))

print(stations[
    ["station_name", "latitude", "longitude", "pm25"]
].to_string(index=False))

if len(stations) == 0:
    raise ValueError("No valid stations found!")

coords = np.radians(
    stations[["latitude", "longitude"]].values
)

eps_km = 5
min_samples = 2

model = DBSCAN(
    eps=eps_km / 6371.0088,
    min_samples=min_samples,
    metric="haversine",
    algorithm="ball_tree"
)

stations["cluster"] = model.fit_predict(coords)

hotspots = stations[stations["cluster"] != -1].copy()
noise = stations[stations["cluster"] == -1].copy()

print("\n" + "=" * 65)
print("ALL DBSCAN HOTSPOTS")
print("=" * 65)

print("Total stations:", len(stations))
print("Number of clusters:", hotspots["cluster"].nunique())
print("Stations in clusters:", len(hotspots))
print("Noise stations:", len(noise))

if hotspots.empty:
    print("\nNo clusters found.")
    print("Check coordinates or increase eps_km.")
else:
    for cluster_id, group in hotspots.groupby("cluster"):
        print(f"\nCLUSTER {cluster_id}")
        print("-" * 50)

        for _, row in group.iterrows():
            print(
                f"{row['station_name']} | "
                f"PM2.5: {row['pm25']:.2f} ug/m3 | "
                f"Coordinates: "
                f"({row['latitude']:.4f}, "
                f"{row['longitude']:.4f})"
            )

stations.to_csv(
    OUTPUT_DIR / "dbscan_all_stations.csv",
    index=False
)

hotspots.to_csv(
    OUTPUT_DIR / "dbscan_hotspots.csv",
    index=False
)

noise.to_csv(
    OUTPUT_DIR / "dbscan_noise.csv",
    index=False
)

print("\nFiles saved successfully:")
print(OUTPUT_DIR / "dbscan_all_stations.csv")
print(OUTPUT_DIR / "dbscan_hotspots.csv")
print(OUTPUT_DIR / "dbscan_noise.csv")

