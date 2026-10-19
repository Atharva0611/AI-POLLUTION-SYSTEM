import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.india_environment import (
    get_environment_for_user
)

from backend.services.advanced_intelligence import (
    run_real_shap,
    run_hotspot,
    format_advanced_report,
)


def main():

    print("=" * 75)
    print("REAL SHAP + HOTSPOT TEST")
    print("=" * 75)

    print("")
    print("[1] LOADING WEATHERAPI ENVIRONMENT")

    environment = (
        get_environment_for_user(
            "What is the current pollution condition in Pune?"
        )
    )

    if not isinstance(
        environment,
        dict,
    ):
        print(
            "ERROR: environment result is not a dictionary"
        )
        return

    print(
        "ENVIRONMENT: OK"
    )

    print("")
    print("[2] RUNNING REAL SHAP")

    shap = run_real_shap(
        environment
    )

    print(
        "Available:",
        shap.get(
            "available"
        )
    )

    print(
        "Status:",
        shap.get(
            "status"
        )
    )

    if shap.get(
        "available"
    ):

        print(
            "Prediction:",
            shap.get(
                "prediction"
            )
        )

        print(
            "R2:",
            shap.get(
                "model_metrics",
            ).get(
                "R2"
            )
        )

        print(
            "RMSE:",
            shap.get(
                "model_metrics",
            ).get(
                "RMSE"
            )
        )

        print(
            ""
        )

        for item in shap.get(
            "top_features",
            [],
        ):

            print(
                f"{item['feature']} | "
                f"value={item['value']} | "
                f"SHAP={item['shap_value']:+.6f} | "
                f"{item['effect']}"
            )

    else:

        print(
            "Message:",
            shap.get(
                "message"
            )
        )

    print("")
    print("[3] RUNNING DBSCAN HOTSPOT")

    hotspot = run_hotspot(
        eps_km=5.0,
        min_samples=2,
    )

    print(
        "Available:",
        hotspot.get(
            "available"
        )
    )

    print(
        "Status:",
        hotspot.get(
            "status"
        )
    )

    if hotspot.get(
        "available"
    ):

        print(
            "Locations:",
            hotspot.get(
                "monitoring_locations"
            )
        )

        print(
            "Clusters:",
            hotspot.get(
                "cluster_count"
            )
        )

        for cluster in hotspot.get(
            "clusters",
            [],
        ):

            print(
                f"Cluster {cluster['cluster_id']} | "
                f"Stations={cluster['stations']} | "
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
            )
        )

    print("")
    print("[4] FINAL REPORT")

    result = {
        "shap": shap,
        "hotspot": hotspot,
    }

    print(
        format_advanced_report(
            result
        )
    )

    print("")
    print("=" * 75)
    print("TEST COMPLETE")
    print("=" * 75)


if __name__ == "__main__":
    main()
