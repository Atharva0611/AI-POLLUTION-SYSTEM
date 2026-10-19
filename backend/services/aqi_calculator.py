# Add CPCB-style AQI estimation from pollutant concentrations.
# WeatherAPI provides pollutant concentrations and its own US EPA / UK DEFRA
# indexes; this function does NOT pretend those indexes are CPCB AQI.

def calculate_aqi_from_pm25(pm25):

    if pm25 is None:
        return None

    pm25 = float(pm25)

    # Project AQI calculation using PM2.5 breakpoints.
    breakpoints = [
        (0.0, 30.0, 0, 50),
        (30.1, 60.0, 51, 100),
        (60.1, 90.0, 101, 200),
        (90.1, 120.0, 201, 300),
        (120.1, 250.0, 301, 400),
        (250.1, 500.0, 401, 500),
    ]

    for c_low, c_high, i_low, i_high in breakpoints:

        if c_low <= pm25 <= c_high:

            return round(
                (
                    (i_high - i_low)
                    / (c_high - c_low)
                )
                * (pm25 - c_low)
                + i_low
            )

    return 500


def get_aqi_category(aqi):

    if aqi is None:
        return "Unavailable"

    if aqi <= 50:
        return "Good"

    if aqi <= 100:
        return "Satisfactory"

    if aqi <= 200:
        return "Moderate"

    if aqi <= 300:
        return "Poor"

    if aqi <= 400:
        return "Very Poor"

    return "Severe"
