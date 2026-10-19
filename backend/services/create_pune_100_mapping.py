import os
import pandas as pd

ROOT = r"C:\final year project\AI-POLLUTION-SYSTEM"

PROCESSED = os.path.join(
    ROOT,
    "data",
    "processed"
)

INPUT_FILE = os.path.join(
    PROCESSED,
    "pune_100_locations.csv"
)

OUTPUT_FILE = os.path.join(
    PROCESSED,
    "pune_100_locations_mapped.csv"
)

# ============================================================
# 12 REAL CPCB DATASET STATIONS USED BY YOUR XGBOOST MODEL
# ============================================================

STATIONS = [
    "Alandi",
    "Bhosari",
    "Bhumkar Nagar",
    "Dhankawadi",
    "Hadapsar",
    "Karve Road",
    "Katraj Dairy",
    "Mhada Colony",
    "Panchawati_Pashan",
    "Revenue Colony-Shivajinagar",
    "SPPU",
    "Transport Nagar-Nigdi"
]

# ============================================================
# 100 PUNE LOCATIONS
# ============================================================

LOCATIONS = [
    "Alandi",
    "Aundh",
    "Baner",
    "Balewadi",
    "Bavdhan",
    "Bhugaon",
    "Bhukum",
    "Bhosari",
    "Bibwewadi",
    "Bhumkar Nagar",
    "Camp",
    "Chakan",
    "Chinchwad",
    "Dapodi",
    "Dattawadi",
    "Deccan Gymkhana",
    "Dhankawadi",
    "Dhayari",
    "Erandwane",
    "Fatima Nagar",
    "Fursungi",
    "Hadapsar",
    "Hinjawadi",
    "Kalyani Nagar",
    "Katraj",
    "Kharadi",
    "Kondhwa",
    "Kothrud",
    "Koregaon Park",
    "Karve Nagar",
    "Karve Road",
    "Lohegaon",
    "Magarpatta",
    "Mahalunge",
    "Manjari",
    "Mangalwar Peth",
    "Market Yard",
    "Mhada Colony",
    "Model Colony",
    "Moshi",
    "Mukund Nagar",
    "Nagar Road",
    "Nanded",
    "Narayan Peth",
    "Nigdi",
    "Pashan",
    "Pimpri",
    "Pimple Gurav",
    "Pimple Nilakh",
    "Pimple Saudagar",
    "Pirangut",
    "Pune Cantonment",
    "Pune Station",
    "Rahatani",
    "Ranjangaon",
    "Rasta Peth",
    "Raviwar Peth",
    "Revenue Colony",
    "Sadashiv Peth",
    "Sangamwadi",
    "Sanjay Park",
    "Sasane Nagar",
    "Senapati Bapat Road",
    "Shaniwar Peth",
    "Shivajinagar",
    "Sinhagad Road",
    "Somwar Peth",
    "SPPU",
    "Sus",
    "Swargate",
    "Tathawade",
    "Thergaon",
    "Tingre Nagar",
    "Undri",
    "Viman Nagar",
    "Vishrantwadi",
    "Wadgaon Budruk",
    "Wadgaon Sheri",
    "Wagholi",
    "Wanowrie",
    "Warje",
    "Yerawada",
    "Akurdi",
    "Ambegaon",
    "Anand Nagar",
    "Bopodi",
    "Dhanori",
    "Gultekdi",
    "Keshav Nagar",
    "Kondhwa Khurd",
    "Mundhwa",
    "NIBM",
    "Parvati",
    "Sinhagad",
    "Talwade",
    "Vadgaon Sheri",
    "Wakad",
    "Wadgaon",
    "Vishal Nagar"
]

# ============================================================
# NORMALIZATION
# ============================================================

def norm(value):
    return (
        str(value)
        .strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
    )


# ============================================================
# DIRECT / REGIONAL MAPPING
#
# This maps each application location to one of the real
# CPCB station datasets used by your ML model.
# It does NOT claim that all 100 are physical CPCB stations.
# ============================================================

