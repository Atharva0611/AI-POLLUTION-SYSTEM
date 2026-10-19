from pathlib import Path
import json
import os
import math
from datetime import datetime

ROOT = Path(r"C:\final year project\AI-POLLUTION-SYSTEM")
EVAL_DIR = ROOT / "evaluation"

REPORT_FILE = EVAL_DIR / "final_evaluation_report.md"
JSON_FILE = EVAL_DIR / "final_evaluation_report.json"


def file_exists(path):
    return path.exists()


def count_files(folder, pattern="*"):
    if not folder.exists():
        return 0
    return len(list(folder.glob(pattern)))


def safe_import(module_name):
    try:
        __import__(module_name)
        return True
    except Exception:
        return False


def evaluate_router():
    tests = [
        ("What is the rainfall status of Wagholi?", "environment"),
        ("What is the current weather in Alandi?", "environment"),
        ("What is the AQI of Kharadi?", "environment"),
        ("What is the temperature in Hadapsar?", "environment"),
        ("Give me the complete environmental report for Alandi.", "environment"),
        ("What are the National Ambient Air Quality Standards?", "policy"),
        ("What is NCAP?", "policy"),
        ("What is the role of CPCB?", "policy"),
        ("How can vehicle pollution be controlled?", "policy"),
        ("What measures can reduce road dust pollution?", "policy"),
        ("What measures can reduce construction dust?", "policy"),
        ("How can industrial emissions be controlled?", "policy"),
    ]

    try:
        from backend.services.intent_router import classify_intent

        results = []
        correct = 0

        for question, expected in tests:
            try:
                actual = classify_intent(question)
                ok = actual == expected

                if ok:
                    correct += 1

                results.append({
                    "question": question,
                    "expected": expected,
                    "actual": actual,
                    "correct": ok,
                })

            except Exception as exc:
                results.append({
                    "question": question,
                    "expected": expected,
                    "actual": f"ERROR: {type(exc).__name__}",
                    "correct": False,
                })

        accuracy = correct / len(tests) if tests else None

        return {
            "status": "completed",
            "total": len(tests),
            "correct": correct,
            "accuracy": accuracy,
            "tests": results,
        }

    except Exception as exc:
        return {
            "status": "unavailable",
            "reason": f"{type(exc).__name__}: {exc}",
        }


def evaluate_hotspots():
    file = ROOT / "data" / "processed" / "pune_hotspots.csv"

    if not file.exists():
        return {
            "status": "unavailable",
            "reason": "pune_hotspots.csv not found",
        }

    try:
        import pandas as pd
        from sklearn.metrics import silhouette_score

        df = pd.read_csv(file)

        result = {
            "status": "completed",
            "rows": len(df),
            "hotspot_count": int(
                df["is_hotspot_cluster"].sum()
            ) if "is_hotspot_cluster" in df.columns else None,
        }

        if "cluster" in df.columns and "latitude" in df.columns and "longitude" in df.columns:

            work = df[
                ["cluster", "latitude", "longitude"]
            ].dropna().copy()

            if len(work) >= 3:

                labels = work["cluster"].astype(int)

                valid = labels.value_counts()

                # Need at least 2 non-noise clusters.
                non_noise = work[labels != -1]

                if (
                    len(non_noise) >= 3
                    and non_noise["cluster"].nunique() >= 2
                ):

                    coords = non_noise[
                        ["latitude", "longitude"]
                    ].values

                    score = silhouette_score(
                        coords,
                        non_noise["cluster"].values
                    )

                    result["silhouette_score"] = float(
                        score
                    )

        return result

    except Exception as exc:
        return {
            "status": "unavailable",
            "reason": f"{type(exc).__name__}: {exc}",
        }


