from pathlib import Path

source = Path("benchmark_phase3_residual.py")
text = source.read_text(encoding="utf-8")

start = text.index('print("4/5 Evaluating on identical test rows..."')
end = text.index('print("5/5 Finished.', start)

replacement = '''
print("4/5 Selecting blend using validation only...", flush=True)

# Validation predictions: choose the weight without looking at test outcomes.
val_delta = model.predict(X_val)
val_residual = np.maximum(0.0, validation["pm25"].to_numpy() + val_delta)
val_baseline = validation["pm25"].to_numpy()
val_actual = y_val.to_numpy()

weights = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
scores = []
for weight in weights:
    blended = (1.0 - weight) * val_baseline + weight * val_residual
    scores.append((mean_absolute_error(val_actual, blended), weight))

best_mae, best_weight = min(scores)
print(f"Selected residual weight={best_weight:.1f}; validation MAE={best_mae:.4f}", flush=True)

print("5/5 Evaluating selected blend on test set...", flush=True)
test_delta = model.predict(X_test)
test_residual = np.maximum(0.0, test["pm25"].to_numpy() + test_delta)
test_baseline = test["pm25"].to_numpy()
test_actual = y_test.to_numpy()
test_blend = (1.0 - best_weight) * test_baseline + best_weight * test_residual

def report(name, predicted):
    print(
        f"{name}: MAE={mean_absolute_error(test_actual, predicted):.4f}; "
        f"RMSE={np.sqrt(mean_squared_error(test_actual, predicted)):.4f}; "
        f"R2={r2_score(test_actual, predicted):.4f}"
    )

report("Persistence baseline", test_baseline)
report("Selected validation blend", test_blend)
print("No model or dataset files were saved or changed.")
'''

out = Path("benchmark_phase3_blend.py")
out.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
print(f"Created {out}; original benchmark unchanged.")
