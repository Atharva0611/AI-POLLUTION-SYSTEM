from __future__ import annotations

import math
import re
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

MODEL_PATH = (
    ROOT
    / "models"
    / "forecasting"
    / "pm25_xgboost.pkl"
)

HOTSPOT_PATH = (
    ROOT
    / "data"
    / "processed"
    / "pune_hotspot_points.csv"
)


def _num(value):
    try:
        if value is None or value == "":
            return None

        value = float(value)

        if math.isnan(value) or math.isinf(value):
            return None

        return value

    except Exception:
        return None


def _norm(value):
    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(value).lower(),
    )


def _current(environment):
    value = environment.get("current", {})
    return value if isinstance(value, dict) else {}


def _air(environment):
    current = _current(environment)

    candidates = [
        current.get("air_quality"),
        environment.get("air_quality"),
    ]

    for item in candidates:
        if isinstance(item, dict):
            return item

    return {}


def _lookup(environment, *names):
    current = _current(environment)
    air = _air(environment)

    wanted = {
        _norm(name)
        for name in names
    }

    for source in [current, air, environment]:

        if not isinstance(source, dict):
            continue

        for key, value in source.items():

            if _norm(key) not in wanted:
                continue

            number = _num(value)

            if number is not None:
                return number

    return None


def _load_model_package():
    if not MODEL_PATH.exists():
        return None

    package = joblib.load(
        MODEL_PATH
    )

    if isinstance(package, dict):
        return package

    return {
        "model": package,
        "feature_names": getattr(
            package,
            "feature_names_in_",
            None,
        ),
        "medians": {},
        "metrics": {},
    }


def _get_feature_names(model, package):
    names = package.get(
        "feature_names"
    )

    if names:
        return list(names)

    names = getattr(
        model,
        "feature_names_in_",
        None,
    )

    if names is not None:
        return list(names)

    try:
        names = (
            model
            .get_booster()
            .feature_names
        )

        if names:
            return list(names)

    except Exception:
        pass

    return None


def _feature_value(environment, feature):
    key = _norm(feature)

    if key == "pm10":
        return _lookup(
            environment,
            "pm10",
            "PM10",
        )

    if key == "no2":
        return _lookup(
            environment,
            "no2",
            "NO2",
        )

    if key == "so2":
        return _lookup(
            environment,
            "so2",
            "SO2",
        )

    if key in {"co", "comgm3"}:
        value = _lookup(
            environment,
            "co",
            "CO",
        )

        if value is not None and value > 20:
            value = value / 1000.0

        return value

    if key in {"ozone", "o3"}:
        return _lookup(
            environment,
            "o3",
            "ozone",
            "O3",
        )

    if key in {
        "temperature",
        "temperaturec",
        "tempc",
    }:
        return _lookup(
            environment,
            "temperature_c",
            "temp_c",
            "temperature",
            "temp",
        )

    if key == "humidity":
        return _lookup(
            environment,
            "humidity",
            "relative_humidity",
            "RH",
        )

    if key in {
        "windspeed",
        "windspeedms",
    }:
        value = _lookup(
            environment,
            "wind_speed_kph",
            "wind_kph",
            "wind_speed",
        )

        if value is not None:
            return value / 3.6

        return None

    if key in {
        "winddirection",
        "winddirectiondeg",
    }:
        return _lookup(
            environment,
            "wind_degree",
            "wind_direction",
            "wind_direction_deg",
        )

    if key in {
        "rainfall",
        "rainfallmm",
    }:
        return _lookup(
            environment,
            "rainfall_mm",
            "precip_mm",
            "rain",
        )

    if key == "hour":
        current = _current(
            environment
        )

        timestamp = current.get(
            "last_updated"
        )

        if timestamp:
            try:
                return float(
                    pd.to_datetime(
                        timestamp
                    ).hour
                )
            except Exception:
                pass

        return float(
            datetime.now().hour
        )

    if key == "dayofweek":
        current = _current(
            environment
        )

        timestamp = current.get(
            "last_updated"
        )

        if timestamp:
            try:
                return float(
                    pd.to_datetime(
                        timestamp
                    ).dayofweek
                )
            except Exception:
                pass

        return float(
            datetime.now().weekday()
        )

    return None


def _build_feature_row(
    environment,
    feature_names,
    medians,
):
    values = {}
    imputed = []

    for feature in feature_names:

        value = _feature_value(
            environment,
            feature,
        )

        if value is None:
            value = medians.get(
                feature
            )

            imputed.append(
                feature
            )

        if value is None:
            value = 0.0

        values[feature] = float(
            value
        )

    return pd.DataFrame(
        [values],
        columns=feature_names,
    ), imputed


