from __future__ import annotations

import argparse
import json
import pickle
import re
from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

MODEL_PATHS = [
    ROOT / "models" / "forecasting" / "pune_multistation_xgboost.pkl",
    ROOT / "models" / "forecasting" / "xgboost_pm25_forecasting.pkl",
]

FEATURE_PATHS = [
    ROOT / "models" / "forecasting" / "pune_multistation_features.pkl",
    ROOT / "models" / "forecasting" / "feature_names.pkl",
]

MEDIAN_PATHS = [
    ROOT / "models" / "forecasting" / "pune_multistation_medians.pkl",
]

DATA_PATHS = [
    ROOT / "data" / "processed" / "pune_cpcb_all_stations_hourly.csv",
    ROOT / "data" / "processed" / "pune_cpcb_cleaned_hourly.csv",
]

OUT_DIR = ROOT / "data" / "reports" / "shap"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# HELPERS
# ============================================================

def norm(x):
    return re.sub(
        r"_+",
        "_",
        re.sub(
            r"[^a-zA-Z0-9]+",
            "_",
            str(x).strip().lower()
        )
    ).strip("_")


def load_pickle(path):
    with open(path, "rb") as f:
        return pickle.load(f)


def find_file(paths, name):
    for p in paths:
        if p.exists():
            return p

    raise FileNotFoundError(
        f"\n{name} not found.\nChecked:\n" +
        "\n".join(str(p) for p in paths)
    )


# ============================================================
# LOAD MODEL
# ============================================================

model_path = find_file(
    MODEL_PATHS,
    "Pune XGBoost model"
)

model_obj = load_pickle(model_path)

if isinstance(model_obj, dict):
    for key in [
        "model",
        "xgb_model",
        "estimator",
        "regressor"
    ]:
        if key in model_obj:
            model_obj = model_obj[key]
            break

MODEL = model_obj

if not hasattr(MODEL, "predict"):
    raise TypeError(
        f"Loaded object from {model_path} does not have predict()."
    )

print("\nModel:")
print(model_path)


# ============================================================
# LOAD FEATURE NAMES
# ============================================================

FEATURE_PATH = None
FEATURES = None

for p in FEATURE_PATHS:
    if p.exists():
        FEATURE_PATH = p
        obj = load_pickle(p)

        if isinstance(obj, dict):
            for key in [
                "feature_names",
                "features",
                "columns"
            ]:
                if key in obj:
                    obj = obj[key]
                    break

        if isinstance(
            obj,
            (list, tuple, np.ndarray, pd.Index)
        ):
            FEATURES = [str(x) for x in obj]
            break


if FEATURES is None:

    if hasattr(MODEL, "feature_names_in_"):
        FEATURES = [
            str(x)
            for x in MODEL.feature_names_in_
        ]

    else:

        try:
            booster = MODEL.get_booster()

            if booster.feature_names:
                FEATURES = [
                    str(x)
                    for x in booster.feature_names
                ]

        except Exception:
            pass


if FEATURES is None:
    raise RuntimeError(
        "\nCould not determine XGBoost feature names."
    )


print("\nFeature count:", len(FEATURES))


# ============================================================
# LOAD DATA
# ============================================================

DATA_PATH = find_file(
    DATA_PATHS,
    "Pune historical dataset"
)

df = pd.read_csv(DATA_PATH)

print("\nDataset:")
print(DATA_PATH)
print("Rows:", len(df))
print("Columns:", len(df.columns))


# ============================================================
# FIND TIMESTAMP
# ============================================================

COLUMN_MAP = {
    norm(c): c
    for c in df.columns
}

timestamp_col = None

for c in [
    "timestamp",
    "datetime",
    "date_time",
    "date",
    "time"
]:

    if c in COLUMN_MAP:
        timestamp_col = COLUMN_MAP[c]
        break


if timestamp_col is None:
    raise RuntimeError(
        "Timestamp column was not found."
    )


df["_timestamp"] = pd.to_datetime(
    df[timestamp_col],
    errors="coerce"
)


# ============================================================
# FIND STATION
# ============================================================

station_col = None

for c in [
    "station_name",
    "station",
    "site",
    "location"
]:

    if c in COLUMN_MAP:
        station_col = COLUMN_MAP[c]
        break


if station_col is None:

    df["_station"] = "Pune"

