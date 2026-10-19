from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

ROOT = Path.cwd()
DATA = ROOT / "data" / "processed"
OUT = DATA / "dbscan_candidate"
OUT.mkdir(parents=True, exist_ok=True)

INPUT = DATA / "pune_cpcb_all_stations_hourly.csv"
COORDS = DATA / "pune_cpcb_verified_stations.csv"

# Explicit mappings only: these names were verified in the coordinate audit.
NAME_MAP = {
    "Alandi, Pune - IITM": "Alandi",
    "Bhosari, Pune - IITM": "Bhosari",
    "Hadapsar, Pune - IITM": "Hadapsar",
    "Karve Road, Pune - MPCB": "Karve Road",
    "Mhada Colony, Pune - IITM": "Mhada Colony",
    "Panchawati_Pashan, Pune - IITM": "Panchawati_Pashan",
}

if not INPUT.exists() or INPUT.stat().st_size == 0:
    raise FileNotFoundError(f"Hourly input is missing or empty: {INPUT}")
if not COORDS.exists() or COORDS.stat().st_size == 0:
    raise FileNotFoundError(f"Coordinate file is missing or empty: {COORDS}")

df = pd.read_csv(INPUT)
coords = pd.read_csv(COORDS)

required_data = {"station_name", "pm25"}
required_coords = {"station_name", "latitude", "longitude"}

if not required_data.issubset(df.columns):
    raise ValueError(f"Hourly data missing: {sorted(required_data - set(df.columns))}")
if not required_coords.issubset(coords.columns):
    raise ValueError(f"Coordinate file missing: {sorted(required_coords - set(coords.columns))}")

df["pm25"] = pd.to_numeric(df["pm25"], errors="coerce")
df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=["station_name", "pm25"])
df = df[df["pm25"] >= 0].copy()

df["coordinate_name"] = df["station_name"].map(NAME_MAP)

unmatched = sorted(df.loc[df["coordinate_name"].isna(), "station_name"].unique())
(DATA / "dbscan_candidate").mkdir(parents=True, exist_ok=True)
pd.DataFrame({"unmatched_station_name": unmatched}).to_csv(
    OUT / "unmatched_stations.csv", index=False
)

coords["latitude"] = pd.to_numeric(coords["latitude"], errors="coerce")
coords["longitude"] = pd.to_numeric(coords["longitude"], errors="coerce")
coords = coords.dropna(subset=["station_name", "latitude", "longitude"])
coords = coords[
    coords["latitude"].between(-90, 90)
    & coords["longitude"].between(-180, 180)
].copy()

if coords["station_name"].duplicated().any():
    raise ValueError("Coordinate table has duplicate station names; refusing ambiguous join.")

summary = (
    df.dropna(subset=["coordinate_name"])
      .groupby(["station_name", "coordinate_name"], as_index=False)
      .agg(
          pm25=("pm25", "mean"),
          pm25_max=("pm25", "max"),
          observations=("pm25", "count"),
      )
)

summary = summary.merge(
    coords.rename(columns={"station_name": "coordinate_name"}),
    on="coordinate_name",
    how="left",
    validate="many_to_one",
    indicator=True,
)

missing_coords = summary.loc[summary["_merge"] != "both", "station_name"].tolist()
if missing_coords:
    raise ValueError(f"Explicitly mapped stations missing coordinates: {missing_coords}")

summary = summary.drop(columns="_merge")

if summary.empty:
    raise ValueError("No stations have both PM2.5 data and verified coordinates.")

coordinates = np.radians(summary[["latitude", "longitude"]].to_numpy(dtype=float))
model = DBSCAN(
    eps=5.0 / 6371.0088,
    min_samples=2,
    metric="haversine",
    algorithm="ball_tree",
)
summary["cluster"] = model.fit_predict(coordinates)
summary["cluster_status"] = np.where(summary["cluster"] == -1, "isolated", "clustered")

summary.to_csv(OUT / "matched_station_clusters.csv", index=False)

print("DBSCAN candidate complete.")
print("Input hourly rows:", len(df))
print("Stations with verified coordinates:", len(summary))
print("Unmatched stations:", len(unmatched))
print("Clustered stations:", int((summary["cluster"] != -1).sum()))
print("Isolated stations:", int((summary["cluster"] == -1).sum()))
print("\nUnmatched station names:")
for name in unmatched:
    print(" -", name)
print("\nCandidate outputs:")
print(OUT / "matched_station_clusters.csv")
print(OUT / "unmatched_stations.csv")
print("\nNOTE: Results cover only stations with verified coordinate matches.")
