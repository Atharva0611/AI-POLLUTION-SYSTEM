from pathlib import Path
import subprocess
import sys

benchmark = Path("benchmark_phase3_residual.py")
if not benchmark.exists():
    raise SystemExit(f"Missing script: {benchmark}")

text = benchmark.read_text(encoding="utf-8")

needle = 'print("5/5 Finished. Model was not saved; production artifacts unchanged.")'
if needle not in text:
    raise SystemExit("Could not find the expected end marker; original script unchanged.")

replacement = '''
print("\\\\nPer-station MAE comparison:", flush=True)
results = []
scored = test[["station_name"]].copy()
scored["actual"] = actual
scored["baseline"] = baseline
scored["residual_prediction"] = residual_predictions

for station, group in scored.groupby("station_name"):
    results.append({
        "station": station,
        "rows": len(group),
        "persistence_MAE": mean_absolute_error(group["actual"], group["baseline"]),
        "residual_MAE": mean_absolute_error(group["actual"], group["residual_prediction"]),
    })

result_df = pd.DataFrame(results)
result_df["MAE_change"] = result_df["residual_MAE"] - result_df["persistence_MAE"]
print(result_df.sort_values("MAE_change").round(3).to_string(index=False))
print("\\\\nEvaluation finished; no model or dataset files were changed.")
'''

out = Path("evaluate_phase3_stations_fixed.py")
out.write_text(text.replace(needle, replacement), encoding="utf-8")
print(f"Created {out}; original benchmark remains unchanged.")
