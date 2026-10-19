from backend.pune_intelligence.location_network import load_locations
from backend.pune_intelligence.engine import build_location_intelligence

def pune_innovation_node(state):
    location = state.get("location") or state.get("resolved_location") or state.get("city")
    report = state.get("environment_report") or state.get("environment") or state.get("report")

    if not location or not isinstance(report, dict):
        return {"pune_innovation":{"available":False,"reason":"Pune location or environment report unavailable."}}

    df = load_locations()
    q = str(location).strip().lower()
    exact = df[df["location"].str.lower() == q]
    if exact.empty:
        exact = df[df["location"].str.lower().str.contains(q,regex=False,na=False)]

    if exact.empty:
        return {"pune_innovation":{"available":False,"reason":f"{location} is not in the Pune 100+ location network."}}

    row = exact.iloc[0].to_dict()
    station = str(row.get("representative_cpcb_station") or "").strip()

    return {
        "pune_innovation": {
            "available": True,
            **build_location_intelligence(report,str(row["location"]),station or None),
        }
    }
