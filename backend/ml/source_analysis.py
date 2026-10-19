from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(r"C:\final year project\AI-POLLUTION-SYSTEM")

DATA_FILE = ROOT / "data" / "processed" / "pune_cpcb_features.csv"
OUTPUT_DIR = ROOT / "data" / "processed" / "source_analysis"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


def normalize(text):
    return (
        str(text)
        .lower()
        .strip()
        .replace("_", " ")
        .replace("-", " ")
    )


def find_column(df, patterns):

    for column in df.columns:

        name = normalize(column)

        for pattern in patterns:

            if pattern in name:
                return column

    return None


def load_data():

    return pd.read_csv(
        DATA_FILE
    )


def station_data(df, station):

    if "station_name" not in df.columns:
        raise ValueError(
            "station_name column not found."
        )

    target = normalize(station)

    df["_key"] = (
        df["station_name"]
        .astype(str)
        .map(normalize)
    )

    result = df[
        df["_key"] == target
    ].copy()

    if result.empty:
        raise ValueError(
            f"No data found for station: {station}"
        )

    return result


def correlation_score(
    df,
    pollutant_column
):

    pm25_col = find_column(
        df,
        [
            "pm2.5",
            "pm25",
            "pm 2.5",
        ]
    )

    if not pm25_col:
        return None

    if not pollutant_column:
        return None

    data = df[
        [
            pm25_col,
            pollutant_column
        ]
    ].apply(
        pd.to_numeric,
        errors="coerce"
    ).dropna()

    if len(data) < 10:
        return None

    correlation = data.iloc[:, 0].corr(
        data.iloc[:, 1],
        method="spearman"
    )

    return float(correlation)


def analyze_source_indicators(
    station=None
):

    df = load_data()

    if station:
        df = station_data(
            df,
            station
        )

    indicators = []

    # --------------------------------------------------------
    # Traffic-related indicators
    # --------------------------------------------------------

    no2 = find_column(
        df,
        ["no2"]
    )

    co = find_column(
        df,
        ["co"]
    )

    traffic_values = []

    for col in [no2, co]:

        score = correlation_score(
            df,
            col
        )

        if score is not None:
            traffic_values.append(
                abs(score)
            )

    if traffic_values:

        indicators.append({
            "source_indicator": "Traffic / combustion",
            "evidence_variables": "NO2, CO",
            "score": float(
                np.mean(traffic_values)
            ),
            "interpretation":
                "PM2.5 relationship with traffic/combustion proxy pollutants.",
        })

    # --------------------------------------------------------
    # Dust-related indicators
    # --------------------------------------------------------

    pm10 = find_column(
        df,
        [
            "pm10",
            "pm 10"
        ]
    )

    dust_score = correlation_score(
        df,
        pm10
    )

    if dust_score is not None:

        indicators.append({
            "source_indicator": "Dust / coarse particulate",
            "evidence_variables": "PM10",
            "score": abs(dust_score),
            "interpretation":
                "PM2.5 relationship with PM10 as a particulate/dust indicator.",
        })

    # --------------------------------------------------------
    # Industrial / combustion indicators
    # --------------------------------------------------------

    so2 = find_column(
        df,
        ["so2"]
    )

    industrial_values = []

    for col in [so2, no2]:

        score = correlation_score(
            df,
            col
        )

        if score is not None:
            industrial_values.append(
                abs(score)
            )

    if industrial_values:

        indicators.append({
            "source_indicator": "Industrial / combustion",
            "evidence_variables": "SO2, NO2",
            "score": float(
                np.mean(industrial_values)
            ),
            "interpretation":
                "Relationship with combustion-related gaseous pollutants.",
        })

    # --------------------------------------------------------
    # Meteorological dispersion
    # --------------------------------------------------------

    wind = find_column(
        df,
        [
            "wind speed",
            "wind_speed",
            "ws "
        ]
    )

    wind_score = correlation_score(
        df,
        wind
    )

    if wind_score is not None:

        indicators.append({
            "source_indicator": "Meteorological dispersion",
            "evidence_variables": "Wind speed",
            "score": abs(wind_score),
            "interpretation":
                "Relationship between PM2.5 and atmospheric dispersion conditions.",
        })

    result = pd.DataFrame(
        indicators
    )

    if not result.empty:

        result = result.sort_values(
            "score",
            ascending=False
        )

    output_name = (
        "source_analysis_all.csv"
        if station is None
        else (
            "source_analysis_"
            + normalize(station).replace(
                " ",
                "_"
            )
            + ".csv"
        )
    )

    output_file = (
        OUTPUT_DIR / output_name
    )

    result.to_csv(
        output_file,
        index=False
    )

    return {
        "station": station,
        "indicators": result.to_dict(
            "records"
        ),
        "output_file": str(
            output_file
        ),
        "note":
            "These are statistical source indicators, not definitive chemical source apportionment.",
    }


if __name__ == "__main__":

    station = input(
        "Station (leave blank for all): "
    ).strip()

    station = station or None

    try:

        result = analyze_source_indicators(
            station
        )

        print("\nSOURCE ANALYSIS")
        print("=" * 70)

        for item in result["indicators"]:

            print(
                f"{item['source_indicator']} | "
                f"score={item['score']:.4f}"
            )

            print(
                f"  Variables: "
                f"{item['evidence_variables']}"
            )

        print(
            "\nSaved:",
            result["output_file"]
        )

        print(
            "\nNOTE:",
            result["note"]
        )

    except Exception as exc:

        print(
            f"ERROR: {type(exc).__name__}: {exc}"
        )
