import os
import pandas as pd

from backend.services.weather_service import get_current_weather


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

    df = pd.read_csv(DATA_PATH)

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce"
    )

    return df


def get_station_data(station_name: str):

    df = load_pollution_data()

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

    return station_df.sort_values(
        "timestamp"
    )


def get_latest_station_record(station_name: str):

    station_df = get_station_data(
        station_name
    )

    return station_df.iloc[-1].to_dict()


def create_state(
    question: str,
    station_name: str
):

    # CPCB pollution data
    pollution = get_latest_station_record(
        station_name
    )

    # Live weather
    weather = get_current_weather(
        "Pune"
    )

    # Merge both
    input_data = {
        **pollution,
        "temperature": weather["temperature"],
        "humidity": weather["humidity"],
        "wind_speed": weather["wind_speed_ms"],
        "wind_direction": weather["wind_direction"],
        "rainfall": weather["rainfall"],
    }

    return {
        "question": question,
        "station_name": station_name,
        "input_data": input_data,
        "error": None
    }


if __name__ == "__main__":

    station = input(
        "Enter station name: "
    )

    state = create_state(
        question="Test weather integration",
        station_name=station
    )

    print("\n=== LIVE INPUT DATA ===")

    for key, value in state["input_data"].items():
        print(f"{key}: {value}")