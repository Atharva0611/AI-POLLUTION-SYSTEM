from pathlib import Path
p = Path("benchmark_phase3_candidate.py")
text = p.read_text(encoding="utf-8")

start = text.index("print(\"3/5 Training temporary XGBoost model in memory...\"")
end = text.index("print(\"5/5 Finished.", start)

replacement = '''print("3/5 Training residual XGBoost in memory...", flush=True)

# Learn the next-hour change instead of the full PM2.5 concentration.
residual_train = y_train - train["pm25"]
residual_val = y_val - validation["pm25"]

model = XGBRegressor(
    n_estimators=400,
    learning_rate=0.03,
    max_depth=6,
    min_child_weight=5,
    subsample=0.8,
    colsample_bytree=0.8,
    objective="reg:squarederror",
    random_state=42,
    tree_method="hist",
    n_jobs=4,
)
model.fit(
    X_train,
    residual_train,
    eval_set=[(X_val, residual_val)],
    verbose=False,
)

print("4/5 Evaluating on identical test rows...", flush=True)
delta = model.predict(X_test)
residual_predictions = np.maximum(0.0, test["pm25"].to_numpy() + delta)
baseline = test["pm25"].to_numpy()
actual = y_test.to_numpy()

def report(name, predicted):
    print(
        f"{name}: MAE={mean_absolute_error(actual, predicted):.4f}; "
        f"RMSE={np.sqrt(mean_squared_error(actual, predicted)):.4f}; "
        f"R2={r2_score(actual, predicted):.4f}"
    )

report("Persistence baseline", baseline)
report("Residual XGBoost candidate", residual_predictions)

'''

out = Path("benchmark_phase3_residual.py")
out.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
print(f"Created {out}; original benchmark script unchanged.")