def evaluate_anomalies():
    file = ROOT / "data" / "processed" / "pune_anomaly_results.csv"

    if not file.exists():
        return {
            "status": "unavailable",
            "reason": "pune_anomaly_results.csv not found",
        }

    try:
        import pandas as pd

        df = pd.read_csv(file)

        result = {
            "status": "completed",
            "rows": len(df),
        }

        if "is_anomaly" in df.columns:
            anomalies = df["is_anomaly"].astype(bool)

            result["anomaly_count"] = int(
                anomalies.sum()
            )

            result["anomaly_rate"] = float(
                anomalies.mean()
            )

        if "anomaly_score" in df.columns:
            result["mean_anomaly_score"] = float(
                pd.to_numeric(
                    df["anomaly_score"],
                    errors="coerce"
                ).mean()
            )

        result["ground_truth_available"] = False
        result["note"] = (
            "Precision, recall and F1 require labeled anomaly ground truth."
        )

        return result

    except Exception as exc:
        return {
            "status": "unavailable",
            "reason": f"{type(exc).__name__}: {exc}",
        }


def evaluate_shap():
    folder = ROOT / "data" / "processed" / "shap"

    if not folder.exists():
        return {
            "status": "unavailable",
            "reason": "SHAP output directory not found",
        }

    files = list(folder.glob("*.csv"))

    return {
        "status": "completed",
        "explanation_files": len(files),
        "note": (
            "SHAP is evaluated as model explainability, not predictive accuracy."
        ),
    }


def evaluate_source_analysis():
    folder = ROOT / "data" / "processed" / "source_analysis"

    if not folder.exists():
        return {
            "status": "unavailable",
            "reason": "source_analysis directory not found",
        }

    files = list(folder.glob("*.csv"))

    return {
        "status": "completed",
        "analysis_files": len(files),
        "note": (
            "Results are statistical source indicators, not definitive source apportionment."
        ),
    }


def evaluate_chroma():
    folder = ROOT / "data" / "vector_store" / "chroma"

    if not folder.exists():
        return {
            "status": "unavailable",
            "reason": "Chroma directory not found",
        }

    result = {
        "status": "completed",
        "directory": str(folder),
    }

    try:
        import chromadb

        client = chromadb.PersistentClient(
            path=str(folder)
        )

        collections = client.list_collections()

        result["collections"] = [
            str(c.name)
            for c in collections
        ]

        try:
            collection = client.get_collection(
                "pune_policy_documents"
            )
            result["document_chunks"] = collection.count()
        except Exception:
            result["document_chunks"] = None

    except Exception as exc:
        result["status"] = "partial"
        result["reason"] = (
            f"{type(exc).__name__}: {exc}"
        )

    return result


def evaluate_database():
    result = {
        "status": "not_verified",
    }

    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except Exception:
        pass

    try:
        import psycopg2

        conn = psycopg2.connect(
            host=os.getenv("PGHOST", "localhost"),
            port=int(os.getenv("PGPORT", "5432")),
            dbname=os.getenv(
                "PGDATABASE",
                "ai_pollution"
            ),
            user=os.getenv(
                "PGUSER",
                "postgres"
            ),
            password=os.getenv(
                "PGPASSWORD",
                ""
            ),
            connect_timeout=3,
        )

        with conn.cursor() as cur:

            cur.execute(
                "SELECT PostGIS_Version();"
            )

            row = cur.fetchone()

            result["status"] = "connected"
            result["postgis_version"] = (
                row[0]
                if row
                else None
            )

        conn.close()

    except Exception as exc:
        result["status"] = "not_connected"
        result["reason"] = (
            f"{type(exc).__name__}: {exc}"
        )

    return result


def evaluate_artifacts():
    checks = {}

    paths = {
        "xgboost_model": ROOT / "models" / "forecasting" / "xgboost_pm25_forecasting.pkl",
        "feature_names": ROOT / "models" / "forecasting" / "feature_names.pkl",
        "weather_service": ROOT / "backend" / "services" / "india_environment.py",
        "ensemble_service": ROOT / "backend" / "services" / "forecast_integration.py",
        "policy_agent": ROOT / "backend" / "agents" / "policy_agent.py",
        "langgraph_agent": ROOT / "backend" / "agents" / "final_agent.py",
        "run_modules": ROOT / "backend" / "run_modules.py",
        "location_resolver": ROOT / "backend" / "services" / "location_resolver.py",
        "postgres_schema": ROOT / "backend" / "database" / "schema.sql",
        "chroma_builder": ROOT / "backend" / "rag" / "build_chroma.py",
        "shap_explainer": ROOT / "backend" / "ml" / "explainability" / "shap_explainer.py",
        "source_analysis": ROOT / "backend" / "ml" / "source_analysis.py",
    }

    for name, path in paths.items():
        checks[name] = file_exists(path)

    return checks