def run_real_shap(environment):
    """
    Runs SHAP against the trained XGBoost PM2.5 model.
    """

    try:
        import shap
    except Exception as exc:
        return {
            "available": False,
            "status": "SHAP_NOT_INSTALLED",
            "message": str(exc),
        }

    package = _load_model_package()

    if package is None:
        return {
            "available": False,
            "status": "MODEL_NOT_FOUND",
            "message": (
                "Trained model not found at: "
                f"{MODEL_PATH}"
            ),
        }

    model = package.get("model")

    if model is None:
        return {
            "available": False,
            "status": "MODEL_EMPTY",
            "message": (
                "The XGBoost model package does not "
                "contain a model."
            ),
        }

    feature_names = _get_feature_names(
        model,
        package,
    )

    if not feature_names:
        return {
            "available": False,
            "status": "FEATURE_NAMES_MISSING",
            "message": (
                "The trained XGBoost model does not "
                "contain feature names."
            ),
        }

    X, imputed = _build_feature_row(
        environment,
        feature_names,
        package.get(
            "medians",
            {},
        ),
    )

    try:

        prediction = float(
            np.asarray(
                model.predict(X)
            ).reshape(-1)[0]
        )

        explainer = shap.TreeExplainer(
            model
        )

        raw_values = explainer.shap_values(
            X
        )

        values = np.asarray(
            raw_values
        )

        if values.ndim == 2:
            values = values[0]

        values = values.reshape(-1)

        expected_value = None

        try:
            expected_value = (
                explainer.expected_value
            )

            if isinstance(
                expected_value,
                np.ndarray,
            ):
                expected_value = (
                    expected_value.reshape(
                        -1
                    )[0]
                )

            expected_value = float(
                expected_value
            )

        except Exception:
            pass

        features = []

        for name, shap_value, feature_value in zip(
            feature_names,
            values,
            X.iloc[0].values,
        ):

            shap_value = float(
                shap_value
            )

            if shap_value > 0:
                effect = (
                    "increases PM2.5 prediction"
                )
            elif shap_value < 0:
                effect = (
                    "decreases PM2.5 prediction"
                )
            else:
                effect = "neutral"

            features.append({
                "feature": str(name),
                "value": round(
                    float(feature_value),
                    6,
                ),
                "shap_value": round(
                    shap_value,
                    6,
                ),
                "absolute_impact": round(
                    abs(shap_value),
                    6,
                ),
                "effect": effect,
            })

        features.sort(
            key=lambda x:
                x["absolute_impact"],
            reverse=True,
        )

        return {
            "available": True,
            "status": "SUCCESS",
            "method": "SHAP TreeExplainer",
            "prediction": round(
                prediction,
                4,
            ),
            "expected_value": (
                expected_value
            ),
            "feature_count": len(
                features
            ),
            "top_features": features[:10],
            "imputed_features": imputed,
            "model_path": str(
                MODEL_PATH
            ),
            "model_metrics": package.get(
                "metrics",
                {},
            ),
            "message": (
                "SHAP calculated from the trained "
                "XGBoost PM2.5 forecasting model."
            ),
        }

    except Exception as exc:

        return {
            "available": False,
            "status": "SHAP_ERROR",
            "message": str(exc),
        }


def run_hotspot(
    eps_km=5.0,
    min_samples=2,
):
    """
    DBSCAN geographic hotspot detection.
    Uses the generated Pune station dataset.
    """

    try:
        from sklearn.cluster import DBSCAN
    except Exception as exc:
        return {
            "available": False,
            "status": "SKLEARN_NOT_INSTALLED",
            "message": str(exc),
        }

    if not HOTSPOT_PATH.exists():
        return {
            "available": False,
            "status": "HOTSPOT_DATA_NOT_FOUND",
            "message": (
                "Hotspot dataset not found: "
                f"{HOTSPOT_PATH}"
            ),
        }

    try:

        df = pd.read_csv(
            HOTSPOT_PATH
        )

        required = [
            "station_name",
            "latitude",
            "longitude",
            "pm25",
        ]

        missing = [
            column
            for column in required
            if column not in df.columns
        ]

        if missing:
            return {
                "available": False,
                "status": "MISSING_COLUMNS",
                "missing_columns": missing,
            }

        for column in [
            "latitude",
            "longitude",
            "pm25",
        ]:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

        df = df.dropna(
            subset=[
                "latitude",
                "longitude",
                "pm25",
            ]
        )

        df = (
            df.groupby(
                "station_name",
                as_index=False,
            )
            .agg({
                "latitude": "mean",
                "longitude": "mean",
                "pm25": "mean",
            })
        )

        if len(df) < min_samples:
            return {
                "available": False,
                "status": "INSUFFICIENT_SPATIAL_DATA",
                "points": int(len(df)),
                "minimum_points": int(
                    min_samples
                ),
                "message": (
                    "Not enough monitoring stations "
                    "are available for DBSCAN."
                ),
            }

        coordinates = np.radians(
            df[
                [
                    "latitude",
                    "longitude",
                ]
            ].values
        )

        earth_radius_km = 6371.0088

        clusterer = DBSCAN(
            eps=(
                eps_km
                / earth_radius_km
            ),
            min_samples=min_samples,
            metric="haversine",
        )

        labels = clusterer.fit_predict(
            coordinates
        )

        df["cluster"] = labels

        clusters = []

        for cluster_id in sorted(
            set(labels)
        ):

            if cluster_id == -1:
                continue

            group = df[
                df["cluster"]
                == cluster_id
            ]

            stations = (
                group[
                    "station_name"
                ]
                .astype(str)
                .tolist()
            )

            clusters.append({
                "cluster_id": int(
                    cluster_id
                ),
                "stations": stations,
                "station_count": len(
                    stations
                ),
                "center_latitude": round(
                    float(
                        group[
                            "latitude"
                        ].mean()
                    ),
                    6,
                ),
                "center_longitude": round(
                    float(
                        group[
                            "longitude"
                        ].mean()
                    ),
                    6,
                ),
                "average_pm25": round(
                    float(
                        group[
                            "pm25"
                        ].mean()
                    ),
                    2,
                ),
                "maximum_pm25": round(
                    float(
                        group[
                            "pm25"
                        ].max()
                    ),
                    2,
                ),
            })

        clusters.sort(
            key=lambda x:
                x["average_pm25"],
            reverse=True,
        )

        return {
            "available": True,
            "status": (
                "HOTSPOTS_DETECTED"
                if clusters
                else "NO_HOTSPOT"
            ),
            "method": "DBSCAN_HAVERSINE",
            "radius_km": eps_km,
            "minimum_samples": min_samples,
            "monitoring_locations": int(
                len(df)
            ),
            "noise_locations": int(
                sum(labels == -1)
            ),
            "cluster_count": len(
                clusters
            ),
            "clusters": clusters,
            "dataset": str(
                HOTSPOT_PATH
            ),
            "message": (
                "Hotspot analysis completed "
                "using multiple monitoring locations."
            ),
        }

    except Exception as exc:

        return {
            "available": False,
            "status": "HOTSPOT_ERROR",
            "message": str(exc),
        }


