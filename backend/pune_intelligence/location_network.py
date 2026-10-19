from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

CANDIDATES = [
    ROOT / "data" / "processed" / "pune_100_locations_mapped.csv",
    ROOT / "data" / "processed" / "pune_100_locations.csv",
]

def _find_col(df, names):
    normalized = {str(c).strip().lower().replace(" ", "_"): c for c in df.columns}
    for name in names:
        key = name.lower().replace(" ", "_")
        if key in normalized:
            return normalized[key]
    for c in df.columns:
        key = str(c).strip().lower().replace(" ", "_")
        if any(name.lower().replace(" ", "_") in key for name in names):
            return c
    return None

def load_locations():
    path = next((p for p in CANDIDATES if p.exists()), None)
    if path is None:
        raise FileNotFoundError(
            "Pune location master not found. Expected: "
            + " or ".join(str(p) for p in CANDIDATES)
        )
    df = pd.read_csv(path)

    name_col = _find_col(df, ["location", "location_name", "locality", "name", "place", "area"])
    lat_col = _find_col(df, ["latitude", "lat"])
    lon_col = _find_col(df, ["longitude", "lon", "lng"])
    station_col = _find_col(df, ["representative_cpcb_station", "representative_station", "cpcb_station", "station"])

    if name_col is None:
        raise ValueError(f"No locality column found. Columns: {df.columns.tolist()}")

    out = pd.DataFrame()
    out["location"] = df[name_col].astype(str).str.strip()
    out["latitude"] = pd.to_numeric(df[lat_col], errors="coerce") if lat_col else float("nan")
    out["longitude"] = pd.to_numeric(df[lon_col], errors="coerce") if lon_col else float("nan")
    out["representative_cpcb_station"] = (
        df[station_col].astype(str).str.strip() if station_col else ""
    )
    out = out[out["location"].ne("")].drop_duplicates("location").reset_index(drop=True)
    return out

def resolve_query(row):
    try:
        lat = float(row.get("latitude"))
        lon = float(row.get("longitude"))
        if pd.notna(lat) and pd.notna(lon):
            return f"{lat},{lon}"
    except Exception:
        pass
    return f"{row['location']}, Pune, Maharashtra, India"
