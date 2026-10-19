from __future__ import annotations

import argparse
from pathlib import Path

from .engine import build_innovation_report, load_environment_report, save_innovation_report


def find_report(location: str) -> Path:
    root = Path("data/reports")
    candidates = [
        root / f"{location}_environment_report.json",
        root / f"{location.lower()}_environment_report.json",
        root / f"{location.replace(' ', '_')}_environment_report.json",
    ]
    for p in candidates:
        if p.exists():
            return p

    # Fallback: case-insensitive scan.
    target = f"{location}_environment_report.json".lower()
    if root.exists():
        for p in root.glob("*_environment_report.json"):
            if p.name.lower() == target:
                return p
    raise FileNotFoundError(f"No environment report found for '{location}' under {root.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Additive Pollution Decision Intelligence layer")
    parser.add_argument("--location", required=True)
    parser.add_argument("--report", help="Optional path to an existing environment report JSON")
    parser.add_argument("--output", help="Optional innovation report output path")
    args = parser.parse_args()

    report_path = Path(args.report) if args.report else find_report(args.location)
    report = load_environment_report(report_path)
    innovation = build_innovation_report(report)

    out = Path(args.output) if args.output else Path("data/reports") / f"{args.location}_innovation_report.json"
    save_innovation_report(innovation, out)

    print("\n=== POLLUTION DECISION INTELLIGENCE ===")
    print(f"Location: {innovation['location']}")
    print(f"Environment report: {report_path}")
    print(f"Innovation report: {out}")

    baseline = innovation["baseline"]
    print(f"PM2.5: {baseline['pm25']}")
    print(f"Next-hour PM2.5: {baseline['next_hour_pm25']}")

    print("\nWHY:")
    for item in innovation["why_engine"]["summary"][:5]:
        print(f"- {item['factor']}: {item['reason']}")

    print("\nSOURCE INDICATORS:")
    for item in innovation["source_fingerprint"]["indicators"][:5]:
        print(f"- {item['source']}: {item['score']:.2f}")

    print("\nPOLICY-TO-ACTION:")
    for item in innovation["policy_to_action"]["actions"][:6]:
        print(f"- [{item['priority']}] {item['window']} {item['action']}")

    preview = innovation["intervention_simulator"]["preview"]
    if preview:
        print("\nINTERVENTION SIMULATOR PREVIEW:")
        print(f"- Scenario: {', '.join(preview['selected_interventions'])}")
        print(f"- Baseline PM2.5: {preview['baseline_pm25']}")
        print(f"- Estimated range: {preview['estimated_pm25_low']}–{preview['estimated_pm25_high']}")
        print(f"- Range reduction: {preview['reduction_low_pct']}–{preview['reduction_high_pct']}%")
        print(f"- Confidence: {preview['confidence']}")

    print("\nNote: source indicators are not definitive source apportionment; scenario ranges are not causal estimates.")


if __name__ == "__main__":
    main()