mapping = {

    # ---------------- NORTH ----------------
    "alandi": "Alandi",
    "bhosari": "Bhosari",
    "bhumkar nagar": "Bhumkar Nagar",
    "chakan": "Bhosari",
    "moshi": "Bhosari",
    "talwade": "Transport Nagar-Nigdi",

    # ---------------- PCMC ----------------
    "chinchwad": "Transport Nagar-Nigdi",
    "dappodi": "Bhosari",
    "dapodi": "Bhosari",
    "pimpri": "Transport Nagar-Nigdi",
    "pimple gurav": "Transport Nagar-Nigdi",
    "pimple nilakh": "Transport Nagar-Nigdi",
    "pimple saudagar": "Transport Nagar-Nigdi",
    "rahatani": "Transport Nagar-Nigdi",
    "tathawade": "Transport Nagar-Nigdi",
    "thergaon": "Transport Nagar-Nigdi",
    "wakad": "Transport Nagar-Nigdi",
    "vishal nagar": "Transport Nagar-Nigdi",
    "ak urdi": "Transport Nagar-Nigdi",
    "akurdi": "Transport Nagar-Nigdi",

    # ---------------- WEST ----------------
    "aundh": "SPPU",
    "baner": "SPPU",
    "balewadi": "SPPU",
    "bavdhan": "Panchawati_Pashan",
    "bhugaon": "Panchawati_Pashan",
    "bhukum": "Panchawati_Pashan",
    "hinjawadi": "SPPU",
    "mahalunge": "SPPU",
    "pashan": "Panchawati_Pashan",
    "pirangut": "Panchawati_Pashan",
    "sus": "Panchawati_Pashan",
    "sppu": "SPPU",
    "model colony": "SPPU",
    "senapati bapat road": "SPPU",

    # ---------------- CENTRAL ----------------
    "deccan gymkhana": "Revenue Colony-Shivajinagar",
    "dattawadi": "Revenue Colony-Shivajinagar",
    "erandwane": "Karve Road",
    "karve nagar": "Karve Road",
    "karve road": "Karve Road",
    "kothrud": "Karve Road",
    "mangalwar peth": "Revenue Colony-Shivajinagar",
    "narayan peth": "Revenue Colony-Shivajinagar",
    "rasta peth": "Revenue Colony-Shivajinagar",
    "raviwar peth": "Revenue Colony-Shivajinagar",
    "sadashiv peth": "Revenue Colony-Shivajinagar",
    "shaniwar peth": "Revenue Colony-Shivajinagar",
    "shivajinagar": "Revenue Colony-Shivajinagar",
    "somwar peth": "Revenue Colony-Shivajinagar",
    "pune station": "Revenue Colony-Shivajinagar",
    "revenue colony": "Revenue Colony-Shivajinagar",
    "bopodi": "Revenue Colony-Shivajinagar",

    # ---------------- SOUTH ----------------
    "dhankawadi": "Dhankawadi",
    "katraj": "Katraj Dairy",
    "bibwewadi": "Katraj Dairy",
    "ambegaon": "Katraj Dairy",
    "dahyari": "Dhankawadi",
    "dhayari": "Dhankawadi",
    "sinhagad road": "Dhankawadi",
    "sinhagad": "Dhankawadi",
    "swargate": "Dhankawadi",
    "parvati": "Dhankawadi",
    "gultekdi": "Dhankawadi",
    "nanded": "Dhankawadi",
    "wadgaon budruk": "Dhankawadi",
    "anand nagar": "Dhankawadi",

    # ---------------- EAST ----------------
    "hadapsar": "Hadapsar",
    "magarpatta": "Hadapsar",
    "manjari": "Hadapsar",
    "fursungi": "Hadapsar",
    "sasane nagar": "Hadapsar",
    "keshav nagar": "Hadapsar",
    "mundhwa": "Hadapsar",
    "nibm": "Hadapsar",
    "kondhwa": "Hadapsar",
    "kondhwa khurd": "Hadapsar",
    "undri": "Hadapsar",
    "fatima nagar": "Hadapsar",
    "wanowrie": "Hadapsar",

    # ---------------- EAST / AIRPORT ----------------
    "kharadi": "Hadapsar",
    "kalyani nagar": "Hadapsar",
    "koregaon park": "Hadapsar",
    "nagar road": "Hadapsar",
    "sanjay park": "Hadapsar",
    "tingre nagar": "Hadapsar",
    "viman nagar": "Hadapsar",
    "vishrantwadi": "Hadapsar",
    "wadgaon sheri": "Hadapsar",
    "vadgaon sheri": "Hadapsar",
    "wagholi": "Hadapsar",
    "lohegaon": "Hadapsar",

    # ---------------- CANTONMENT ----------------
    "camp": "Hadapsar",
    "pune cantonment": "Hadapsar",
    "mukund nagar": "Hadapsar",
    "market yard": "Dhankawadi",

    # ---------------- SOUTH / EAST ----------------
    "saswad": "Hadapsar",
    "r anjangaon": "Hadapsar",
    "ranjangaon": "Hadapsar",

    # ---------------- CENTRAL / WEST ----------------
    "warje": "Karve Road",
    "wadi": "Karve Road",
    "wadgaon": "Dhankawadi",

    # ---------------- NIGDI ----------------
    "nigdi": "Transport Nagar-Nigdi",

    # ---------------- MISC ----------------
    "pimpri": "Transport Nagar-Nigdi",
    "nanded": "Dhankawadi",
    "bhumkar nagar": "Bhumkar Nagar",
}