def enhance_result(
    environment,
    result,
    location=None,
    model=None,
    feature_row=None,
    feature_names=None,
):
    """
    Add SHAP and hotspot analysis to the
    existing intelligence result.
    """

    if not isinstance(
        result,
        dict,
    ):
        result = {}

    result["shap"] = run_real_shap(
        environment
    )

    result["hotspot"] = run_hotspot(
        eps_km=5.0,
        min_samples=2,
    )

    result["advanced_analysis"] = {
        "shap_enabled": bool(
            result["shap"].get(
                "available",
                False,
            )
        ),
        "hotspot_enabled": bool(
            result["hotspot"].get(
                "available",
                False,
            )
        ),
    }

    return result


def format_advanced_report(result):

    lines = []

    shap = result.get(
        "shap",
        {},
    )

    lines.append("")
    lines.append(
        "SHAP ANALYSIS"
    )
    lines.append(
        "-" * 60
    )

    if shap.get(
        "available"
    ):

        lines.append(
            "Status: SUCCESS"
        )

        lines.append(
            "XGBoost PM2.5 prediction: "
            f"{shap.get('prediction')}"
        )

        metrics = shap.get(
            "model_metrics",
            {},
        )

        if metrics:
            lines.append(
                "R2: "
                f"{metrics.get('R2')}"
            )

            lines.append(
                "RMSE: "
                f"{metrics.get('RMSE')}"
            )

        lines.append("")

        for item in shap.get(
            "top_features",
            [],
        ):

            lines.append(
                f"{item['feature']} | "
                f"value={item['value']} | "
                f"SHAP={item['shap_value']:+.6f} | "
                f"{item['effect']}"
            )

    else:

        lines.append(
            "Status: "
            + str(
                shap.get(
                    "status",
                    "UNAVAILABLE",
                )
            )
        )

        lines.append(
            str(
                shap.get(
                    "message",
                    "",
                )
            )
        )

    hotspot = result.get(
        "hotspot",
        {},
    )

    lines.append("")
    lines.append(
        "HOTSPOT ANALYSIS"
    )
    lines.append(
        "-" * 60
    )

    if hotspot.get(
        "available"
    ):

        lines.append(
            "Status: SUCCESS"
        )

        lines.append(
            "Monitoring locations: "
            f"{hotspot.get('monitoring_locations')}"
        )

        lines.append(
            "Hotspot clusters: "
            f"{hotspot.get('cluster_count')}"
        )

        lines.append(
            "DBSCAN radius: "
            f"{hotspot.get('radius_km')} km"
        )

        for cluster in hotspot.get(
            "clusters",
            [],
        ):

            lines.append(
                f"Cluster {cluster['cluster_id']} | "
                f"Stations={cluster['stations']} | "
                f"Center="
                f"{cluster['center_latitude']}, "
                f"{cluster['center_longitude']} | "
                f"Average PM2.5="
                f"{cluster['average_pm25']} | "
                f"Maximum PM2.5="
                f"{cluster['maximum_pm25']}"
            )

    else:

        lines.append(
            "Status: "
            + str(
                hotspot.get(
                    "status",
                    "UNAVAILABLE",
                )
            )
        )

        lines.append(
            str(
                hotspot.get(
                    "message",
                    "",
                )
            )
        )

    return "\n".join(
        lines
    )
