import csv
import random
from pathlib import Path
from collections import Counter
from backend.agents.final_agent import intent_node

random.seed(42)

cities = [
    "Pune", "Delhi", "Mumbai", "Nashik", "Nagpur",
    "Bengaluru", "Chennai", "Hyderabad", "Kolkata", "Jaipur",
    "Lucknow", "Ahmedabad", "Indore", "Bhopal", "Thane",
    "Noida", "Gurugram", "Patna", "Surat", "Kanpur",
]

concepts = [
    "AQI", "PM2.5", "PM10", "ozone", "nitrogen dioxide",
    "sulfur dioxide", "carbon monoxide", "smog", "air pollution",
    "WeatherAPI", "DBSCAN", "SHAP", "machine learning",
    "air quality monitoring", "pollution forecasting",
    "particulate matter", "temperature inversion", "greenhouse gases",
    "vehicle emissions", "industrial pollution", "air quality sensors",
]

conceptual_templates = [
    "What is {concept}?",
    "Can you explain {concept}?",
    "Explain {concept} in simple words.",
    "Define {concept}.",
    "Tell me about {concept}.",
    "What does {concept} mean?",
    "How does {concept} work?",
    "Give me a beginner explanation of {concept}.",
    "I want to understand {concept}.",
    "Describe {concept} for a student.",
]

weather_templates = [
    "What is the current AQI in {city}?",
    "Check the weather in {city}.",
    "Show me the live AQI for {city}.",
    "What is the air quality index in {city} right now?",
    "Tell me the current pollution level in {city}.",
    "Get the temperature in {city}.",
    "Will it rain in {city}?",
    "What is the humidity in {city} today?",
    "Check wind speed in {city}.",
    "How polluted is the air in {city} currently?",
    "Show current PM2.5 in {city}.",
    "Give me today's weather for {city}.",
]

dbscan_templates = [
    "Find pollution hotspots in {city}.",
    "Run DBSCAN hotspot analysis for {city}.",
    "Identify polluted zones in {city}.",
    "Show pollution clusters for {city}.",
    "Which areas are the most polluted in {city}?",
    "Perform spatial analysis of pollution in {city}.",
    "Detect high pollution zones in {city}.",
    "Find hotspots and clusters in {city}.",
]

forecast_templates = [
    "Forecast PM2.5 in {city} for tomorrow.",
    "Predict pollution levels in {city}.",
    "Give me an air quality forecast for {city}.",
    "Predict PM2.5 for the next 24 hours in {city}.",
    "Run XGBoost prediction for {city}.",
    "Show the pollution forecast for {city} tomorrow.",
    "Explain SHAP feature importance for the pollution model in {city}.",
    "Why did the model prediction change in {city}?",
]

policy_topics = [
    "CPCB standards", "NA AQS standards", "emission standards",
    "air pollution policy", "air act regulations", "legal limits",
    "construction dust guidelines", "open burning regulations",
    "road dust control policy", "environmental compliance",
]

policy_templates = [
    "Explain {topic}.",
    "What are the {topic}?",
    "Give me information about {topic}.",
    "What rules apply to {topic}?",
    "How can I understand {topic}?",
    "Summarize the requirements for {topic}.",
]

conversation_questions = [
    "Hello", "Hi", "Hey", "Good morning", "Good afternoon",
    "Good evening", "Thanks", "Thank you", "Who are you?",
    "What can you do?", "Help", "Tell me a joke",
    "Write a poem about trees", "What is the capital of France?",
    "How are you?", "Goodbye",
]

questions = {}

def add(template_list, values, expected, key):
    for template in template_list:
        for value in values:
            q = template.format(**{key: value})
            questions[q] = expected

add(conceptual_templates, concepts, "conceptual", "concept")
add(weather_templates, cities, "weather", "city")
add(dbscan_templates, cities, "dbscan", "city")
add(forecast_templates, cities, "forecast_shap", "city")
add(policy_templates, policy_topics, "rag", "topic")

for q in conversation_questions:
    questions[q] = "conversation"

# Add more varied phrasing while keeping the intended action explicit.
prefixes = [
    "Please ", "Can you ", "I need you to ", "For my project, ",
    "Help me to ", "I would like to ",
]
actions = [
    ("check the current AQI in {city}", "weather"),
    ("check weather in {city}", "weather"),
    ("find pollution hotspots in {city}", "dbscan"),
    ("predict PM2.5 in {city} tomorrow", "forecast_shap"),
    ("explain DBSCAN", "conceptual"),
    ("explain AQI", "conceptual"),
    ("summarize CPCB standards", "rag"),
]

for prefix in prefixes:
    for action, expected in actions:
        for city in cities:
            if "{city}" in action:
                q = prefix + action.format(city=city)
            else:
                q = prefix + action
            questions[q] = expected

# Add time and wording variants.
times = ["today", "tomorrow", "right now", "for the next 24 hours", "currently"]
for city in cities:
    for time in times:
        questions[f"Check the current AQI in {city} {time}."] = "weather"
        questions[f"Predict PM2.5 in {city} {time}."] = "forecast_shap"
        questions[f"Find pollution hotspots in {city} {time}."] = "dbscan"

# Deterministically expand additional natural-language variations.
verbs = ["explain", "describe", "define", "help me understand", "teach me about"]
for concept in concepts:
    for verb in verbs:
        questions[f"{verb.capitalize()} {concept}."] = "conceptual"

rows = []
for question, expected in questions.items():
    try:
        actual = intent_node({"question": question}).get("route", "missing")
        error = ""
    except Exception as exc:
        actual = "ERROR"
        error = repr(exc)

    rows.append({
        "question": question,
        "expected_route": expected,
        "actual_route": actual,
        "passed": actual == expected,
        "error": error,
    })

out = Path("tests/oriva_routing_benchmark.csv")
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

passed = sum(row["passed"] for row in rows)
total = len(rows)
counts = Counter(row["expected_route"] for row in rows)
failures = [row for row in rows if not row["passed"]]

print("\n========== ORIVA ROUTING BENCHMARK ==========")
print(f"Questions tested: {total}")
print(f"Passed:           {passed}")
print(f"Failed:           {total - passed}")
print(f"Accuracy:         {passed / total * 100:.2f}%")
print("\nExpected-route distribution:")
for route, count in sorted(counts.items()):
    print(f"  {route:16} {count}")

print(f"\nCSV report saved to: {out.resolve()}")

if failures:
    print("\nFirst 40 routing failures:")
    for row in failures[:40]:
        print(
            f"- {row['question']!r} | expected={row['expected_route']} "
            f"| actual={row['actual_route']}"
        )
else:
    print("\nAll generated questions passed.")
