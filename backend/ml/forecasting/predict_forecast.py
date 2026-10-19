import os
import re
import math
import joblib
import pandas as pd
import requests

PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        ".."
    )
)

FEATURE_FILE = os.path.join(
    PROJECT_ROOT,
    "data",
    "processed",
    "pune_cpcb_features.csv"
)

LOCATIONS_FILE = os.path.join(
    PROJECT_ROOT,
    "data",
    "processed",
    "pune_100_locations.csv"
)

MODEL_FILE = os.path.join(
    PROJECT_ROOT,
    "models",
    "forecasting",
    "xgboost_pm25_forecasting.pkl"
)

FEATURE_NAMES_FILE = os.path.join(
    PROJECT_ROOT,
    "models",
    "forecasting",
    "feature_names.pkl"
)

NOMINATIM_URL = (
    "https://nominatim.openstreetmap.org/search"
)

USER_AGENT = (
    "AI-Pollution-System/1.0"
)


# ============================================================
# LOAD FILES
# ============================================================

df = pd.read_csv(
    FEATURE_FILE
)

model = joblib.load(
    MODEL_FILE
)

feature_names = joblib.load(
    FEATURE_NAMES_FILE
)

if os.path.exists(LOCATIONS_FILE):

    locations_df = pd.read_csv(
        LOCATIONS_FILE
    )

else:

    locations_df = pd.DataFrame(
        columns=[
            "location_id",
            "location_name"
        ]
    )


# ============================================================
# NORMALIZE NAME
# ============================================================

