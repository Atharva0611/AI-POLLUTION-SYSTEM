exec(compile(
    open("benchmark_phase3_residual.py", encoding="utf-8").read()
        .replace(
            'print("5/5 Finished. Model was not saved; production artifacts unchanged.")',
            '''
print("\\\\nPer-station MAE comparison:", flush=True)
results = []
for station, group in test.assign(
    baseline=baseline,
    residual_prediction=residual_predictions,
    actual=actual,
).groupby("station_name"):
    results.append({
        "station": station,
        "rows": len(group),
        "persistence_MAE": mean_absolute_error(group["actual"], group["baseline"]),
        "residual_MAE": mean_absolute_error(group["actual"], group["residual_prediction"]),
    })
result_df = pd.DataFrame(results)
result_df["MAE_change"] = result_df["residual_MAE"] - result_df["persistence_MAE"]
print(result_df.sort_values("MAE_change").round(3).to_string(index=False))
print("\\\\nNo model or dataset files were changed.")
'''
        ),
    "exec",
))
