from backend.services.environment_service import (
    get_environment_report,
    format_environment_report
)

from backend.services.forecast_integration import (
    get_xgboost_forecast
)

from backend.services.decision_engine import (
    get_decision
)

from backend.services.intent_router import (
    classify_intent
)

from backend.agents.policy_agent import (
    answer_question
)


print("=" * 70)
print("AI POLLUTION ENVIRONMENTAL ASSISTANT")
print("=" * 70)
print("Type 'exit' to close.")
print()


while True:

    try:

        question = input(
            "You: "
        ).strip()

        if not question:
            continue

        intent = classify_intent(
            question
        )

        if intent == "exit":

            print(
                "\nAssistant: Goodbye!"
            )

            break

        print(
            f"\nIntent detected: {intent}"
        )

        print(
            "Assistant: Analyzing...\n"
        )

        # ====================================================
        # EXISTING RAG POLICY AGENT
        # ====================================================

        if intent == "policy":

            result = answer_question(
                question
            )

            print(
                "POLICY / RAG ANSWER"
            )

            print(
                "-" * 70
            )

            print(
                result
            )

        # ====================================================
        # WEATHER
        # ====================================================

        elif intent == "weather":

            report = get_environment_report(
                question,
                forecast_hours=6
            )

            print(
                format_environment_report(
                    report
                )
            )

        # ====================================================
        # LIVE AIR QUALITY
        # ====================================================

        elif intent == "live_aqi":

            report = get_environment_report(
                question,
                forecast_hours=6
            )

            current = report[
                "current"
            ]

            print(
                "LIVE AIR QUALITY"
            )

            print(
                "-" * 70
            )

            for key in [
                "pm2_5",
                "pm10",
                "no2",
                "so2",
                "co",
                "o3"
            ]:

                print(
                    f"{key}: {current.get(key)}"
                )

            print(
                "\nTemperature:",
                current.get(
                    "temperature_c"
                ),
                "°C"
            )

            print(
                "Humidity:",
                current.get(
                    "humidity"
                ),
                "%"
            )

            print(
                "Rainfall:",
                current.get(
                    "rainfall_mm"
                ),
                "mm"
            )

        # ====================================================
        # XGBOOST
        # ====================================================

        elif intent == "forecast":

            report = get_environment_report(
                question,
                forecast_hours=6
            )

            location = report[
                "location"
            ][
                "requested_location"
            ]

            xgb = get_xgboost_forecast(
                location
            )

            print(
                "XGBOOST PM2.5 FORECAST"
            )

            print(
                "-" * 70
            )

            for key, value in xgb.items():

                print(
                    f"{key}: {value}"
                )

            print(
                "\nWEATHER FORECAST"
            )

            print(
                "-" * 70
            )

            for item in report[
                "forecast"
            ]:

                print(
                    item
                )

        # ====================================================
        # ANOMALY
        # ====================================================

        elif intent == "anomaly":

            report = get_environment_report(
                question,
                forecast_hours=1
            )

            location = report[
                "location"
            ][
                "requested_location"
            ]

            xgb = get_xgboost_forecast(
                location
            )

            decision = get_decision(
                location,
                report[
                    "current"
                ],
                xgb
            )

            print(
                "ANOMALY ANALYSIS"
            )

            print(
                "-" * 70
            )

            print(
                decision[
                    "anomaly"
                ]
            )

        # ====================================================
        # HOTSPOT
        # ====================================================

        elif intent == "hotspot":

            import os
            import pandas as pd

            root = (
                r"C:\final year project"
                r"\AI-POLLUTION-SYSTEM"
            )

            file = os.path.join(
                root,
                "data",
                "processed",
                "pune_hotspots.csv"
            )

            if not os.path.exists(file):

                print(
                    "Hotspot result file not found."
                )

            else:

                df = pd.read_csv(
                    file
                )

                hotspots = df[
                    df[
                        "is_hotspot_cluster"
                    ] == True
                ].sort_values(
                    "hotspot_score",
                    ascending=False
                )

                if hotspots.empty:

                    print(
                        "No hotspot cluster detected."
                    )

                else:

                    print(
                        hotspots.to_string(
                            index=False
                        )
                    )

        # ====================================================
        # DECISION / ACTION
        # ====================================================

        elif intent == "decision":

            report = get_environment_report(
                question,
                forecast_hours=6
            )

            location = report[
                "location"
            ][
                "requested_location"
            ]

            xgb = get_xgboost_forecast(
                location
            )

            decision = get_decision(
                location,
                report[
                    "current"
                ],
                xgb
            )

            print(
                "ENVIRONMENTAL DECISION"
            )

            print(
                "-" * 70
            )

            print(
                "Priorities:"
            )

            for item in decision[
                "priorities"
            ]:

                print(
                    f"- {item}"
                )

            print(
                "\nWarnings:"
            )

            for item in decision[
                "warnings"
            ]:

                print(
                    f"- {item}"
                )

            print(
                "\nRecommended actions:"
            )

            for item in decision[
                "recommended_actions"
            ]:

                print(
                    f"- {item}"
                )

        # ====================================================
        # DEFAULT ENVIRONMENT
        # ====================================================

        else:

            report = get_environment_report(
                question,
                forecast_hours=6
            )

            print(
                format_environment_report(
                    report
                )
            )

        print(
            "\n" + "=" * 70 + "\n"
        )

    except KeyboardInterrupt:

        print(
            "\nAssistant: Exiting..."
        )

        break

    except Exception as exc:

        print(
            "\nAssistant ERROR:"
        )

        print(
            exc
        )

        print(
            "\n" + "-" * 70 + "\n"
        )