else:

    df["_station"] = (
        df[station_col]
        .astype(str)
        .str.strip()
    )


df = df.dropna(
    subset=["_timestamp"]
).copy()

df = df.sort_values(
    ["_station", "_timestamp"]
).reset_index(
    drop=True
)


# ============================================================
# CLEAN NUMERIC DATA
# ============================================================

for col in df.columns:

    if col not in [
        "_timestamp",
        "_station",
        timestamp_col,
        station_col
    ]:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )


# ============================================================
# LOAD TRAINING MEDIANS
# ============================================================

MEDIANS = {}

for p in MEDIAN_PATHS:

    if p.exists():

        obj = load_pickle(p)

        if isinstance(obj, dict):

            for k, v in obj.items():

                try:
                    MEDIANS[norm(k)] = float(v)
                except Exception:
                    pass

        break


# ============================================================
# BUILD FEATURES
# ============================================================

def resolve_raw_column(base):

    b = norm(base)

    for c in df.columns:

        if norm(c) == b:
            return c

    aliases = {

        "pm25": [
            "pm25",
            "pm2_5",
            "pm2.5"
        ],

        "pm10": [
            "pm10"
        ],

        "no2": [
            "no2"
        ],

        "so2": [
            "so2"
        ],

        "co": [
            "co"
        ],

        "o3": [
            "o3"
        ],

        "nh3": [
            "nh3"
        ],

        "temperature": [
            "temperature",
            "temp"
        ],

        "humidity": [
            "humidity",
            "rh"
        ],

        "wind_speed": [
            "wind_speed",
            "ws"
        ],

        "rainfall": [
            "rainfall",
            "rain",
            "rf"
        ],

        "pressure": [
            "pressure",
            "bp"
        ]
    }

    for key, candidates in aliases.items():

        if b == key:

            for candidate in candidates:

                for c in df.columns:

                    if norm(c) == norm(candidate):
                        return c

    return None


def station_dummy(feature):

    f = norm(feature)

    prefixes = [
        "station_",
        "station_name_",
        "site_",
        "site_name_"
    ]

    for prefix in prefixes:

        if f.startswith(prefix):

            encoded = f[len(prefix):]

            return encoded

    return None


def make_feature(feature):

    f = norm(feature)

    values = pd.Series(
        np.nan,
        index=df.index,
        dtype=float
    )


    # --------------------------------------------------------
    # EXACT COLUMN
    # --------------------------------------------------------

    exact = resolve_raw_column(f)

    if exact is not None:

        return pd.to_numeric(
            df[exact],
            errors="coerce"
        )


    # --------------------------------------------------------
    # STATION ONE-HOT
    # --------------------------------------------------------

    encoded_station = station_dummy(f)

    if encoded_station is not None:

        return (
            df["_station"]
            .map(
                lambda x:
                1.0
                if norm(x) == encoded_station
                else 0.0
            )
        )


    # --------------------------------------------------------
    # TIME FEATURES
    # --------------------------------------------------------

    if f in [
        "hour",
        "hour_of_day"
    ]:

        return df["_timestamp"].dt.hour.astype(float)


    if f in [
        "day_of_week",
        "dow"
    ]:

        return df["_timestamp"].dt.dayofweek.astype(float)


    if f == "month":

        return df["_timestamp"].dt.month.astype(float)


    if f == "day_of_year":

        return df["_timestamp"].dt.dayofyear.astype(float)


    if f in [
        "is_weekend",
        "weekend"
    ]:

        return (
            df["_timestamp"]
            .dt.dayofweek
            .ge(5)
            .astype(float)
        )


    if f in [
        "hour_sin",
        "sin_hour"
    ]:

        return np.sin(
            2 * np.pi *
            df["_timestamp"].dt.hour / 24
        )


    if f in [
        "hour_cos",
        "cos_hour"
    ]:

        return np.cos(
            2 * np.pi *
            df["_timestamp"].dt.hour / 24
        )


    if f in [
        "dow_sin",
        "sin_dow"
    ]:

        return np.sin(
            2 * np.pi *
            df["_timestamp"].dt.dayofweek / 7
        )


    if f in [
        "dow_cos",
        "cos_dow"
    ]:

        return np.cos(
            2 * np.pi *
            df["_timestamp"].dt.dayofweek / 7
        )


    # --------------------------------------------------------
    # LAG FEATURES
    # --------------------------------------------------------

    lag_match = re.match(
        r"(.+)_lag_?(\d+)h?$",
        f
    )

    if lag_match is None:

        lag_match = re.match(
            r"(.+)_l(\d+)$",
            f
        )


    if lag_match is not None:

        base = lag_match.group(1)
        lag = int(lag_match.group(2))

        raw_col = resolve_raw_column(base)

        if raw_col is None:
            return values

        result = pd.Series(
            np.nan,
            index=df.index,
            dtype=float
        )

        grouped = (
            df.groupby("_station")
        )

        result = grouped[raw_col].shift(lag)

        return pd.to_numeric(
            result,
            errors="coerce"
        )


    # --------------------------------------------------------
    # ROLLING FEATURES
    # --------------------------------------------------------

    roll_match = re.match(
        r"(.+)_rolling_?(\d+)$",
        f
    )

    if roll_match is not None:

        base = roll_match.group(1)
        window = int(roll_match.group(2))

        raw_col = resolve_raw_column(base)

        if raw_col is None:
            return values

        return (
            df.groupby("_station")[raw_col]
            .transform(
                lambda s:
                s.rolling(
                    window,
                    min_periods=1
                ).mean()
            )
        )


    # --------------------------------------------------------
    # UNKNOWN
    # --------------------------------------------------------

    return values