# ============================================================
# IF THE 100 CSV DOES NOT EXIST, CREATE IT
# ============================================================

if not os.path.exists(INPUT_FILE):

    print(
        "pune_100_locations.csv not found."
    )

    print(
        "Creating it from the project location master..."
    )

    pd.DataFrame(
        {
            "location_id": range(
                1,
                len(LOCATIONS) + 1
            ),
            "location_name": LOCATIONS,
            "location_type": [
                "analysis_location"
            ] * len(LOCATIONS),
            "source": [
                "Pune analysis master"
            ] * len(LOCATIONS)
        }
    ).to_csv(
        INPUT_FILE,
        index=False
    )


# ============================================================
# LOAD LOCATIONS
# ============================================================

df = pd.read_csv(
    INPUT_FILE
)

if "location_name" not in df.columns:

    raise ValueError(
        "location_name column is missing."
    )


# ============================================================
# CREATE MAPPING
# ============================================================

df["normalized_location"] = (
    df["location_name"]
    .map(norm)
)

def find_station(name):

    key = norm(name)

    # Direct mapping
    if key in mapping:
        return mapping[key]

    # Existing CPCB station name
    for station in STATIONS:
        if norm(station) == key:
            return station

    # Fallback by broad regional keywords

    if any(x in key for x in [
        "pimpri",
        "pimple",
        "wakad",
        "thergaon",
        "rahatani",
        "tathawade",
        "chinchwad",
        "akurdi"
    ]):
        return "Transport Nagar-Nigdi"

    if any(x in key for x in [
        "hadapsar",
        "magarpatta",
        "kharadi",
        "wagholi",
        "mundhwa",
        "undri",
        "kondhwa"
    ]):
        return "Hadapsar"

    if any(x in key for x in [
        "kothrud",
        "karve",
        "warje"
    ]):
        return "Karve Road"

    if any(x in key for x in [
        "pashan",
        "aundh",
        "baner",
        "balewadi",
        "sus",
        "bavdhan"
    ]):
        return "Panchawati_Pashan"

    if any(x in key for x in [
        "katraj",
        "dhankawadi",
        "ambegaon",
        "parvati",
        "sinhagad",
        "bibwewadi"
    ]):
        return "Dhankawadi"

    if any(x in key for x in [
        "shivajinagar",
        "peth",
        "camp",
        "station",
        "deccan"
    ]):
        return "Revenue Colony-Shivajinagar"

    return "SPPU"


df["representative_cpcb_station"] = (
    df["location_name"]
    .map(find_station)
)

df["mapping_method"] = (
    "100-location analysis master -> "
    "representative real CPCB dataset station"
)

df["mapping_note"] = (
    "This is not a claim that the area has its own CPCB station. "
    "The assigned station is the model's representative monitoring station."
)

df = df.drop(
    columns=[
        "normalized_location"
    ]
)

# ============================================================
# VALIDATION
# ============================================================

invalid = df[
    ~df[
        "representative_cpcb_station"
    ].isin(STATIONS)
]

if not invalid.empty:

    print(
        "\nERROR: invalid station mappings:"
    )

    print(
        invalid[
            [
                "location_name",
                "representative_cpcb_station"
            ]
        ].to_string(
            index=False
        )
    )

    raise SystemExit(1)


# ============================================================
# SAVE
# ============================================================

df.to_csv(
    OUTPUT_FILE,
    index=False
)

print()
print("=" * 75)
print("PUNE 100 LOCATION MAPPING CREATED")
print("=" * 75)

print(
    "Locations:",
    len(df)
)

print(
    "Mapped:",
    df[
        "representative_cpcb_station"
    ].notna().sum()
)

print(
    "Unmapped:",
    df[
        "representative_cpcb_station"
    ].isna().sum()
)

print()
print(
    "Output:"
)

print(
    OUTPUT_FILE
)

print()
print(
    "Station distribution:"
)

print(
    df[
        "representative_cpcb_station"
    ].value_counts().to_string()
)
