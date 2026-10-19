from pathlib import Path
import re
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
RAW_ROOT = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / "pune_cpcb_all_stations_hourly.csv"

KNOWN_STATIONS = [
    "Alandi",
    "Bhosari",
    "Bhumkar Nagar",
    "Dhankawadi",
    "Hadapsar",
    "Karve Road",
    "Katraj Dairy",
    "Mhada Colony",
    "Panchawati_Pashan",
    "Revenue Colony-Shivajinagar",
    "SPPU",
    "Transport Nagar-Nigdi",
]

ALIASES = {
    "timestamp": [
        "timestamp","datetime","date_time","date","time",
        "Timestamp","Date","Date_Time"
    ],
    "station_name": [
        "station_name","station","stationname","site",
        "location","monitoring_station"
    ],
    "pm25": [
        "pm25","pm2.5","pm2_5","PM2.5",
        "PM2.5 (µg/m³)","PM2.5 (ug/m3)"
    ],
    "pm10": [
        "pm10","PM10","PM10 (µg/m³)","PM10 (ug/m3)"
    ],
    "no2": [
        "no2","NO2","NO2 (µg/m³)","NO2 (ug/m3)"
    ],
    "so2": [
        "so2","SO2","SO2 (µg/m³)","SO2 (ug/m3)"
    ],
    "co": [
        "co","CO","CO (mg/m³)","CO (ug/m3)"
    ],
    "o3": [
        "o3","O3","O3 (µg/m³)","O3 (ug/m3)"
    ],
    "nh3": [
        "nh3","NH3","NH3 (µg/m³)","NH3 (ug/m3)"
    ],
    "temperature": [
        "temperature","temp","AT","AT (°C)",
        "temperature_c","temp_c"
    ],
    "humidity": [
        "humidity","RH","RH (%)","relative_humidity"
    ],
    "pressure": [
        "pressure","BP","BP (mmHg)","pressure_mb","pressure_hpa"
    ],
    "wind_speed": [
        "wind_speed","WS","WS (m/s)","wind_kph","wind_mps"
    ],
    "wind_direction": [
        "wind_direction","WD","WD (deg)"
    ],
    "rainfall": [
        "rainfall","RF","RF (mm)","precip_mm"
    ],
}


def norm(x):
    return (
        str(x).strip().lower()
        .replace(" ", "_")
        .replace(".", "")
        .replace("-", "_")
        .replace("/", "_")
    )


def find_col(df, aliases):
    lookup = {norm(c): c for c in df.columns}

    for a in aliases:
        if norm(a) in lookup:
            return lookup[norm(a)]

    for c in df.columns:
        nc = norm(c)
        for a in aliases:
            na = norm(a)
            if na in nc or nc in na:
                return c

    return None


def station_from_filename(path):
    filename = re.sub(r"[_-]+", " ", path.stem.lower())

    for station in KNOWN_STATIONS:
        target = re.sub(r"[_-]+", " ", station.lower())

        if target in filename:
            return station

    return None


files = [
    p for p in RAW_ROOT.rglob("*.csv")
    if "processed" not in str(p).lower()
    and ".venv" not in str(p).lower()
    and p.name.lower() != "punepollution.csv.csv"
]

print(f"Raw CSV files discovered: {len(files)}")

frames = []
accepted = []