# ============================================================
# GENERATE FEATURE MATRIX
# ============================================================

print("\nBuilding SHAP feature matrix...")

X = pd.DataFrame(
    index=df.index
)

missing_features = []

for feature in FEATURES:

    X[feature] = make_feature(feature)

    if X[feature].isna().all():

        missing_features.append(feature)


if missing_features:

    print("\nFeatures not directly reconstructed:")
    for f in missing_features:
        print(" -", f)


# ============================================================
# NUMERIC CLEANUP
# ============================================================

X = X.replace(
    [np.inf, -np.inf],
    np.nan
)


# ============================================================
# MEDIAN IMPUTATION
# ============================================================

for col in X.columns:

    if X[col].isna().any():

        key = norm(col)

        if key in MEDIANS:

            X[col] = X[col].fillna(
                MEDIANS[key]
            )

        else:

            median = X[col].median()

            if pd.notna(median):

                X[col] = X[col].fillna(
                    median
                )


# ============================================================
# VALID ROWS
# ============================================================

valid = X.notna().all(axis=1)

X = X.loc[valid].copy()

META = df.loc[
    valid,
    [
        "_timestamp",
        "_station"
    ]
].copy()


if X.empty:

    raise RuntimeError(
        "\nNo valid feature rows could be built.\n"
        "The SHAP matrix does not match the saved model feature schema."
    )


# ============================================================
# ALIGN EXACT ORDER
# ============================================================

X = X[FEATURES]

X = X.astype(float)


print("\nFinal SHAP matrix:")
print("Rows:", len(X))
print("Features:", len(X.columns))


# ============================================================
# LOAD SHAP
# ============================================================

import shap

print("\nCreating SHAP TreeExplainer...")

try:

    EXPLAINER = shap.TreeExplainer(
        MODEL
    )

except Exception as e:

    print(
        "TreeExplainer fallback:",
        e
    )

    EXPLAINER = shap.Explainer(
        MODEL,
        X
    )


# ============================================================
# SAMPLE DATA FOR SHAP
# ============================================================

MAX_ROWS = 1000

if len(X) > MAX_ROWS:

    sample_idx = np.linspace(
        0,
        len(X) - 1,
        MAX_ROWS,
        dtype=int
    )

    X_SHAP = X.iloc[
        sample_idx
    ].copy()

    META_SHAP = META.iloc[
        sample_idx
    ].copy()

else:

    X_SHAP = X.copy()
    META_SHAP = META.copy()


# ============================================================
# CALCULATE SHAP
# ============================================================

print(
    f"\nCalculating SHAP for {len(X_SHAP)} rows..."
)

SHAP_RAW = EXPLAINER.shap_values(
    X_SHAP
)


if isinstance(
    SHAP_RAW,
    list
):

    SHAP_VALUES = np.asarray(
        SHAP_RAW[0]
    )

