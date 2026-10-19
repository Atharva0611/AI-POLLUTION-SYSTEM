"""
ORIVA Phase 3: walk-forward station-aware residual-blend benchmark.
Experimental only; production artifacts are never modified.
"""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parent
CANDIDATE_PATH = ROOT / "backend/ml/forecasting/pune_multistation_xgboost.phase3_candidate.py"
DATA_PATH = ROOT / "data/processed/pune_cpcb_all_stations_hourly.csv"
REPORT_PATH = ROOT / "data/reports/phase3_walkforward_station_blend.json"

WEIGHT_GRID = np.round(np.arange(0.0, 0.501, 0.05), 2)
MIN_STATION_VALIDATION_ROWS = 100
MIN_TRAIN_ROWS = 1000
MIN_TEST_ROWS = 100
VALIDATION_FRACTION = 0.20
RANDOM_STATE = 42


def load_candidate():
    if not CANDIDATE_PATH.exists():
        raise FileNotFoundError(f"Candidate module not found: {CANDIDATE_PATH}")
    spec = importlib.util.spec_from_file_location("oriva_phase3_candidate", CANDIDATE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load candidate module: {CANDIDATE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_model():
    return XGBRegressor(
        n_estimators=400,
        learning_rate=0.03,
        max_depth=6,
        min_child_weight=5,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="reg:squarederror",
        eval_metric="rmse",
        random_state=RANDOM_STATE,
        tree_method="hist",
        n_jobs=4,
    )


def metrics(actual, prediction):
    return {
        "mae": float(mean_absolute_error(actual, prediction)),
        "rmse": float(np.sqrt(mean_squared_error(actual, prediction))),
        "r2": float(r2_score(actual, prediction)),
    }


def residual_prediction(model, frame, features, medians):
    x = frame[features].replace([np.inf, -np.inf], np.nan)
    x = x.fillna(medians).fillna(0)
    current = frame["pm25"].to_numpy(dtype=float)
    return np.maximum(0.0, current + model.predict(x))


def choose_station_weights(validation, current, corrected):
    actual = validation["target_pm25_next_1h"].to_numpy(dtype=float)
    station_values = validation["station_name"].astype(str).to_numpy()
    weights = {}
    details = []

    for station in sorted(set(station_values)):
        mask = station_values == station
        count = int(mask.sum())
        base = current[mask]
        candidate = corrected[mask]
        truth = actual[mask]

        if count < MIN_STATION_VALIDATION_ROWS:
            chosen = 0.0
            chosen_mae = float(mean_absolute_error(truth, base))
            reason = "fallback_to_persistence_insufficient_validation_rows"
        else:
            trials = []
            for weight in WEIGHT_GRID:
                pred = (1.0 - float(weight)) * base + float(weight) * candidate
                trials.append((float(mean_absolute_error(truth, pred)), float(weight)))
            chosen_mae, chosen = min(trials, key=lambda item: (item[0], item[1]))
            reason = "selected_using_pre_test_validation_mae"

        weights[station] = float(chosen)
        details.append({
            "station": station,
            "validation_rows": count,
            "selected_xgboost_weight": float(chosen),
            "validation_mae": float(chosen_mae),
            "reason": reason,
        })
    return weights, details


def blend(frame, current, corrected, weights):
    station_values = frame["station_name"].astype(str).to_numpy()
    row_weights = np.array([weights.get(station, 0.0) for station in station_values])
    return (1.0 - row_weights) * current + row_weights * corrected


def main():
    print("ORIVA Phase 3 walk-forward station-aware blend benchmark")
    print("Production model and artifacts will NOT be modified.")
    print("1/5 Loading candidate and data...", flush=True)

    module = load_candidate()
    raw = pd.read_csv(DATA_PATH, low_memory=False)
    data, features, stations = module.make_features(raw, training=True)
    data = data.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True, errors="coerce")
    data = data.dropna(subset=[
        "timestamp", "station_name", "pm25", "target_pm25_next_1h"
    ])
    data = data.sort_values(["timestamp", "station_name"]).reset_index(drop=True)

    times = data["timestamp"].drop_duplicates().sort_values().reset_index(drop=True)
    if len(times) < 100:
        raise RuntimeError(f"Insufficient unique timestamps: {len(times)}")

    cuts = [times.iloc[int(len(times) * p)] for p in (0.55, 0.70, 0.85)]
    windows = [
        ("Window 1", cuts[0], cuts[1]),
        ("Window 2", cuts[1], cuts[2]),
        ("Window 3", cuts[2], times.iloc[-1] + pd.Timedelta(hours=1)),
    ]

    print(
        f"Rows={len(data):,}; features={len(features)}; "
        f"stations={len(stations)}; timestamps={len(times):,}",
        flush=True,
    )
    print("2/5 Evaluating rolling windows...", flush=True)
    results = []

    for name, start, end in windows:
        # Targets are at t+1h; exclude rows whose target crosses the test boundary.
        pre = data[
            (data["timestamp"] < start)
            & (data["timestamp"] + pd.Timedelta(hours=1) <= start)
        ].copy()
        test = data[(data["timestamp"] >= start) & (data["timestamp"] < end)].copy()

        if len(pre) < MIN_TRAIN_ROWS or len(test) < MIN_TEST_ROWS:
            results.append({
                "window": name,
                "status": "SKIPPED_INSUFFICIENT_ROWS",
                "train_rows": len(pre),
                "test_rows": len(test),
            })
            print(f"{name}: SKIPPED (train={len(pre)}, test={len(test)})", flush=True)
            continue

        pre_times = pre["timestamp"].drop_duplicates().sort_values().reset_index(drop=True)
        validation_cut = pre_times.iloc[
            max(1, int(len(pre_times) * (1.0 - VALIDATION_FRACTION)))
        ]
        train_core = pre[
            (pre["timestamp"] < validation_cut)
            & (pre["timestamp"] + pd.Timedelta(hours=1) <= validation_cut)
        ].copy()
        validation = pre[pre["timestamp"] >= validation_cut].copy()

        if len(train_core) < MIN_TRAIN_ROWS or len(validation) < MIN_TEST_ROWS:
            results.append({
                "window": name,
                "status": "SKIPPED_INSUFFICIENT_INTERNAL_VALIDATION",
                "train_rows": len(pre),
                "train_core_rows": len(train_core),
                "validation_rows": len(validation),
                "test_rows": len(test),
            })
            print(f"{name}: SKIPPED (internal validation too small)", flush=True)
            continue

        # Fit on earlier data and select station weights on prior validation only.
        core_medians = (
            train_core[features].replace([np.inf, -np.inf], np.nan)
            .median(numeric_only=True).fillna(0)
        )
        model_selection = make_model()
        x_core = (
            train_core[features].replace([np.inf, -np.inf], np.nan)
            .fillna(core_medians).fillna(0)
        )
        y_core = (
            train_core["target_pm25_next_1h"].to_numpy(dtype=float)
            - train_core["pm25"].to_numpy(dtype=float)
        )
        model_selection.fit(x_core, y_core, verbose=False)

        val_current = validation["pm25"].to_numpy(dtype=float)
        val_corrected = residual_prediction(
            model_selection, validation, features, core_medians
        )
        weights, weight_details = choose_station_weights(
            validation, val_current, val_corrected
        )

        # Refit model on all eligible pre-window rows; test stays untouched.
        full_medians = (
            pre[features].replace([np.inf, -np.inf], np.nan)
            .median(numeric_only=True).fillna(0)
        )
        model_final = make_model()
        x_full = (
            pre[features].replace([np.inf, -np.inf], np.nan)
            .fillna(full_medians).fillna(0)
        )
        y_full = (
            pre["target_pm25_next_1h"].to_numpy(dtype=float)
            - pre["pm25"].to_numpy(dtype=float)
        )
        model_final.fit(x_full, y_full, verbose=False)

        current = test["pm25"].to_numpy(dtype=float)
        actual = test["target_pm25_next_1h"].to_numpy(dtype=float)
        corrected = residual_prediction(model_final, test, features, full_medians)
        station_blend = blend(test, current, corrected, weights)

        base_metrics = metrics(actual, current)
        corrected_metrics = metrics(actual, corrected)
        blend_metrics = metrics(actual, station_blend)
        passed = (
            blend_metrics["mae"] < base_metrics["mae"]
            and blend_metrics["rmse"] < base_metrics["rmse"]
        )

        results.append({
            "window": name,
            "status": "EVALUATED",
            "start": str(start),
            "end_exclusive": str(end),
            "train_rows": len(pre),
            "train_core_rows": len(train_core),
            "validation_rows": len(validation),
            "test_rows": len(test),
            "validation_cut": str(validation_cut),
            "persistence": base_metrics,
            "residual_xgboost": corrected_metrics,
            "station_aware_blend": blend_metrics,
            "gate_pass": bool(passed),
            "station_weights": weight_details,
        })
        print(
            f"{name}: persistence MAE={base_metrics['mae']:.4f}, "
            f"RMSE={base_metrics['rmse']:.4f} | "
            f"station blend MAE={blend_metrics['mae']:.4f}, "
            f"RMSE={blend_metrics['rmse']:.4f} | "
            f"gate={'PASS' if passed else 'FAIL'}",
            flush=True,
        )

    evaluated = [r for r in results if r.get("status") == "EVALUATED"]
    all_three = len(evaluated) == 3
    all_pass = all_three and all(r["gate_pass"] for r in evaluated)
    decision = "ELIGIBLE_FOR_INDEPENDENT_REVIEW" if all_pass else "NO_GO"

    report = {
        "purpose": "experimental_walk_forward_station_aware_blend",
        "production_artifacts_modified": False,
        "production_model_promoted": False,
        "promotion_rule": "Both MAE and RMSE must strictly improve over persistence in every rolling window.",
        "validation_fraction": VALIDATION_FRACTION,
        "minimum_station_validation_rows": MIN_STATION_VALIDATION_ROWS,
        "weight_grid": [float(v) for v in WEIGHT_GRID],
        "window_results": results,
        "all_three_windows_evaluated": bool(all_three),
        "decision": decision,
        "note": "A passing benchmark requires independent review; it does not automatically authorize promotion.",
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\n4/5 Report saved:", REPORT_PATH)
    print("5/5 Final decision:", decision)
    print("Production artifacts modified: False")
    print("Production model promoted: False")


if __name__ == "__main__":
    main()
