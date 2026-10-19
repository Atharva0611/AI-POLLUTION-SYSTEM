import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import pandas as pd

from backend.services.weather_intelligence import get_weather_report
from backend.ml.forecasting.predict_forecast import get_xgboost_forecast
from backend.pune_intelligence.location_network import load_locations, resolve_query
from backend.pune_intelligence.engine import build_location_intelligence

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "reports" / "pune_network"
OUT_JSON = OUT_DIR / "pune_100_plus_intelligence.json"
OUT_CSV = OUT_DIR / "pune_100_plus_summary.csv"

def _one(row):
    location = str(row["location"])
    query = resolve_query(row)
    try:
        env = get_weather_report(query, days=1)
    except Exception as exc:
        return {"location":location,"status":"weather_error","error":str(exc)}

    station = str(row.get("representative_cpcb_station") or "").strip()
    xgb = {}
    if station and station.lower() not in {"nan","none"}:
        try:
            xgb = get_xgboost_forecast(station)
        except Exception as exc:
            xgb = {"available":False,"reason":str(exc)}
    env["xgboost"] = xgb

    intel = build_location_intelligence(env, location, station or None)
    return {
        "location":location,
        "query":query,
        "latitude":row.get("latitude"),
        "longitude":row.get("longitude"),
        "representative_cpcb_station":station or None,
        "status":"ok",
        "environment":env,
        "intelligence":intel,
    }

def build_network(workers=4):
    locations = load_locations()
    if len(locations) < 100:
        raise ValueError(f"Only {len(locations)} Pune locations found; need 100+.")

    rows = locations.to_dict("records")
    results = []
    with ThreadPoolExecutor(max_workers=max(1,min(workers,8))) as pool:
        futures = [pool.submit(_one,row) for row in rows]
        for i,f in enumerate(as_completed(futures),1):
            r = f.result()
            results.append(r)
            print(f"[{i}/{len(rows)}] {r.get('location')} -> {r.get('status')}")

    ok = [r for r in results if r.get("status") == "ok"]
    scores = [r["intelligence"]["environmental_score"]["score"] for r in ok if r["intelligence"]["environmental_score"].get("score") is not None]
    for r in ok:
        if scores:
            s = r["intelligence"]["environmental_score"]["score"]
            r["intelligence"]["pune_relative_percentile"] = round(100*sum(x <= s for x in scores)/len(scores),1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "project":"Pune Locality Environmental Intelligence",
        "location_count":len(rows),
        "successful_locations":len(ok),
        "failed_locations":len(rows)-len(ok),
        "locations":results,
    }
    OUT_JSON.write_text(json.dumps(payload,indent=2,ensure_ascii=False,default=str), encoding="utf-8")

    summary=[]
    for r in results:
        intel=r.get("intelligence",{})
        ef=intel.get("environmental_score",{})
        top=intel.get("factor_fingerprint",{}).get("top_factors",[])
        summary.append({
            "location":r.get("location"),
            "latitude":r.get("latitude"),
            "longitude":r.get("longitude"),
            "representative_cpcb_station":r.get("representative_cpcb_station"),
            "status":r.get("status"),
            "environmental_score":ef.get("score"),
            "risk_band":ef.get("band"),
            "top_factor":top[0]["factor"] if top else None,
            "pune_relative_percentile":intel.get("pune_relative_percentile")
        })
    pd.DataFrame(summary).to_csv(OUT_CSV,index=False)
    return payload


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    result = build_network(args.workers)
    print()
    print("=" * 64)
    print("PUNE 100+ LOCALITY ENVIRONMENTAL INTELLIGENCE")
    print("=" * 64)
    print("Locations:", result["location_count"])
    print("Successful:", result["successful_locations"])
    print("Failed:", result["failed_locations"])
    print("JSON:", OUT_JSON)
    print("CSV:", OUT_CSV)
