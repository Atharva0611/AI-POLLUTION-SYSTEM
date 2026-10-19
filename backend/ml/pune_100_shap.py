from pathlib import Path
import json
import re
import subprocess
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

LOCATION_FILE = (
    ROOT
    / "data"
    / "processed"
    / "pune_100_locations_mapped.csv"
)

STATION_DATA = (
    ROOT
    / "data"
    / "processed"
    / "pune_cpcb_all_stations_hourly.csv"
)

SHAP_SCRIPT = (
    ROOT
    / "backend"
    / "ml"
    / "shap_final.py"
)

OUT_DIR = (
    ROOT
    / "data"
    / "reports"
    / "shap"
    / "pune_100"
)

OUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# HELPERS
# ============================================================

def norm(value):
    value = str(value).strip().lower()
    value = re.sub(
        r"[^a-z0-9]+",
        "_",
        value
    )
    return re.sub(
        r"_+",
        "_",
        value
    ).strip("_")


def find_column(df, candidates):

    normalized = {
        norm(c): c
        for c in df.columns
    }

    for candidate in candidates:

        key = norm(candidate)

        if key in normalized:
            return normalized[key]

    for col in df.columns:

        n = norm(col)

        for candidate in candidates:

            if norm(candidate) in n:
                return col

    return None


# ============================================================
# CHECK FILES
# ============================================================

for path, name in [
    (LOCATION_FILE, "Pune 100+ location master"),
    (STATION_DATA, "Pune CPCB station dataset"),
    (SHAP_SCRIPT, "SHAP engine")
]:

    if not path.exists():

        raise FileNotFoundError(
            f"{name} not found:\n{path}"
        )


# ============================================================
# LOAD LOCATION MASTER
# ============================================================

locations = pd.read_csv(
    LOCATION_FILE
)

location_col = find_column(
    locations,
    [
        "location",
        "location_name",
        "locality",
        "name",
        "place",
        "area"
    ]
)

station_col = find_column(
    locations,
    [
        "representative_cpcb_station",
        "representative_station",
        "cpcb_station",
        "station"
    ]
)

lat_col = find_column(
    locations,
    [
        "latitude",
        "lat"
    ]
)

lon_col = find_column(
    locations,
    [
        "longitude",
        "lon",
        "lng"
    ]
)

if location_col is None:
    raise ValueError(
        "Location column not found.\n"
        f"Columns: {locations.columns.tolist()}"
    )

if station_col is None:
    raise ValueError(
        "Representative CPCB station column not found.\n"
        f"Columns: {locations.columns.tolist()}"
    )


locations = locations.rename(
    columns={
        location_col: "location",
        station_col: "representative_station"
    }
)

if lat_col:
    locations["latitude"] = pd.to_numeric(
        locations[lat_col],
        errors="coerce"
    )
else:
    locations["latitude"] = None

if lon_col:
    locations["longitude"] = pd.to_numeric(
        locations[lon_col],
        errors="coerce"
    )
else:
    locations["longitude"] = None


locations["location"] = (
    locations["location"]
    .astype(str)
    .str.strip()
)

locations["representative_station"] = (
    locations["representative_station"]
    .astype(str)
    .str.strip()
)

locations = locations[
    locations["location"].ne("")
].drop_duplicates(
    "location"
).reset_index(
    drop=True
)


# ============================================================
# LOAD ACTUAL CPCB STATIONS
# ============================================================

station_df = pd.read_csv(
    STATION_DATA,
    usecols=lambda c: c
)

actual_station_col = find_column(
    station_df,
    [
        "station_name",
        "station",
        "site"
    ]
)

if actual_station_col is None:

    raise ValueError(
        "station_name column not found in CPCB dataset."
    )


actual_stations = sorted(
    station_df[
        actual_station_col
    ]
    .dropna()
    .astype(str)
    .str.strip()
    .unique()
    .tolist()
)


# ============================================================
# MAP REPRESENTATIVE STATION
# ============================================================