else:

    SHAP_VALUES = np.asarray(
        SHAP_RAW
    )


if SHAP_VALUES.ndim == 3:

    SHAP_VALUES = SHAP_VALUES[:, :, 0]


if SHAP_VALUES.ndim != 2:

    raise RuntimeError(
        f"Unexpected SHAP shape: {SHAP_VALUES.shape}"
    )


# ============================================================
# PREDICTIONS
# ============================================================

PRED = np.asarray(
    MODEL.predict(
        X_SHAP
    )
).reshape(-1)


# ============================================================
# EXPECTED VALUE
# ============================================================

expected = EXPLAINER.expected_value

expected = float(
    np.asarray(
        expected
    ).reshape(-1)[0]
)


# ============================================================
# GLOBAL SHAP IMPORTANCE
# ============================================================

GLOBAL = pd.DataFrame({

    "feature": FEATURES,

    "mean_abs_shap":
        np.mean(
            np.abs(
                SHAP_VALUES
            ),
            axis=0
        ),

    "mean_shap":
        np.mean(
            SHAP_VALUES,
            axis=0
        )

})


GLOBAL = GLOBAL.sort_values(
    "mean_abs_shap",
    ascending=False
).reset_index(
    drop=True
)


GLOBAL["importance_percent"] = (
    GLOBAL["mean_abs_shap"]
    /
    GLOBAL["mean_abs_shap"].sum()
    * 100
)


# ============================================================
# LOCAL EXPLANATION
# ============================================================

latest_idx = len(
    X_SHAP
) - 1


LOCAL = pd.DataFrame({

    "feature": FEATURES,

    "feature_value":
        X_SHAP.iloc[
            latest_idx
        ].values,

    "shap_value":
        SHAP_VALUES[
            latest_idx
        ],

})


LOCAL["absolute_shap"] = (
    LOCAL["shap_value"]
    .abs()
)


LOCAL["direction"] = np.where(
    LOCAL["shap_value"] > 0,
    "INCREASES_PREDICTION",
    np.where(
        LOCAL["shap_value"] < 0,
        "DECREASES_PREDICTION",
        "NEUTRAL"
    )
)


LOCAL = LOCAL.sort_values(
    "absolute_shap",
    ascending=False
).reset_index(
    drop=True
)


# ============================================================
# ADDITIVITY CHECK
# ============================================================

local_shap_sum = (
    expected
    +
    SHAP_VALUES[
        latest_idx
    ].sum()
)

prediction = float(
    PRED[
        latest_idx
    ]
)

additivity_error = abs(
    prediction
    -
    local_shap_sum
)

additivity_ok = (
    additivity_error
    <=
    max(
        1e-4,
        abs(prediction) * 1e-4
    )
)


# ============================================================
# STATION INFO
# ============================================================

latest_station = str(
    META_SHAP.iloc[
        latest_idx
    ]["_station"]
)

latest_timestamp = (
    META_SHAP.iloc[
        latest_idx
    ]["_timestamp"]
)

if pd.notna(
    latest_timestamp
):

    latest_timestamp = (
        latest_timestamp.isoformat()
    )

else:

    latest_timestamp = None


# ============================================================
# SAVE CSV
# ============================================================

GLOBAL_PATH = (
    OUT_DIR /
    "shap_global_importance.csv"
)

LOCAL_PATH = (
    OUT_DIR /
    f"shap_local_{norm(latest_station)}.csv"
)

GLOBAL.to_csv(
    GLOBAL_PATH,
    index=False
)

LOCAL.to_csv(
    LOCAL_PATH,
    index=False
)


# ============================================================
# SAVE JSON REPORT
# ============================================================

