from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.agents.final_agent import intent_node

print("Backend import successful.")
print(intent_node({"question": "What is AQI?"}))
