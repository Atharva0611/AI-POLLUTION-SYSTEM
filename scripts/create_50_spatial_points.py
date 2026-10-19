import numpy as np
import pandas as pd
import os


# Pune urban analysis area
LAT_MIN = 18.43
LAT_MAX = 18.63

LON_MIN = 73.76
LON_MAX = 74.00

ROWS = 5
COLS = 10


def create_spatial_points():

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
                "latitude": round(float(lat), 6),
                "longitude": round(float(lon), 6),
                "location_type": "spatial_grid"
            })

            location_id += 1

    df = pd.DataFrame(rows)

    output_dir = "data/processed"

    os.makedirs(
        output_dir,
        exist_ok=True
    )

    output_file = os.path.join(
        output_dir,
        "pune_50_spatial_locations.csv"
    )

    df.to_csv(
        output_file,
        index=False
    )

    print(
        f"\nCreated {len(df)} spatial locations."
    )

    print(
        f"Saved to: {output_file}"
    )

    print(
        "\nFirst 10 locations:"
    )

    print(
        df.head(10).to_string(
            index=False
        )
    )


if __name__ == "__main__":
    create_spatial_points()