REPORT = {

    "available": True,

    "method":
        "SHAP TreeExplainer",

    "model":
        str(model_path),

    "feature_file":
        str(FEATURE_PATH)
        if FEATURE_PATH
        else None,

    "data":
        str(DATA_PATH),

    "station":
        latest_station,

    "timestamp":
        latest_timestamp,

    "predicted_next_hour_pm25":
        prediction,

    "expected_value":
        expected,

    "reconstructed_prediction":
        local_shap_sum,

    "additivity_error":
        additivity_error,

    "additivity_check":
        additivity_ok,

    "rows_explained":
        len(X_SHAP),

    "feature_count":
        len(FEATURES),

    "top_global_features": [

        {

            "feature":
                str(row["feature"]),

            "mean_abs_shap":
                float(
                    row["mean_abs_shap"]
                ),

            "mean_shap":
                float(
                    row["mean_shap"]
                ),

            "importance_percent":
                float(
                    row[
                        "importance_percent"
                    ]
                )

        }

        for _, row
        in GLOBAL.head(15).iterrows()

    ],

    "top_local_factors": [

        {

            "feature":
                str(row["feature"]),

            "value":
                float(
                    row[
                        "feature_value"
                    ]
                ),

            "shap":
                float(
                    row["shap_value"]
                ),

            "direction":
                str(
                    row["direction"]
                )

        }

        for _, row
        in LOCAL.head(15).iterrows()

    ],

    "note":
        "SHAP explains the XGBoost prediction. "
        "SHAP values are not causal source apportionment."

}


REPORT_PATH = (
    OUT_DIR /
    "shap_report.json"
)

with open(
    REPORT_PATH,
    "w",
    encoding="utf-8"
) as f:

    json.dump(REPORT, f, indent=2, ensure_ascii=False, default=lambda o: o.item() if hasattr(o, "item") else str(o))


# ============================================================
# PLOTS
# ============================================================

import matplotlib

matplotlib.use(
    "Agg"
)

import matplotlib.pyplot as plt


# ------------------------------------------------------------
# BAR PLOT
# ------------------------------------------------------------

TOP = GLOBAL.head(15).sort_values(
    "mean_abs_shap"
)

plt.figure(
    figsize=(10, 7)
)

plt.barh(
    TOP["feature"],
    TOP["mean_abs_shap"]
)

plt.xlabel(
    "Mean |SHAP value|"
)

plt.ylabel(
    "Feature"
)

plt.title(
    "Pune XGBoost SHAP Feature Importance"
)

plt.tight_layout()

plt.savefig(
    OUT_DIR /
    "shap_summary_bar.png",
    dpi=180,
    bbox_inches="tight"
)

plt.close()


# ------------------------------------------------------------
# BEESWARM
# ------------------------------------------------------------

try:

    plt.figure()

    shap.summary_plot(
        SHAP_VALUES,
        X_SHAP,
        feature_names=FEATURES,
        max_display=15,
        show=False
    )

    plt.tight_layout()

    plt.savefig(
        OUT_DIR /
        "shap_summary_beeswarm.png",
        dpi=180,
        bbox_inches="tight"
    )

    plt.close()

except Exception as e:

    print(
        "\nBeeswarm plot warning:",
        e
    )


# ============================================================
# TERMINAL RESULT
# ============================================================

print("\n")
print("=" * 70)
print("SHAP EXPLAINABILITY COMPLETE")
print("=" * 70)

print(
    "\nStation:",
    latest_station
)

print(
    "Timestamp:",
    latest_timestamp
)

print(
    "Predicted next-hour PM2.5:",
    round(
        prediction,
        4
    )
)

print(
    "\nAdditivity check:"
)

print(
    "Expected value:",
    round(
        expected,
        6
    )
)

print(
    "Reconstructed:",
    round(
        local_shap_sum,
        6
    )
)

print(
    "Error:",
    round(
        additivity_error,
        10
    )
)

print(
    "PASS:",
    additivity_ok
)


print(
    "\nTOP SHAP FACTORS:"
)

for i, row in LOCAL.head(10).iterrows():

    print(
        f"{i+1:2d}. "
        f"{row['feature']} | "
        f"value={row['feature_value']:.4f} | "
        f"SHAP={row['shap_value']:+.4f} | "
        f"{row['direction']}"
    )


print(
    "\nGLOBAL FEATURE IMPORTANCE:"
)

for i, row in GLOBAL.head(10).iterrows():

    print(
        f"{i+1:2d}. "
        f"{row['feature']} | "
        f"{row['importance_percent']:.2f}%"
    )


print(
    "\nFILES CREATED:"
)

print(
    GLOBAL_PATH
)

print(
    LOCAL_PATH
)

print(
    REPORT_PATH
)

print(
    OUT_DIR /
    "shap_summary_bar.png"
)

print(
    OUT_DIR /
    "shap_summary_beeswarm.png"
)

print(
    "\nSHAP STATUS: 100% COMPLETE"
)


