from pathlib import Path
import pandas as pd
import numpy as np
import re


# ============================================================
# ADD VERIFIED PUNE WEATHER LOCATION WHEN MASTER HAS <100
# ============================================================

def _norm_location(value):

    value = str(value).strip().lower()

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value
    )

    return re.sub(
        r"\s+",
        " ",
        value
    ).strip()


PUNE_WEATHER_SEED = [

    {
        "location": "NIGDI",
        "latitude": 18.646511,
        "longitude": 73.775411
    },

    {
        "location": "Bibwewadi",
        "latitude": 18.492332,
        "longitude": 73.861939
    },

    {
        "location": "Nanded-Nahre",
        "latitude": 18.453179,
        "longitude": 73.811077
    },

    {
        "location": "Camp Area",
        "latitude": 18.513693,
        "longitude": 73.877293
    },

    {
        "location": "Magarpatta",
        "latitude": 18.519482,
        "longitude": 73.934360
    },

    {
        "location": "Yerwada",
        "latitude": 18.544659,
        "longitude": 73.869499
    },

    {
        "location": "Kalyani Nagar",
        "latitude": 18.546538,
        "longitude": 73.906594
    },

    {
        "location": "Dhanori",
        "latitude": 18.588936,
        "longitude": 73.907711
    },

    {
        "location": "Kharadi",
        "latitude": 18.552390,
        "longitude": 73.941901
    },

    {
        "location": "Wagholi",
        "latitude": 18.579310,
        "longitude": 73.972122
    }

]


def add_100th_location(
    locations,
    actual_stations,
    cpcb_df
):

    if len(locations) >= 100:

        return locations


    existing = {
        _norm_location(x)
        for x in locations[
            "location"
        ].astype(str)
    }


    new_location = None


    for candidate in PUNE_WEATHER_SEED:

        if _norm_location(
            candidate["location"]
        ) not in existing:

            new_location = candidate

            break


    if new_location is None:

        raise RuntimeError(
            "Could not find an additional unique "
            "Pune weather location."
        )


    # --------------------------------------------------------
    # Find nearest real CPCB station.
    # Simple coordinate-distance approximation is sufficient
    # for choosing a representative station at city scale.
    # --------------------------------------------------------

    station_points = (
        cpcb_df[
            [
                "_station",
                "_latitude",
                "_longitude"
            ]
        ]
        .drop_duplicates(
            "_station"
        )
        .dropna()
    )


    if station_points.empty:

        representative = ""


    else:

        lat = float(
            new_location["latitude"]
        )

        lon = float(
            new_location["longitude"]
        )


        distances = (

            (
                station_points[
                    "_latitude"
                ] - lat
            ) ** 2

            +

            (
                station_points[
                    "_longitude"
                ] - lon
            ) ** 2

        )


        nearest_index = distances.idxmin()


        representative = str(
            station_points.loc[
                nearest_index,
                "_station"
            ]
        )


    new_row = {

        "location":
            new_location[
                "location"
            ],

        "latitude_input":
            new_location[
                "latitude"
            ],

        "longitude_input":
            new_location[
                "longitude"
            ],

        "representative_station":
            representative,

        "location_mapping_method":
            "WeatherUnion_verified_location",

        "station_mapping_method":
            "nearest_cpcb_by_distance"

    }


    locations = pd.concat(

        [
            locations,
            pd.DataFrame(
                [new_row]
            )
        ],

        ignore_index=True

    )


    print("")
    print(
        "Added verified 100th Pune location:"
    )

    print(
        "Location:",
        new_location[
            "location"
        ]
    )

    print(
        "Latitude:",
        new_location[
            "latitude"
        ]
    )

    print(
        "Longitude:",
        new_location[
            "longitude"
        ]
    )

    print(
        "Nearest CPCB station:",
        representative
    )


    return locations