def known_xgboost_benchmark():
    """
    Previous project benchmark recorded during development.
    This is NOT recalculated here and should be replaced by a
    proper held-out test evaluation before final publication.
    """
    return {
        "status": "previous_benchmark",
        "mae": 1.84,
        "rmse": 21.58,
        "r2": 0.7058,
        "note": (
            "Previous development benchmark. "
            "Run a held-out chronological test before using this as final paper/report evidence."
        ),
    }


def build_report(data):

    router = data["router"]
    xgb = data["xgboost"]

    lines = []

    lines.append("# AI Pollution System - Final Evaluation Report")
    lines.append("")
    lines.append(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    lines.append("")

    lines.append("## 1. System Modules")
    lines.append("")
    lines.append("| Module | Status |")
    lines.append("|---|---|")

    module_map = {
        "Data / Models": data["artifacts"]["xgboost_model"],
        "WeatherAPI": data["artifacts"]["weather_service"],
        "XGBoost": data["artifacts"]["xgboost_model"],
        "Ensemble": data["artifacts"]["ensemble_service"],
        "Isolation Forest": file_exists(
            ROOT / "data" / "processed" / "pune_anomaly_results.csv"
        ),
        "DBSCAN": file_exists(
            ROOT / "data" / "processed" / "pune_hotspots.csv"
        ),
        "SHAP": data["shap"]["status"] == "completed",
        "Source Analysis": data["source_analysis"]["status"] == "completed",
        "RAG Policy Agent": data["artifacts"]["policy_agent"],
        "LangGraph": data["artifacts"]["langgraph_agent"],
        "PostgreSQL/PostGIS": data["database"]["status"] == "connected",
        "Chroma Vector DB": data["chroma"]["status"] in {
            "completed",
            "partial",
        },
    }

    for module, status in module_map.items():
        lines.append(
            f"| {module} | {'Available' if status else 'Missing / incomplete'} |"
        )

    lines.append("")

    lines.append("## 2. XGBoost PM2.5 Forecasting")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| MAE | {xgb['mae']} |")
    lines.append(f"| RMSE | {xgb['rmse']} |")
    lines.append(f"| R2 | {xgb['r2']} |")
    lines.append("")
    lines.append(
        "> Important: these values are the previous development benchmark. "
        "They should not be presented as the final test result without a "
        "chronological held-out evaluation."
    )
    lines.append("")

    lines.append("## 3. LangGraph Routing Evaluation")
    lines.append("")
    lines.append(
        f"Routing accuracy: "
        f"{router['accuracy'] * 100:.2f}% "
        f"({router['correct']}/{router['total']})"
        if router.get("accuracy") is not None
        else "Routing evaluation unavailable."
    )
    lines.append("")
    lines.append("| Question | Expected | Actual | Correct |")
    lines.append("|---|---|---|---|")

    for item in router.get("tests", []):
        lines.append(
            f"| {item['question']} | "
            f"{item['expected']} | "
            f"{item['actual']} | "
            f"{'Yes' if item['correct'] else 'No'} |"
        )

    lines.append("")

    lines.append("## 4. Anomaly Detection")
    lines.append("")

    anomaly = data["anomaly"]

    if anomaly["status"] == "completed":

        lines.append(
            f"- Observations: {anomaly.get('rows')}"
        )

        lines.append(
            f"- Detected anomalies: {anomaly.get('anomaly_count')}"
        )

        if anomaly.get("anomaly_rate") is not None:
            lines.append(
                f"- Anomaly rate: "
                f"{anomaly['anomaly_rate'] * 100:.2f}%"
            )

        lines.append(
            "- Ground-truth labels: Not available"
        )

    else:

        lines.append(
            f"Status: {anomaly.get('reason')}"
        )

    lines.append("")

    lines.append("## 5. DBSCAN Hotspot Detection")
    lines.append("")

    hotspots = data["hotspots"]

    if hotspots["status"] == "completed":

        lines.append(
            f"- Records: {hotspots.get('rows')}"
        )

        lines.append(
            f"- Hotspot records: {hotspots.get('hotspot_count')}"
        )

        if hotspots.get("silhouette_score") is not None:
            lines.append(
                f"- Silhouette score: "
                f"{hotspots['silhouette_score']:.4f}"
            )
        else:
            lines.append(
                "- Silhouette score: unavailable"
            )

    else:

        lines.append(
            f"Status: {hotspots.get('reason')}"
        )

    lines.append("")

    lines.append("## 6. SHAP Explainability")
    lines.append("")
    lines.append(
        f"Generated explanation files: "
        f"{data['shap'].get('explanation_files', 0)}"
    )
    lines.append(
        "SHAP provides feature contribution explanations; "
        "it is not an accuracy metric."
    )
    lines.append("")

    lines.append("## 7. Source Analysis")
    lines.append("")
    lines.append(
        f"Generated source-analysis files: "
        f"{data['source_analysis'].get('analysis_files', 0)}"
    )
    lines.append(
        "Interpretation: statistical source indicators, "
        "not definitive chemical source apportionment."
    )
    lines.append("")

    lines.append("## 8. RAG / Vector Database")
    lines.append("")
    lines.append(
        f"Chroma status: {data['chroma']['status']}"
    )

    if data["chroma"].get("document_chunks") is not None:
        lines.append(
            f"Indexed document chunks: "
            f"{data['chroma']['document_chunks']}"
        )

    lines.append("")

    lines.append("## 9. PostgreSQL / PostGIS")
    lines.append("")
    lines.append(
        f"Database status: {data['database']['status']}"
    )

    if data["database"].get("postgis_version"):
        lines.append(
            f"PostGIS version: "
            f"{data['database']['postgis_version']}"
        )

    if data["database"].get("reason"):
        lines.append(
            f"Reason: {data['database']['reason']}"
        )

    lines.append("")

    lines.append("## 10. Final Assessment")
    lines.append("")
    lines.append(
        "The project contains the main intelligence modules for "
        "live environmental analysis, PM2.5 forecasting, anomaly "
        "detection, hotspot detection, explainability, source "
        "analysis, policy retrieval and LangGraph orchestration."
    )
    lines.append("")
    lines.append(
        "Final predictive accuracy should be reported only from a "
        "chronological held-out test set. Anomaly and hotspot modules "
        "require task-specific validation rather than a generic accuracy percentage."
    )
    lines.append("")

    return "\n".join(lines)


def main():

    data = {
        "artifacts": evaluate_artifacts(),
        "router": evaluate_router(),
        "xgboost": known_xgboost_benchmark(),
        "anomaly": evaluate_anomalies(),
        "hotspots": evaluate_hotspots(),
        "shap": evaluate_shap(),
        "source_analysis": evaluate_source_analysis(),
        "chroma": evaluate_chroma(),
        "database": evaluate_database(),
    }

    report = build_report(
        data
    )

    REPORT_FILE.write_text(
        report,
        encoding="utf-8"
    )

    JSON_FILE.write_text(
        json.dumps(
            data,
            indent=2,
            default=str
        ),
        encoding="utf-8"
    )

    print("=" * 70)
    print("FINAL PROJECT EVALUATION")
    print("=" * 70)
    print("")
    print(report)
    print("")
    print("=" * 70)
    print("Report saved:")
    print(REPORT_FILE)
    print(JSON_FILE)
    print("=" * 70)


if __name__ == "__main__":
    main()
