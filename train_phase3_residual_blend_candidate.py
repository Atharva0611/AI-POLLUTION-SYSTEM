from pathlib import Path
import importlib.util
import json
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ROOT = Path(__file__).resolve().parent
BENCHMARK_PATH = ROOT / "benchmark_phase3_walkforward_blend.py"
DATA_PATH = ROOT / "data" / "processed" / "pune_cpcb_all_stations_hourly.csv"
OUT_DIR = ROOT / "models" / "forecasting" / "phase3_residual_blend_candidate"
REPORT_PATH = ROOT / "data" / "reports" / "phase3_residual_blend_candidate.json"

def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def main():
    if not BENCHMARK_PATH.exists():
        raise FileNotFoundError(BENCHMARK_PATH)
    if not DATA_PATH.exists():
        raise FileNotFoundError(DATA_PATH)

    benchmark = load_module(BENCHMARK_PATH, "phase3_benchmark_module")
    candidate = benchmark.load_candidate()

    print("Loading historical data...", flush=True)
    raw = pd.read_csv(DATA_PATH, low_memory=False)
    data, features, stations = candidate.make_features(raw, training=True)

    data = data.copy()
    data["timestamp"] = pd.to_datetime(
        data["timestamp"], utc=True, errors="coerce"
    )
    data = data.replace([np.inf, -np.inf], np.nan)
    data = data.dropna(
        subset=["timestamp", "station_name", "pm25", "target_pm25_next_1h"]
    )
    data = data.sort_values(["timestamp", "station_name"]).reset_index(drop=True)

    times = data["timestamp"].drop_duplicates().sort_values().reset_index(drop=True)
    if len(times) < 100:
        raise RuntimeError(f"Insufficient unique timestamps: {len(times)}")

    # Reserve the latest 15% of timestamps as the final untouched holdout.
    test_start = times.iloc[int(len(times) * 0.85)]
    pre = data[
        (data["timestamp"] < test_start)
        & (data["timestamp"] + pd.Timedelta(hours=1) <= test_start)
    ].copy()
    test = data[data["timestamp"] >= test_start].copy()

    pre_times = pre["timestamp"].drop_duplicates().sort_values().reset_index(drop=True)
    if len(pre_times) < 50 or len(test) < 100:
        raise RuntimeError(
            f"Insufficient split sizes: pre={len(pre)}, test={len(test)}"
        )

    validation_cut = pre_times.iloc[int(len(pre_times) * 0.80)]
    train_core = pre[
        (pre["timestamp"] < validation_cut)
        & (pre["timestamp"] + pd.Timedelta(hours=1) <= validation_cut)
    ].copy()
    validation = pre[pre["timestamp"] >= validation_cut].copy()

    if len(train_core) < 1000 or len(validation) < 100:
        raise RuntimeError(
            f"Insufficient training/validation rows: "
            f"train_core={len(train_core)}, validation={len(validation)}"
        )

    print(
        f"Rows={len(data):,}; features={len(features)}; stations={len(stations)}",
        flush=True,
    )
    print(
        f"Train core={len(train_core):,}; validation={len(validation):,}; "
        f"pre-holdout={len(pre):,}; final holdout={len(test):,}",
        flush=True,
    )

    core_medians = (
        train_core[features]
        .replace([np.inf, -np.inf], np.nan)
        .median(numeric_only=True)
        .fillna(0)
    )
    x_core = (
        train_core[features]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(core_medians)
        .fillna(0)
    )
    y_core = (
        train_core["target_pm25_next_1h"].to_numpy(dtype=float)
        - train_core["pm25"].to_numpy(dtype=float)
    )

    selection_model = benchmark.make_model()
    selection_model.fit(x_core, y_core, verbose=False)

    validation_corrected = benchmark.residual_prediction(
        selection_model, validation, features, core_medians
    )
    weights, weight_details = benchmark.choose_station_weights(
        validation,
        validation["pm25"].to_numpy(dtype=float),
        validation_corrected,
    )

    # Refit on all eligible pre-holdout data. The final holdout remains untouched.
    full_medians = (
        pre[features]
        .replace([np.inf, -np.inf], np.nan)
        .median(numeric_only=True)
        .fillna(0)
    )
    x_full = (
        pre[features]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(full_medians)
        .fillna(0)
    )
    y_full = (
        pre["target_pm25_next_1h"].to_numpy(dtype=float)
        - pre["pm25"].to_numpy(dtype=float)
    )

    final_model = benchmark.make_model()
    final_model.fit(x_full, y_full, verbose=False)

    current = test["pm25"].to_numpy(dtype=float)
    actual = test["target_pm25_next_1h"].to_numpy(dtype=float)
    corrected = benchmark.residual_prediction(
        final_model, test, features, full_medians
    )
    blend_prediction = benchmark.blend(test, current, corrected, weights)

    def score(y, pred):
        return {
            "mae": float(mean_absolute_error(y, pred)),
            "rmse": float(np.sqrt(mean_squared_error(y, pred))),
            "r2": float(r2_score(y, pred)),
        }

    persistence_metrics = score(actual, current)
    residual_metrics = score(actual, corrected)
    blend_metrics = score(actual, blend_prediction)
    gate_pass = (
        blend_metrics["mae"] < persistence_metrics["mae"]
        and blend_metrics["rmse"] < persistence_metrics["rmse"]
    )

    # Refuse to overwrite any prior candidate artifacts.
    if OUT_DIR.exists() and any(OUT_DIR.iterdir()):
        raise RuntimeError(
            f"Candidate output directory already contains files: {OUT_DIR}. "
            "Nothing was saved; inspect or back up that directory first."
        )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    joblib.dump(final_model, OUT_DIR / "residual_model.pkl")
    joblib.dump(list(features), OUT_DIR / "features.pkl")
    joblib.dump(full_medians.to_dict(), OUT_DIR / "medians.pkl")
    joblib.dump(list(stations), OUT_DIR / "stations.pkl")
    joblib.dump({str(k): float(v) for k, v in weights.items()},
                OUT_DIR / "station_weights.pkl")

    report = {
        "purpose": "isolated_residual_station_blend_candidate",
        "production_artifacts_modified": False,
        "production_model_promoted": False,
        "candidate_artifact_dir": str(OUT_DIR),
        "data_source": str(DATA_PATH),
        "features_count": len(features),
        "stations": list(stations),
        "train_core_rows": len(train_core),
        "validation_rows": len(validation),
        "pre_holdout_rows": len(pre),
        "holdout_rows": len(test),
        "holdout_start": test_start.isoformat(),
        "persistence": persistence_metrics,
        "residual_model": residual_metrics,
        "station_aware_blend": blend_metrics,
        "holdout_gate_pass": bool(gate_pass),
        "station_weights": weight_details,
        "decision": "ELIGIBLE_FOR_REVIEW" if gate_pass else "NO_GO",
        "note": (
            "Experimental candidate only. A passing holdout is not production "
            "approval. Historical CPCB inputs and live inference compatibility "
            "still require separate verification."
        ),
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\nFINAL HOLDOUT RESULTS")
    print(json.dumps({
        "persistence": persistence_metrics,
        "residual_model": residual_metrics,
        "station_aware_blend": blend_metrics,
        "holdout_gate_pass": bool(gate_pass),
        "decision": report["decision"],
        "candidate_artifact_dir": str(OUT_DIR),
        "report": str(REPORT_PATH),
        "production_artifacts_modified": False,
        "production_model_promoted": False,
    }, indent=2), flush=True)

if __name__ == "__main__":
    main()
