import os
import pandas as pd
import numpy as np
import math
from sklearn.cluster import DBSCAN

ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)

FEATURE_FILE = os.path.join(
    ROOT, "data", "processed", "pune_cpcb_features.csv"
)

STATION_FILE = os.path.join(
    ROOT, "data", "processed", "pune_cpcb_verified_stations.csv"
)

RESULT_FILE = os.path.join(
    ROOT, "data", "processed", "pune_hotspots.csv"
)

EARTH_RADIUS_KM = 6371.0088


def normalize(value):
    return (
        str(value).strip().lower()
        .replace("_", " ")
        .replace("-", " ")
    )


def get_hotspot_clusters(
    input_data=None,
    eps_km=5.0,
    min_samples=2
):
    """
    Return station-level spatial clusters and pollution summaries.

    input_data may be a DataFrame or a list of station dictionaries.
    If omitted, the function loads the processed CPCB and station files.
    """

    if not isinstance(eps_km, (int, float)) or isinstance(eps_km, bool):
        raise ValueError("eps_km must be a positive finite number")
    if not math.isfinite(eps_km) or eps_km <= 0:
        raise ValueError("eps_km must be a positive finite number")
    if not isinstance(min_samples, int) or isinstance(min_samples, bool) or min_samples < 1:
        raise ValueError("min_samples must be a positive integer")

    if input_data is None:
        if not os.path.exists(FEATURE_FILE):
            raise FileNotFoundError(
                f"Feature file not found: {FEATURE_FILE}"
            )

        if not os.path.exists(STATION_FILE):
            raise FileNotFoundError(
                f"Station file not found: {STATION_FILE}"
            )

        df = pd.read_csv(FEATURE_FILE)
        stations = pd.read_csv(STATION_FILE)

        if "station_name" not in df.columns:
            raise ValueError(
                "station_name missing in CPCB feature file"
            )

        if "station_name" not in stations.columns:
            raise ValueError(
                "station_name missing in verified station file"
            )

        pm_candidates = [
            "pm25", "pm2_5", "pm2.5",
            "PM2.5", "PM2.5 (µg/m³)"
        ]

        pm_col = next(
            (c for c in pm_candidates if c in df.columns),
            None
        )

        if pm_col is None:
            pm_col = next(
                (c for c in df.columns if "pm2.5" in c.lower()
                 or "pm25" in c.lower()),
                None
            )

        if pm_col is None:
            raise ValueError("PM2.5 column not found")

        df["_key"] = df["station_name"].map(normalize)
        stations["_key"] = stations["station_name"].map(normalize)

        df[pm_col] = pd.to_numeric(
            df[pm_col], errors="coerce"
        )

        df = df[
            df[pm_col].notna() & (df[pm_col] >= 0)
        ].copy()

        summary = df.groupby("_key", as_index=False).agg(
            pm25_mean=(pm_col, "mean"),
            pm25_max=(pm_col, "max"),
            observations=(pm_col, "count")
        )

        required = [
            "_key", "station_name", "latitude", "longitude"
        ]

        missing = [
            c for c in required if c not in stations.columns
        ]

        if missing:
            raise ValueError(
                f"Station file missing columns: {missing}"
            )

        geo = stations[required].drop_duplicates("_key")

        data = summary.merge(
            geo, on="_key", how="inner"
        )

    else:
        if isinstance(input_data, pd.DataFrame):
            data = input_data.copy()
        else:
            data = pd.DataFrame(input_data)

        aliases = {
            "pm25": ["pm25", "pm2_5", "pm2.5", "PM2.5", "PM2.5 (?g/m?)"],
            "station_name": ["station_name", "station"],
            "latitude": ["latitude", "lat"],
            "longitude": ["longitude", "lon", "lng"]
        }

        for target, options in aliases.items():
            if target not in data.columns:
                for col in options:
                    if col in data.columns:
                        data[target] = data[col]
                        break

        required = [
            "station_name", "latitude",
            "longitude", "pm25"
        ]

        missing = [
            c for c in required if c not in data.columns
        ]

        if missing:
            raise ValueError(
                f"Input data missing columns: {missing}"
            )

        data["pm25"] = pd.to_numeric(
            data["pm25"], errors="coerce"
        )

        data["latitude"] = pd.to_numeric(
            data["latitude"], errors="coerce"
        )

        data["longitude"] = pd.to_numeric(
            data["longitude"], errors="coerce"
        )

        data = data.dropna(
            subset=[
                "pm25", "latitude", "longitude"
            ]
        ).copy()

        data = data[data["pm25"] >= 0]

        data = data.rename(
            columns={"pm25": "pm25_mean"}
        )

        if "pm25_max" not in data.columns:
            data["pm25_max"] = data["pm25_mean"]

        if "observations" not in data.columns:
            data["observations"] = 1

    for column in ("latitude", "longitude", "pm25_mean"):
        data[column] = pd.to_numeric(data[column], errors="coerce")

    data = data.dropna(
        subset=["latitude", "longitude", "pm25_mean"]
    ).copy()

    # Exclude NaN and infinite numeric values before geographic validation.
    finite_mask = np.isfinite(
        data[["latitude", "longitude", "pm25_mean"]].to_numpy(dtype=float)
    ).all(axis=1)
    data = data.loc[finite_mask].copy()

    if data.empty:
        return []

    if not data["latitude"].between(-90, 90).all():
        raise ValueError("Invalid latitude values")

    if not data["longitude"].between(-180, 180).all():
        raise ValueError("Invalid longitude values")

    # Haversine DBSCAN expects coordinates in radians.
    coordinates = np.radians(
        data[["latitude", "longitude"]].to_numpy()
    )

    model = DBSCAN(
        eps=eps_km / EARTH_RADIUS_KM,
        min_samples=min_samples,
        metric="haversine",
        algorithm="ball_tree"
    )

    data["cluster"] = model.fit_predict(coordinates)

    data["is_hotspot_cluster"] = (
        data["cluster"] != -1
    )

    data["pollution_level"] = pd.cut(
        data["pm25_mean"],
        bins=[-np.inf, 35, 60, 90, np.inf],
        labels=[
            "lower", "elevated",
            "high", "very_high"
        ]
    ).astype(str)

    # Spatial membership alone is not sufficient to call a pollution hotspot.
    # This project's existing pollution-level scale defines "high" at 60 ?g/m?.
    data["is_pollution_hotspot"] = (
        data["is_hotspot_cluster"] & (data["pm25_mean"] >= 60)
    )

    minimum = data["pm25_mean"].min()
    maximum = data["pm25_mean"].max()

    if maximum == minimum:
        data["pollution_score"] = 1.0
    else:
        data["pollution_score"] = (
            (data["pm25_mean"] - minimum)
            / (maximum - minimum)
        )

    data["hotspot_score"] = np.where(
        data["is_pollution_hotspot"],
        data["pollution_score"],
        0.0
    )

    os.makedirs(
        os.path.dirname(RESULT_FILE),
        exist_ok=True
    )

    output_columns = [
        "station_name", "latitude", "longitude",
        "pm25_mean", "pm25_max", "observations",
        "cluster", "is_hotspot_cluster", "is_pollution_hotspot",
        "pollution_level", "pollution_score",
        "hotspot_score"
    ]

    output = data[output_columns].copy()
    output.to_csv(RESULT_FILE, index=False)

    return output.to_dict(orient="records")
