import os
import pandas as pd


CURRENT_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

PROJECT_ROOT = os.path.abspath(
    os.path.join(
        CURRENT_DIR,
        "..",
        ".."
    )
)

DATA_PATH = os.path.join(
    PROJECT_ROOT,
    "data",
    "processed",
    "pune_cpcb_cleaned_hourly.csv"
)


def load_pollution_data():

    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(
            f"Dataset not found:\n{DATA_PATH}"
        )

    df = pd.read_csv(
        DATA_PATH
    )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce"
    )

    return df


def get_station_data(
    station_name: str
):

    df = load_pollution_data()

    if "station_name" not in df.columns:
        raise ValueError(
            "station_name column not found."
        )

    station_df = df[
        df["station_name"]
        .astype(str)
        .str.strip()
        .str.lower()
        == station_name.strip().lower()
    ].copy()

    if station_df.empty:
        raise ValueError(
            f"Station not found: {station_name}"
        )

    station_df = station_df.sort_values(
        "timestamp"
    )

    return station_df


def get_latest_station_record(
    station_name: str
):

    station_df = get_station_data(
        station_name
    )

    latest = station_df.iloc[-1]

    return latest.to_dict()


def create_state(
    question: str,
    station_name: str
):

    latest_data = get_latest_station_record(
        station_name
    )

    return {
        "question": question,
        "station_name": station_name,
        "input_data": latest_data,
        "error": None
    }


if __name__ == "__main__":

    print(
        "Input Service"
    )

    station = input(
        "Enter station name: "
    )

    try:

        state = create_state(
            question="Test pollution analysis",
            station_name=station
        )

        print("\nSTATE CREATED:")
        print(state)

    except Exception as e:

        print("\nERROR:")
        print(e)