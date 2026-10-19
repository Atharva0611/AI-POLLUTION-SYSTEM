import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

from backend.agents.orchestrator import run_pipeline
from backend.services.intent_router import classify_intent

queries = [
    ("WeatherAPI",     "What is the live AQI of Pune?"),
    ("RAG",            "What is the NAAQS standard for PM2.5?"),
    ("CPCB",           "Show me the CPCB station data for Pune"),
    ("DBSCAN",         "Show me the pollution hotspots in Pune"),
    ("Recommendation", "What steps should be taken to reduce pollution in Pune?"),
]

print("=" * 60)
print("INTENT CLASSIFICATION CHECK")
print("=" * 60)
for expected, q in queries:
    got = classify_intent(q)
    status = "OK" if got == expected.lower() else "MISMATCH"
    print(f"  [{status}] Expected={expected:<15} Got={got:<15}")
    print(f"         Q: {q}")

print()
print("=" * 60)
print("RUNNING ALL 5 PIPELINE BRANCHES")
print("=" * 60)

for expected, q in queries:
    state = {
        "question": q,
        "retrieved_documents": [],
        "final_answer": None,
        "error": None,
    }
    result = run_pipeline(state)
    intent = result.get("intent", "?")
    answer = result.get("final_answer", "NO ANSWER")
    print()
    print("INTENT: " + intent + "  |  " + q)
    print(answer)
    print("-" * 60)