def resolve_station(requested):

    requested_norm = norm(
        requested
    )

    if requested_norm in {
        "",
        "nan",
        "none"
    }:
        return None

    # Exact normalized match
    for station in actual_stations:

        if norm(station) == requested_norm:
            return station

    # Requested name contained in real name
    for station in actual_stations:

        station_norm = norm(
            station
        )

        if (
            requested_norm in station_norm
            or
            station_norm in requested_norm
        ):
            return station

    return None


locations["resolved_station"] = (
    locations[
        "representative_station"
    ]
    .map(resolve_station)
)


# ============================================================
# UNIQUE STATION LIST
# ============================================================

station_map = {}

for station in (
    locations[
        "resolved_station"
    ]
    .dropna()
    .unique()
):

    station_map[
        station
    ] = None


print("")
print("=" * 70)
print("PUNE 100+ SHAP ANALYSIS")
print("=" * 70)

print(
    f"\nPune localities: {len(locations)}"
)

print(
    f"Actual CPCB stations available: "
    f"{len(actual_stations)}"
)

print(
    f"Unique SHAP stations required: "
    f"{len(station_map)}"
)


# ============================================================
# RUN SHAP ON EACH UNIQUE STATION
# ============================================================

station_reports = {}

for index, station in enumerate(
    station_map.keys(),
    start=1
):

    print("")
    print(
        f"[{index}/{len(station_map)}] "
        f"SHAP -> {station}"
    )

    safe_station = norm(
        station
    )

    report_file = (
        ROOT
        / "data"
        / "reports"
        / "shap"
        / f"shap_local_{safe_station}.csv"
    )

    json_file = (
        ROOT
        / "data"
        / "reports"
        / "shap"
        / "shap_report.json"
    )

    try:

        result = subprocess.run(

            [
                sys.executable,
                str(SHAP_SCRIPT),

                "--station",
                station,

                "--max-rows",
                "1000",

                "--top-n",
                "10"
            ],

            cwd=str(ROOT),

            capture_output=True,

            text=True,

            timeout=300

        )


        # Save terminal output for debugging.
        log_file = (
            OUT_DIR
            / f"{safe_station}_shap.log"
        )

        log_file.write_text(
            result.stdout
            + "\n\nSTDERR\n"
            + result.stderr,
            encoding="utf-8"
        )


        if result.returncode != 0:

            print(
                f"  FAILED: {station}"
            )

            print(
                result.stderr[-1000:]
            )

            continue


        if not json_file.exists():

            print(
                "  FAILED: SHAP report not created."
            )

            continue


        with open(
            json_file,
            "r",
            encoding="utf-8"
        ) as f:

            report = json.load(f)


        # Copy station-specific JSON report.
        station_json = (
            OUT_DIR
            / f"{safe_station}_shap_report.json"
        )

        with open(
            station_json,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                report,
                f,
                indent=2,
                ensure_ascii=False
            )


        station_reports[
            station
        ] = report


        print(
            "  PASS"
        )

        print(
            "  Prediction:",
            report.get(
                "latest_explanation",
                {}
            ).get(
                "predicted_pm25_next_1h"
            )
        )

        print(
            "  Additivity:",
            report.get(
                "latest_explanation",
                {}
            )
            .get(
                "additivity_check",
                {}
            )
            .get(
                "within_tolerance"
            )
        )


    except subprocess.TimeoutExpired:

        print(
            "  TIMEOUT"
        )

    except Exception as exc:

        print(
            "  ERROR:",
            exc
        )


# ============================================================
# BUILD LOCALITY-LEVEL OUTPUT
# ============================================================

results = []

