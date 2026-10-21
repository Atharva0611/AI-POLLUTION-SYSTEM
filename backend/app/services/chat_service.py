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

    # Route explicit current AQI / pollution / weather questions to source-aware data.
    live_question = bool(re.search(
        r"\\b(aqi|air quality|pm2\\.?5|pm10|pollution|current weather|live weather|temperature|humidity|wind speed)\\b",
        question, flags=re.IGNORECASE
    )) and not bool(re.search(r"\\b(forecast|predict|prediction|historical|history|yesterday|last week|last month)\\b", question, flags=re.IGNORECASE))
    if live_question:
        if re.search(r"\\b(near me|around me|my location)\\b", question, flags=re.IGNORECASE):
            return {
                "answer": "I need a town, city, or locality to look up live provider data. Please ask e.g. 'AQI of Wagholi, Pune'. I will not guess your coordinates.",
                "session_id": sid, "status": "partial", "intent": "live_aqi"
            }
        location_match = re.search(
            r"\\b(?:in|of|for|at)\\s+(.+?)(?=\\s+(?:right now|currently|today|now)\\b|[?.!,]|$)",
            question, flags=re.IGNORECASE
        )
        target = location_match.group(1).strip() if location_match else "Wagholi, Pune, Maharashtra, India"
        target = re.sub(r"\\s+", " ", target).strip(" .")
        try:
            from backend.api.routes.live_environment import current_environment
            snapshot = current_environment(target)
            providers = snapshot.get("providers") or {}
            pollution = providers.get("openweather_air_pollution") or {}
            weather = providers.get("openweather_weather") or {}
            openaq = providers.get("openaq") or {}
            resolved = (snapshot.get("location") or {}).get("resolved_name") or target
            lines = [f"Current environmental data for {resolved}:"]
            if pollution.get("status") == "ok":
                lines.append(f"OpenWeather Air Quality Index: {pollution.get('aqi', 'unavailable')} on OpenWeather's 1–5 scale (not CPCB AQI).")
                for key, label in (("pm2_5", "PM2.5"), ("pm10", "PM10"), ("no2", "NO2"), ("so2", "SO2"), ("o3", "O3"), ("co", "CO")):
                    value = (pollution.get("components") or {}).get(key)
                    if value is not None:
                        lines.append(f"OpenWeather {label}: {value} µg/m³.")
                lines.append(f"OpenWeather pollution observed at: {pollution.get('observed_at') or 'timestamp unavailable'} (UTC); freshness: {pollution.get('freshness', 'unknown')}.")
            else:
                lines.append(f"OpenWeather current pollution is unavailable: {pollution.get('error') or pollution.get('status', 'unknown status')}.")
            if weather.get("status") == "ok":
                lines.append(f"OpenWeather weather: {weather.get('temperature_c', '—')} °C, humidity {weather.get('humidity_percent', '—')}%, wind {weather.get('wind_speed_m_s', '—')} m/s.")
                lines.append(f"Weather observed at: {weather.get('observed_at') or 'timestamp unavailable'} (UTC); freshness: {weather.get('freshness', 'unknown')}.")
            else:
                lines.append(f"OpenWeather current weather is unavailable: {weather.get('error') or weather.get('status', 'unknown status')}.")
            fresh = openaq.get("live_measurements") or []
            if fresh:
                lines.append(f"OpenAQ has {len(fresh)} sensor measurement(s) within the configured live window:")
                for item in fresh[:8]:
                    lines.append(f"OpenAQ {item.get('pollutant', 'pollutant')} at {item.get('station', 'station')}: {item.get('value')} {item.get('unit') or ''}, observed {item.get('observed_at_utc') or 'timestamp unavailable'} (UTC).")
            else:
                lines.append(f"OpenAQ current sensor readings unavailable: {openaq.get('error') or 'no measurements meet the live-data threshold'}.")
            lines.append("Provider values are kept separate. No historical value is substituted and OpenWeather AQI is not CPCB AQI.")
            available = pollution.get("status") == "ok" or weather.get("status") == "ok" or bool(fresh)
            return {
                "answer": "\\n".join(lines), "session_id": sid,
                "status": "ok" if available else "partial",
                "intent": "live_aqi", "location": resolved
            }
        except Exception:
            return {
                "answer": "Current environmental data could not be retrieved. Check the OpenAQ and OpenWeather provider status on the Live Air Quality page; no historical reading has been substituted.",
                "session_id": sid, "status": "partial", "intent": "live_aqi"
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
