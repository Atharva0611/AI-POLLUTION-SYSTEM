from uuid import uuid4
from datetime import date

from backend.agents.orchestrator import run_pipeline
from backend.services.historical_weather import get_historical_weather
import re


def process_chat(message: str, session_id: str | None = None) -> dict:
    question = (message or "").strip()
    sid = session_id or str(uuid4())

    if not question:
        return {
            "answer": "Please enter a question.",
            "session_id": sid,
            "status": "invalid",
        }

    # Dedicated deterministic route for historical weather requests. This avoids
    # sending weather-history questions to the policy RAG fallback.
    historical_weather_query = re.search(
        r"\\b(historical|history|past|last\\s+(?:\\d+\\s+)?(?:days?|weeks?|months?)|yesterday)\\b.*"
        r"\\b(weather|temperature|humidity|rainfall|precipitation|wind|weather data)\\b"
        r"|\\b(weather|temperature|humidity|rainfall|precipitation|wind)\\b.*"
        r"\\b(historical|history|past|last\\s+(?:\\d+\\s+)?(?:days?|weeks?|months?)|yesterday)\\b",
        question,
        flags=re.IGNORECASE,
    )
    if historical_weather_query:
        try:
            location_match = re.search(
                r"\\b(?:in|for|at)\\s+([A-Za-z][A-Za-z .'-]{1,60}?)(?=\\s+(?:from|between|during|for the|over the|last|past|yesterday|on)\\b|[?.!,]|$)",
                question,
                flags=re.IGNORECASE,
            )
            location = location_match.group(1).strip() if location_match else "Pune"
            date_match = re.search(
                r"\\b(20\\d{2}-\\d{2}-\\d{2})\\b.*?\\b(20\\d{2}-\\d{2}-\\d{2})\\b",
                question,
            )
            start_date = date.fromisoformat(date_match.group(1)) if date_match else None
            end_date = date.fromisoformat(date_match.group(2)) if date_match else None
            history = get_historical_weather(location, start_date, end_date)
            rows = history["hourly"]
            temps = [r["temperature_2m"] for r in rows if r.get("temperature_2m") is not None]
            humidity = [r["relative_humidity_2m"] for r in rows if r.get("relative_humidity_2m") is not None]
            rain = [r["precipitation"] for r in rows if r.get("precipitation") is not None]
            winds = [r["wind_speed_10m"] for r in rows if r.get("wind_speed_10m") is not None]
            answer = (
                f"Historical weather summary for {history['location']['resolved']}, "
                f"{history['start_date']} to {history['end_date']} (Asia/Kolkata)\\n"
                f"Source: {history['source']}\\n"
                f"Hourly records returned: {len(rows)}\\n"
                f"Temperature range: {min(temps):.1f}–{max(temps):.1f} °C\\n" if temps else
                f"Historical weather data for {history['location']['resolved']}, "
                f"{history['start_date']} to {history['end_date']}\\nSource: {history['source']}\\n"
            )
            if humidity:
                answer += f"Relative humidity range: {min(humidity):.0f}–{max(humidity):.0f}%\\n"
            if rain:
                answer += f"Total precipitation across returned hourly records: {sum(rain):.1f} mm\\n"
            if winds:
                answer += f"Wind speed range: {min(winds):.1f}–{max(winds):.1f} km/h\\n"
            answer += (
                "\\nThis is weather reanalysis data, not measured PM2.5 or official AQI. "
                "For exact dates, ask e.g. 'Historical weather in Wagholi from 2026-10-01 to 2026-10-03'."
            )
            return {"answer": answer, "session_id": sid, "status": "ok", "intent": "historical_weather", "location": history["location"]["resolved"]}
        except Exception as exc:
            return {
                "answer": f"I couldn't retrieve historical weather for that request: {exc}",
                "session_id": sid,
                "status": "error",
                "intent": "historical_weather",
            }

    try:
        result = run_pipeline({
            "question": question,
            "session_id": sid,
        })

        answer = (
            result.get("final_answer")
            or result.get("direct_message")
            or result.get("error")
        )

        if not answer:
            answer = (
                "I couldn't generate a reliable answer. "
                "Please try rephrasing your question."
            )

        return {
            "answer": str(answer),
            "session_id": sid,
            "status": "ok" if result.get("final_answer") or result.get("direct_message") else "partial",
            "intent": result.get("intent"),
            "location": result.get("location"),
        }
    except Exception:
        # Avoid leaking API keys, internal paths, or stack traces to chat users.
        return {
            "answer": (
                "I couldn't complete that request because an internal service "
                "encountered an error. Please try again."
            ),
            "session_id": sid,
            "status": "error",
        }