for path in files:
    try:
        sample = pd.read_csv(
            path,
            nrows=5,
            low_memory=False,
        )
    except Exception as exc:
        print(f"[SKIP] {path.name}: {exc}")
        continue

    timestamp_col = find_col(
        sample,
        ALIASES["timestamp"],
    )

    pm25_col = find_col(
        sample,
        ALIASES["pm25"],
    )

    if timestamp_col is None or pm25_col is None:
        continue

    station_col = find_col(
        sample,
        ALIASES["station_name"],
    )

    station_from_file = station_from_filename(path)

    try:
        df = pd.read_csv(
            path,
            low_memory=False,
        )
    except Exception as exc:
        print(f"[SKIP] {path.name}: {exc}")
        continue

    timestamp_col = find_col(
        df,
        ALIASES["timestamp"],
    )

    pm25_col = find_col(
        df,
        ALIASES["pm25"],
    )

    if timestamp_col is None or pm25_col is None:
        continue

    out = pd.DataFrame()

    out["timestamp"] = pd.to_datetime(
        df[timestamp_col],
        errors="coerce",
    )

    if station_col and station_col in df.columns:
        out["station_name"] = (
            df[station_col]
            .astype(str)
            .str.strip()
        )
    elif station_from_file:
        out["station_name"] = station_from_file
    else:
        continue

    for target in [
        "pm25",
        "pm10",
        "no2",
        "so2",
        "co",
        "o3",
        "nh3",
        "temperature",
        "humidity",
        "pressure",
        "wind_speed",
        "wind_direction",
        "rainfall",
    ]:

        col = find_col(
            df,
            ALIASES[target],
        )

        if col:
            out[target] = pd.to_numeric(
                df[col],
                errors="coerce",
            )
        else:
            out[target] = np.nan

    out = out.dropna(
        subset=[
            "timestamp",
            "station_name",
            "pm25",
        ]
    )

    out["station_name"] = (
        out["station_name"]
        .astype(str)
        .str.strip()
    )

    # Normalize known station spellings.
    def normalize_station(value):
        v = value.lower().strip()

        for station in KNOWN_STATIONS:
            if v == station.lower():
                return station

        for station in KNOWN_STATIONS:
            a = re.sub(r"[_-]+", " ", v)
            b = re.sub(r"[_-]+", " ", station.lower())

            if a == b:
                return station

        return value

    out["station_name"] = (
        out["station_name"]
        .map(normalize_station)
    )

    if out.empty:
        continue

    frames.append(out)

    accepted.append(
        (
            path,
            len(out),
            sorted(
                out["station_name"]
                .dropna()
                .unique()
                .tolist()
            ),
        )
    )

    print(
        f"[ACCEPT] {path.name}: "
        f"{len(out):,} rows -> "
        f"{sorted(out['station_name'].unique().tolist())}"
    )


if not frames:
    raise RuntimeError(
        "No usable raw CPCB files were found. "
        "The original multi-station raw CSVs are required."
    )


combined = pd.concat(
    frames,
    ignore_index=True,
)

combined["timestamp"] = pd.to_datetime(
    combined["timestamp"],
    errors="coerce",
)

combined = combined.dropna(
    subset=[
        "timestamp",
        "station_name",
        "pm25",
    ]
)

# Hourly aggregation.
numeric_columns = [
    c for c in combined.columns
    if c not in {
        "timestamp",
        "station_name",
    }
]

combined = (
    combined
    .set_index("timestamp")
    .groupby("station_name")[numeric_columns]
    .resample("1h")
    .mean()
    .reset_index()
)

combined = combined.sort_values(
    [
        "station_name",
        "timestamp",
    ]
).reset_index(drop=True)

# Remove impossible negative pollutant values.
for col in [
    "pm25",
    "pm10",
    "no2",
    "so2",
    "co",
    "o3",
    "nh3",
]:
    if col in combined:
        combined.loc[
            combined[col] < 0,
            col,
        ] = np.nan

OUT.parent.mkdir(
    parents=True,
    exist_ok=True,
)

combined.to_csv(
    OUT,
    index=False,
)

stations = sorted(
    combined["station_name"]
    .dropna()
    .unique()
    .tolist()
)

print()
print("=" * 70)
print("PUNE ALL-STATION DATASET CREATED")
print("=" * 70)
print(f"Rows       : {len(combined):,}")
print(f"Stations   : {len(stations)}")
print()
print("Stations found:")
for station in stations:
    print(f"  - {station}")

print()
print(f"Output:")
print(OUT)

if len(stations) < 6:
    raise RuntimeError(
        f"Only {len(stations)} stations were recovered. "
        "More original Pune CPCB station files are required."
    )
