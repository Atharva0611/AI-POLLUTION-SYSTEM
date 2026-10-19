from __future__ import annotations

import csv
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "processed"
REPORTS = ROOT / "data" / "reports"
RAW_OUT = OUT / "phase3_pune_official_feed_raw.json"
CSV_OUT = OUT / "phase3_pune_station_observations.csv"
REPORT_OUT = REPORTS / "phase3_observation_feed_audit.json"

API_URL = "https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
MAX_AGE_HOURS = 72
PUNE_BOUNDS = (18.2, 18.9, 73.4, 74.2)


def read_key():
    key = os.environ.get("DATA_GOV_IN_API_KEY", "").strip()
    if key:
        return key
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            match = re.match(r"^\s*(?:export\s+)?DATA_GOV_IN_API_KEY\s*=\s*(.*?)\s*$", line)
            if match:
                return match.group(1).strip().strip("'\"")
    return ""


def parse_time(value):
    if not value:
        return None
    text = str(value).strip()
    candidates = (
        text,
        text.replace(" IST", "+05:30"),
        text.replace(" UTC", "+00:00"),
    )
    formats = (
        "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M",
        "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
        "%d-%b-%Y %H:%M", "%d %b %Y, %H:%M",
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
    )
    for candidate in candidates:
        try:
            dt = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                # data.gov.in station timestamps are generally local station time.
                from zoneinfo import ZoneInfo
                dt = dt.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
            return dt.astimezone(timezone.utc)
        except (ValueError, TypeError):
            pass
        for fmt in formats:
            try:
                from zoneinfo import ZoneInfo
                dt = datetime.strptime(candidate, fmt).replace(tzinfo=ZoneInfo("Asia/Kolkata"))
                return dt.astimezone(timezone.utc)
            except ValueError:
                pass
    return None


def number(value):
    try:
        v = float(str(value).replace(",", "").strip())
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def first(record, *keys):
    lowered = {str(k).strip().lower().replace(" ", "_"): v for k, v in record.items()}
    for key in keys:
        val = lowered.get(key.lower().replace(" ", "_"))
        if val not in (None, ""):
            return val
    return None


def normalize(record):
    pollutant = str(first(record, "pollutant_id", "pollutant", "parameter") or "").strip().upper()
    if pollutant.replace(" ", "") not in {"PM2.5", "PM25", "PM_2.5", "PM₂.₅"}:
        return None

    city = str(first(record, "city", "district") or "").strip()
    state = str(first(record, "state", "state_name") or "").strip()
    if "pune" not in city.lower() or "maharashtra" not in state.lower():
        return None

    lat = number(first(record, "latitude", "lat"))
    lon = number(first(record, "longitude", "lon", "lng"))
    value = number(first(record, "pollutant_avg", "concentration", "value", "pollutant_value"))
    unit = str(first(record, "pollutant_unit", "unit", "units") or "").strip().lower()
    stamp_raw = first(record, "last_update", "last_updated", "timestamp", "date_time", "datetime")
    stamp = parse_time(stamp_raw)

    # Never guess missing coordinates or unknown concentration units.
    coordinate_ok = lat is not None and lon is not None and (
        PUNE_BOUNDS[0] <= lat <= PUNE_BOUNDS[1]
        and PUNE_BOUNDS[2] <= lon <= PUNE_BOUNDS[3]
    )
    unit_ok = unit in {"ug/m3", "µg/m3", "μg/m3", "microgram/m3", "micrograms/m3"}
    now = datetime.now(timezone.utc)
    age_hours = (now - stamp).total_seconds() / 3600 if stamp else None
    fresh = age_hours is not None and -0.25 <= age_hours <= MAX_AGE_HOURS
    valid_value = value is not None and 0 <= value <= 1000

    return {
        "station_id": str(first(record, "station_id", "site_id", "id") or ""),
        "station_name": str(first(record, "station", "station_name", "location") or ""),
        "city": city,
        "state": state,
        "latitude": lat,
        "longitude": lon,
        "timestamp_utc": stamp.isoformat() if stamp else "",
        "pm25_ug_m3": value if unit_ok else None,
        "source_unit": unit,
        "source": "data.gov.in_CPCB_catalog",
        "coordinate_valid": coordinate_ok,
        "unit_valid": unit_ok,
        "timestamp_valid": stamp is not None,
        "fresh_72h": fresh,
        "value_valid": valid_value,
        "age_hours": round(age_hours, 2) if age_hours is not None else None,
        "usable_for_model": bool(coordinate_ok and unit_ok and stamp and fresh and valid_value),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    report = {
        "source": API_URL,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "freshness_limit_hours": MAX_AGE_HOURS,
        "production_artifacts_modified": False,
        "status": "failed",
    }

    key = read_key()
    if not key:
        report["reason"] = (
            "DATA_GOV_IN_API_KEY is missing. Add a valid data.gov.in API key "
            "to the environment or project .env; no fabricated station data was created."
        )
        REPORT_OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    records = []
    try:
        for offset in range(0, 1000, 500):
            params = {
                "api-key": key,
                "format": "json",
                "limit": 500,
                "offset": offset,
                "filters[state]": "Maharashtra",
                "filters[city]": "Pune",
            }
            response = requests.get(API_URL, params=params, timeout=25)
            response.raise_for_status()
            payload = response.json()
            batch = payload.get("records", [])
            if not isinstance(batch, list):
                raise ValueError("API response does not contain a records list.")
            records.extend(batch)
            if len(batch) < 500:
                break
    except Exception as exc:
        report["reason"] = f"Official catalog API request failed: {type(exc).__name__}: {exc}"
        REPORT_OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 3

    RAW_OUT.write_text(json.dumps(records, indent=2), encoding="utf-8")
    normalized = [x for r in records if (x := normalize(r)) is not None]
    # Deduplicate station rows by station id/name and observation time.
    dedup = {}
    for row in normalized:
        identity = (row["station_id"] or row["station_name"], row["timestamp_utc"])
        dedup[identity] = row
    normalized = list(dedup.values())

    fields = list(normalized[0].keys()) if normalized else [
        "station_id", "station_name", "city", "state", "latitude", "longitude",
        "timestamp_utc", "pm25_ug_m3", "source_unit", "source",
        "coordinate_valid", "unit_valid", "timestamp_valid", "fresh_72h",
        "value_valid", "age_hours", "usable_for_model",
    ]
    with CSV_OUT.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(normalized)

    usable = [x for x in normalized if x["usable_for_model"]]
    report.update({
        "status": "success" if records else "no_records",
        "records_returned_by_api": len(records),
        "pune_pm25_records_normalized": len(normalized),
        "fresh_valid_station_observations": len(usable),
        "unique_usable_stations": len({x["station_id"] or x["station_name"] for x in usable}),
        "invalid_or_stale_records": len(normalized) - len(usable),
        "csv_path": str(CSV_OUT.relative_to(ROOT)),
        "raw_response_path": str(RAW_OUT.relative_to(ROOT)),
        "model_input_ready": bool(usable),
        "production_artifacts_modified": False,
    })
    report["reason"] = (
        "Fresh, valid provider observations found. Review station provenance before model inference."
        if usable else
        "No fresh, valid station observations found. Candidate inference must remain blocked."
    )
    REPORT_OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if usable else 4


if __name__ == "__main__":
    sys.exit(main())
