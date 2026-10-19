from pathlib import Path

source = Path("backend/ml/forecasting/pune_multistation_xgboost.py")
candidate = source.with_name("pune_multistation_xgboost.phase3_candidate.py")

text = source.read_text(encoding="utf-8")
start = text.find("def make_features(")
end = text.find("\ndef train(", start)

if start < 0 or end < 0:
    raise SystemExit("Could not locate make_features() boundaries.")

print("Source loaded successfully.")
print(f"Source size: {len(text):,} characters")
print(f"Feature function: characters {start:,} to {end:,}")
print("No files changed.")