def normalize_name(
    value: str
) -> str:

    value = str(value).strip().lower()

    value = value.replace(
        "_",
        " "
    )

    value = value.replace(
        "-",
        " "
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


# ============================================================
# STATION NAME LOOKUP
# ============================================================

STATION_NAMES = (
    df["station_name"]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)

STATION_LOOKUP = {
    normalize_name(x): x
    for x in STATION_NAMES
}


# ============================================================
# 100 LOCATION LOOKUP
# ============================================================

LOCATION_NAMES = []

if "location_name" in locations_df.columns:

    LOCATION_NAMES = (
        locations_df["location_name"]
        .dropna()
        .astype(str)
        .tolist()
    )

LOCATION_LOOKUP = {
    normalize_name(x): x
    for x in LOCATION_NAMES
}


# ============================================================
# GEOCODING
# ============================================================

def geocode_location(
    location: str
):

    headers = {
        "User-Agent": USER_AGENT
    }

    queries = [
        f"{location}, Pune, Maharashtra, India",
        f"{location}, Maharashtra, India",
        f"{location}, India"
    ]

    for query in queries:

        try:

            response = requests.get(
                NOMINATIM_URL,
                params={
                    "q": query,
                    "format": "jsonv2",
                    "limit": 1,
                    "countrycodes": "in"
                },
                headers=headers,
                timeout=15
            )

            response.raise_for_status()

            results = response.json()

            if results:

                return {
                    "latitude": float(
                        results[0]["lat"]
                    ),
                    "longitude": float(
                        results[0]["lon"]
                    ),
                    "display_name": results[0].get(
                        "display_name",
                        location
                    )
                }

        except Exception:
            continue

    return None


# ============================================================
# HAVERSINE DISTANCE
# ============================================================

def haversine_km(
    lat1,
    lon1,
    lat2,
    lon2
):

    radius = 6371.0

    p1 = math.radians(
        lat1
    )

    p2 = math.radians(
        lat2
    )

    dp = math.radians(
        lat2 - lat1
    )

    dl = math.radians(
        lon2 - lon1
    )

    a = (
        math.sin(dp / 2) ** 2
        +
        math.cos(p1)
        *
        math.cos(p2)
        *
        math.sin(dl / 2) ** 2
    )

    return (
        2
        *
        radius
        *
        math.asin(
            math.sqrt(a)
        )
    )


# ============================================================
# BUILD CPCB STATION COORDINATES
# ============================================================

def get_station_coordinates():

    coordinate_columns = {
        c.lower(): c
        for c in df.columns
    }

    latitude_col = None
    longitude_col = None

    for name in [
        "latitude",
        "lat"
    ]:

        if name in coordinate_columns:

            latitude_col = coordinate_columns[
                name
            ]

            break

    for name in [
        "longitude",
        "lon",
        "lng"
    ]:

        if name in coordinate_columns:

            longitude_col = coordinate_columns[
                name
            ]

            break

    # --------------------------------------------------------
    # If dataset already has coordinates
    # --------------------------------------------------------

    if (
        latitude_col
        and longitude_col
    ):

        station_coordinates = (
            df[
                [
                    "station_name",
                    latitude_col,
                    longitude_col
                ]
            ]
            .dropna()
            .drop_duplicates(
                subset=[
                    "station_name"
                ]
            )
        )

        result = []

        for _, row in station_coordinates.iterrows():

            try:

                result.append({
                    "station_name": str(
                        row["station_name"]
                    ),

                    "latitude": float(
                        row[latitude_col]
                    ),

                    "longitude": float(
                        row[longitude_col]
                    )
                })

            except Exception:
                continue

        if result:
            return result

    # --------------------------------------------------------
    # Otherwise geocode each real CPCB station
    # --------------------------------------------------------

    cache_file = os.path.join(
        PROJECT_ROOT,
        "data",
        "processed",
        "pune_cpcb_station_coordinates.csv"
    )

    if os.path.exists(cache_file):

        cached = pd.read_csv(
            cache_file
        )

        result = []

        for _, row in cached.iterrows():

            try:

                result.append({
                    "station_name": str(
                        row["station_name"]
                    ),

                    "latitude": float(
                        row["latitude"]
                    ),

                    "longitude": float(
                        row["longitude"]
                    )
                })

            except Exception:
                continue

        if result:
            return result

    result = []

    print(
        "\nBuilding CPCB station coordinate cache..."
    )

    for station in STATION_NAMES:

        print(
            f"Resolving station: {station}"
        )

        coordinates = geocode_location(
            station
        )

        if coordinates is None:

            continue

        result.append({
            "station_name": station,
            "latitude": coordinates[
                "latitude"
            ],
            "longitude": coordinates[
                "longitude"
            ]
        })

    if result:

        pd.DataFrame(
            result
        ).to_csv(
            cache_file,
            index=False
        )

    return result


# ============================================================
# FIND NEAREST MODEL STATION
# ============================================================

def find_nearest_station(
    location
):

    coordinates = geocode_location(
        location
    )

    if coordinates is None:

        raise ValueError(
            f"Could not resolve location '{location}'."
        )

    stations = get_station_coordinates()

    if not stations:

        raise ValueError(
            "No CPCB station coordinates available."
        )

    nearest = None
    nearest_distance = float(
        "inf"
    )

    for station in stations:

        distance = haversine_km(
            coordinates["latitude"],
            coordinates["longitude"],
            station["latitude"],
            station["longitude"]
        )

        if distance < nearest_distance:

            nearest_distance = distance
            nearest = station

    if nearest is None:

        raise ValueError(
            "Could not determine nearest CPCB station."
        )

    return {
        "requested_location": location,

        "resolved_location": coordinates[
            "display_name"
        ],

        "latitude": coordinates[
            "latitude"
        ],

        "longitude": coordinates[
            "longitude"
        ],

        "model_station": nearest[
            "station_name"
        ],

        "station_latitude": nearest[
            "latitude"
        ],

        "station_longitude": nearest[
            "longitude"
        ],

        "distance_km": round(
            nearest_distance,
            3
        )
    }


# ============================================================
# RESOLVE STATION
# ============================================================

def resolve_model_station(
    location
):

    normalized = normalize_name(
        location
    )

    # --------------------------------------------------------
    # Direct real CPCB station
    # --------------------------------------------------------

    if normalized in STATION_LOOKUP:

        return {
            "requested_location": location,
            "model_station": STATION_LOOKUP[
                normalized
            ],
            "method": "direct_station_match",
            "distance_km": 0.0
        }

    # --------------------------------------------------------
    # 100-location master
    # --------------------------------------------------------

    master_location = LOCATION_LOOKUP.get(
        normalized
    )

    if master_location is None:

        # Still allow arbitrary Pune locations

        master_location = location

    # --------------------------------------------------------
    # Nearest CPCB model station
    # --------------------------------------------------------

    result = find_nearest_station(
        master_location
    )

    result["method"] = (
        "nearest_cpcb_station"
    )

    return result


# ============================================================
# GET LATEST CPCB RECORD
# ============================================================

def get_latest_record(
    station_name
):

    normalized = normalize_name(
        station_name
    )

    matching_rows = df[
        df["station_name"]
        .astype(str)
        .map(normalize_name)
        == normalized
    ].copy()

    if matching_rows.empty:

        raise ValueError(
            f"Station '{station_name}' not found "
            "in the CPCB feature dataset."
        )

    if "timestamp" in matching_rows.columns:

        matching_rows["timestamp"] = pd.to_datetime(
            matching_rows["timestamp"],
            errors="coerce"
        )

        matching_rows = matching_rows.sort_values(
            "timestamp"
        )

    return matching_rows.iloc[-1]


# ============================================================
# PREPARE FEATURES
# ============================================================

def prepare_features(
    station_name
):

    row = get_latest_record(
        station_name
    )

    data = {}

    for feature in feature_names:

        if feature in row.index:

            value = row[feature]

            try:
                data[feature] = float(
                    value
                )

            except (
                TypeError,
                ValueError
            ):

                data[feature] = 0.0

        else:

            data[feature] = 0.0

    X = pd.DataFrame(
        [data],
        columns=feature_names
    )

    return X


# ============================================================
# PREDICT SINGLE
# ============================================================

def predict_single(
    station_name
):

    X = prepare_features(
        station_name
    )

    prediction = model.predict(
        X
    )

    return float(
        prediction[0]
    )


# ============================================================
# PUBLIC FORECAST FUNCTION
# ============================================================

def get_forecast(
    location
):

    resolved = resolve_model_station(
        location
    )

    station = resolved[
        "model_station"
    ]

    prediction = predict_single(
        station
    )

    return {
        "available": True,

        "requested_location": location,

        "model_station": station,

        "mapping_method": resolved[
            "method"
        ],

        "distance_km": resolved.get(
            "distance_km"
        ),

        "predicted_pm25_next_1h": round(
            prediction,
            2
        ),

        "unit": "µg/m³",

        "model": "XGBoost",

        "note": (
            "For locations that are not direct "
            "CPCB model stations, the prediction "
            "uses the nearest available CPCB "
            "model station."
        )
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    location = input(
        "Enter Pune location: "
    ).strip()

    try:

        result = get_forecast(
            location
        )

        print(
            "\nXGBOOST FORECAST"
        )

        print(
            "=" * 60
        )

        for key, value in result.items():

            print(
                f"{key}: {value}"
            )

    except Exception as exc:

        print(
            "\nERROR:"
        )

        print(
            exc
        )
