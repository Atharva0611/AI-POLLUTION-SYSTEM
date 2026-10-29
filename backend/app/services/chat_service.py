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
        r"\b(historical|history|past|last\s+(?:\d+\s+)?(?:days?|weeks?|months?)|yesterday)\b.*"
        r"\b(weather|temperature|humidity|rainfall|precipitation|wind|weather data)\b"
        r"|\b(weather|temperature|humidity|rainfall|precipitation|wind)\b.*"
        r"\b(historical|history|past|last\s+(?:\d+\s+)?(?:days?|weeks?|months?)|yesterday)\b",
        question,
        flags=re.IGNORECASE,
    )
    if historical_weather_query:
        try:
            location_match = re.search(
                r"\b(?:in|for|at)\s+([A-Za-z][A-Za-z .'-]{1,60}?)(?=\s+(?:from|between|during|for the|over the|last|past|yesterday|on)\b|[?.!,]|$)",
                question,
                flags=re.IGNORECASE,
            )
            location = location_match.group(1).strip() if location_match else "Pune"
            date_match = re.search(
                r"\b(20\d{2}-\d{2}-\d{2})\b.*?\b(20\d{2}-\d{2}-\d{2})\b",
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
                f"{history['start_date']} to {history['end_date']} (Asia/Kolkata)\n"
                f"Source: {history['source']}\n"
                f"Hourly records returned: {len(rows)}\n"
                f"Temperature range: {min(temps):.1f}–{max(temps):.1f} °C\n" if temps else
                f"Historical weather data for {history['location']['resolved']}, "
                f"{history['start_date']} to {history['end_date']}\nSource: {history['source']}\n"
            )
            if humidity:
                answer += f"Relative humidity range: {min(humidity):.0f}–{max(humidity):.0f}%\n"
            if rain:
                answer += f"Total precipitation across returned hourly records: {sum(rain):.1f} mm\n"
            if winds:
                answer += f"Wind speed range: {min(winds):.1f}–{max(winds):.1f} km/h\n"
            answer += (
                "\nThis is weather reanalysis data, not measured PM2.5 or official AQI. "
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

    # Current AQI/weather questions use WeatherAPI as the single live provider.
    # Historical, forecast, ML, SHAP, DBSCAN and RAG routes remain separate.
    live_question = bool(re.search(
        r"\b(aqi|air quality|pm2\.?5|pm10|pollution|weather|temperature|humidity|"
        r"wind speed|wind direction|rainfall|precipitation|no2|so2|ozone)\b",
        question,
        flags=re.IGNORECASE,
    )) and not bool(re.search(
        r"\b(forecast|predict|prediction|historical|history|yesterday|last week|last month)\b",
        question,
        flags=re.IGNORECASE,
    ))

    if live_question:
        if re.search(r"\b(near me|around me|my location)\b", question, flags=re.IGNORECASE):
            return {
                "answer": (
                    "Please provide a city or locality for live WeatherAPI data, "
                    "for example: 'AQI in Wagholi, Pune'. I won't guess your location."
                ),
                "session_id": sid,
                "status": "partial",
                "intent": "live_aqi",
            }

        location_match = re.search(
            r"\b(?:in|of|for|at)\s+(.+?)(?=\s+(?:right now|currently|today|now)\b|[?.!,]|$)",
            question,
            flags=re.IGNORECASE,
        )
        target = (
            location_match.group(1).strip()
            if location_match
            else "Wagholi, Pune, Maharashtra, India"
        )
        target = re.sub(r"\s+", " ", target).strip(" .")

        try:
            from backend.services.india_environment import get_environment_for_user

            env = get_environment_for_user(target)
            if env.get("status") != "ok":
                detail = (env.get("policy") or [])
                detail_text = str(detail[0]) if detail else "WeatherAPI did not return current data."
                return {
                    "answer": (
                        f"WeatherAPI could not retrieve current environmental data for {target}. "
                        f"{detail_text} Check WEATHER_API_KEY in the project .env file, "
                        "your WeatherAPI quota, and the provider response. "
                        "No historical data has been substituted."
                    ),
                    "session_id": sid,
                    "status": "partial",
                    "intent": "live_aqi",
                    "location": target,
                }

            current = env.get("current") or {}
            aqi = env.get("current_aqi") or {}
            loc = env.get("location") or {}
            display = loc.get("display_name") or target
            updated = current.get("last_updated") or loc.get("local_time") or "Unavailable"

            lines = [
                f"CURRENT AIR QUALITY & WEATHER — {display}",
                f"Source: WeatherAPI current weather and air-quality data",
                f"Last updated by provider: {updated}",
                "",
                "AIR QUALITY",
                f"Indicative India-style AQI: {aqi.get('value', 'Unavailable')} "
                f"({aqi.get('category', 'Unavailable')})",
                f"Controlling pollutant: {aqi.get('controlling_pollutant', 'Unavailable')}",
                f"PM2.5: {current.get('pm2_5', 'Unavailable')} µg/m³",
                f"PM10: {current.get('pm10', 'Unavailable')} µg/m³",
                f"NO₂: {current.get('no2', 'Unavailable')} µg/m³",
                f"SO₂: {current.get('so2', 'Unavailable')} µg/m³",
                f"CO: {current.get('co', 'Unavailable')} µg/m³",
                f"O₃: {current.get('o3', 'Unavailable')} µg/m³",
                "",
                "CURRENT WEATHER",
                f"Temperature: {current.get('temperature_c', 'Unavailable')} °C",
                f"Feels like: {current.get('feels_like_c', 'Unavailable')} °C",
                f"Humidity: {current.get('humidity', 'Unavailable')}%",
                f"Wind: {current.get('wind_speed_kph', 'Unavailable')} km/h "
                f"({current.get('wind_direction', 'Unavailable')})",
                f"Rainfall: {current.get('rainfall_mm', 'Unavailable')} mm",
                f"Conditions: {current.get('condition', 'Unavailable')}",
                "",
                "AQI note: this is an indicative calculation from available pollutant "
                "concentrations, not a verified official CPCB station reading. "
                "WeatherAPI's US EPA and UK DEFRA indices are different scales.",
            ]

            has_current_data = any(
                current.get(key) is not None
                for key in (
                    "pm2_5", "pm10", "no2", "so2", "co", "o3",
                    "temperature_c", "humidity", "wind_speed_kph",
                )
            )
            if not has_current_data:
                return {
                    "answer": (
                        f"WeatherAPI responded for {display}, but did not provide usable "
                        "current weather or pollutant values. No historical data was substituted."
                    ),
                    "session_id": sid,
                    "status": "partial",
                    "intent": "live_aqi",
                    "location": display,
                }

            return {
                "answer": "\n".join(lines),
                "session_id": sid,
                "status": "ok",
                "intent": "live_aqi",
                "location": display,
            }

        except Exception:
            return {
                "answer": (
                    "WeatherAPI could not retrieve current environmental data. "
                    "Check WEATHER_API_KEY in the project .env file, your API quota, "
                    "network connectivity, and WeatherAPI provider status. "
                    "No historical reading has been substituted."
                ),
                "session_id": sid,
                "status": "partial",
                "intent": "live_aqi",
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
