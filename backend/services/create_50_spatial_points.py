import numpy as np
import pandas as pd

# Approximate Pune urban-area bounding box
# These are analysis-grid coordinates, NOT monitoring stations.
LAT_MIN = 18.43
LAT_MAX = 18.63

LON_MIN = 73.76
LON_MAX = 74.00

ROWS = 5
COLS = 10

latitudes = np.linspace(
    LAT_MIN,
    LAT_MAX,
    ROWS
)

longitudes = np.linspace(
    LON_MIN,
    LON_MAX,
    COLS
)

rows = []

location_id = 1

for lat in latitudes:

    for lon in longitudes:

        rows.append({
            "location_id": location_id,
            "location_name": f"GRID_{location_id:02d}",
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "location_type": "spatial_grid"
        })

        location_id += 1


df = pd.DataFrame(rows)

output_path = (
    "data/processed/"
    "pune_50_spatial_locations.csv"
)

df.to_csv(
    output_path,
    index=False
)

print(
    f"Created {len(df)} spatial locations."
)

print(
    f"Saved to: {output_path}"
)

print(df.to_string(index=False))