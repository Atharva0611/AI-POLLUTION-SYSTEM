import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.india_environment import (
    get_environment_for_user,
)

from backend.services.intelligence_engine import (
    build_intelligence,
)

from backend.services.advanced_intelligence import (
    format_advanced_report,
)


def main():

    print("=" * 70)
    print("FULL SHAP + HOTSPOT CONNECTION TEST")
    print("=" * 70)

    question = (
        "What is the current pollution condition in Pune?"
    )

    print("\nQUESTION")
    print(question)

    print("\n[1] WEATHER / ENVIRONMENT")
    environment = get_environment_for_user(
        question
    )

    if not isinstance(
        environment,
        dict,
    ):
        print(
            "ERROR: Environment service "
            "did not return a dictionary."
        )
        return

    print(
        "Environment loaded: OK"
    )

    print("\n[2] INTELLIGENCE ENGINE")
    intelligence = build_intelligence(
        environment=environment,
        location="Pune",
    )

    print(
        "Intelligence engine: OK"
    )

    print("\n[3] SHAP")
    shap = intelligence.get(
        "shap",
        {},
    )

    print(
        "Available:",
        shap.get(
            "available"
        ),
    )

    print(
        "Status:",
        shap.get(
            "status"
        ),
    )

    if shap.get("available"):
        print(
            "Prediction:",
            shap.get(
                "prediction"
            ),
        )

        print(
            "Model:",
            shap.get(
                "model_source"
            ),
        )

        for item in shap.get(
            "top_features",
            [],
        ):
            print(
                f"{item['feature']} | "
                f"SHAP={item['shap_value']:+.6f} | "
                f"{item['effect']}"
            )

    else:
        print(
            "Message:",
            shap.get(
                "message"
            ),
        )

    print("\n[4] HOTSPOT")
    hotspot = intelligence.get(
        "hotspot",
        {},
    )

    print(
        "Available:",
        hotspot.get(
            "available"
        ),
    )

    print(
        "Status:",
        hotspot.get(
            "status"
        ),
    )

    if hotspot.get("available"):

        print(
            "Dataset:",
            hotspot.get(
                "dataset"
            ),
        )

        print(
            "Clusters:",
            hotspot.get(
                "cluster_count"
            ),
        )

        for cluster in hotspot.get(
            "clusters",
            [],
        ):
            print(
                f"Cluster {cluster['cluster_id']} | "
                f"Center="
                f"{cluster['center_latitude']},"
                f"{cluster['center_longitude']} | "
                f"Avg PM2.5="
                f"{cluster['average_pm25']} | "
                f"Max PM2.5="
                f"{cluster['maximum_pm25']}"
            )

    else:
        print(
            "Message:",
            hotspot.get(
                "message"
            ),
        )

    print("\n[5] FINAL ADVANCED REPORT")
    print(
        format_advanced_report(
            intelligence
        )
    )

    print("\n")
    print("=" * 70)
    print("CONNECTION TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