for _, row in locations.iterrows():

    locality = row[
        "location"
    ]

    representative = row[
        "representative_station"
    ]

    resolved = row[
        "resolved_station"
    ]


    base = {

        "location":
            locality,

        "latitude":
            row.get(
                "latitude"
            ),

        "longitude":
            row.get(
                "longitude"
            ),

        "representative_cpcb_station":
            representative,

        "resolved_cpcb_station":
            resolved,

        "shap_status":
            "UNAVAILABLE"

    }


    if (
        pd.isna(resolved)
        or
        resolved is None
        or
        str(resolved).strip() == ""
    ):

        base[
            "reason"
        ] = (
            "Representative station "
            "could not be matched to "
            "the 12-station XGBoost model."
        )

        results.append(
            base
        )

        continue


    report = station_reports.get(
        resolved
    )


    if not report:

        base[
            "reason"
        ] = (
            "SHAP station analysis failed."
        )

        results.append(
            base
        )

        continue


    latest = report.get(
        "latest_explanation",
        {}
    )


    additivity = latest.get(
        "additivity_check",
        {}
    )


    base.update({

        "shap_status":
            "AVAILABLE",

        "predicted_pm25_next_1h":
            latest.get(
                "predicted_pm25_next_1h"
            ),

        "expected_value":
            additivity.get(
                "expected_value"
            ),

        "reconstructed_prediction":
            additivity.get(
                "reconstructed_prediction"
            ),

        "shap_additivity_error":
            additivity.get(
                "absolute_error"
            ),

        "shap_additivity_pass":
            additivity.get(
                "within_tolerance"
            )
    })


    factors = latest.get(
        "top_factors",
        []
    )


    for i in range(
        5
    ):

        position = i + 1

        if i < len(factors):

            factor = factors[i]

            base[
                f"factor_{position}"
            ] = factor.get(
                "feature"
            )

            base[
                f"factor_{position}_value"
            ] = factor.get(
                "feature_value"
            )

            base[
                f"factor_{position}_shap"
            ] = factor.get(
                "shap_value"
            )

            base[
                f"factor_{position}_direction"
            ] = factor.get(
                "direction"
            )

        else:

            base[
                f"factor_{position}"
            ] = None

            base[
                f"factor_{position}_value"
            ] = None

            base[
                f"factor_{position}_shap"
            ] = None

            base[
                f"factor_{position}_direction"
            ] = None


    results.append(
        base
    )


# ============================================================
# SAVE CSV
# ============================================================

result_df = pd.DataFrame(
    results
)

CSV_PATH = (
    OUT_DIR
    / "pune_100_shap_results.csv"
)

result_df.to_csv(
    CSV_PATH,
    index=False
)


# ============================================================
# SAVE JSON
# ============================================================

JSON_PATH = (
    OUT_DIR
    / "pune_100_shap_results.json"
)

with open(
    JSON_PATH,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        results,
        f,
        indent=2,
        ensure_ascii=False,
        default=lambda x:
            x.item()
            if hasattr(x, "item")
            else str(x)
    )


# ============================================================
# SUMMARY
# ============================================================

available = (
    result_df[
        "shap_status"
    ]
    .eq("AVAILABLE")
    .sum()
)

unavailable = len(
    result_df
) - available


print("")
print("=" * 70)
print("PUNE 100+ SHAP COMPLETE")
print("=" * 70)

print(
    "\nTotal localities:",
    len(result_df)
)

print(
    "SHAP available:",
    available
)

print(
    "SHAP unavailable:",
    unavailable
)

print(
    "\nOutput:"
)

print(
    CSV_PATH
)

print(
    JSON_PATH
)


print("")
print(
    "Sample results:"
)

display_cols = [
    "location",
    "resolved_cpcb_station",
    "predicted_pm25_next_1h",
    "factor_1",
    "factor_1_shap",
    "factor_2",
    "factor_2_shap",
    "factor_3",
    "factor_3_shap"
]

display_cols = [
    c
    for c in display_cols
    if c in result_df.columns
]

print(
    result_df[
        display_cols
    ]
    .head(15)
    .to_string(
        index=False
    )
)

print("")
print(
    "SHAP STATUS: 100+ LOCALITY ANALYSIS COMPLETE"
)
