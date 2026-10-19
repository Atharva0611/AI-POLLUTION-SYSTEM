def calculate_pm25_indicative_aqi(pm25):
    """
    PM2.5-only indicative AQI using CPCB PM2.5 breakpoint ranges.

    This is NOT the official overall CPCB AQI because the official
    AQI requires multiple pollutants and appropriate averaging periods.
    """

    if pm25 is None:
        return None, "Unavailable"

    try:
        pm25 = float(pm25)
    except (TypeError, ValueError):
        return None, "Unavailable"

    if pm25 < 0:
        return None, "Invalid"

    # CPCB PM2.5 health-breakpoint ranges
    concentration = [0, 30, 60, 90, 120, 250, 500]
    index = [0, 50, 100, 200, 300, 400, 500]

    if pm25 >= 500:
        return 500, "Severe"

    for i in range(len(concentration) - 1):

        c_low = concentration[i]
        c_high = concentration[i + 1]

        if c_low <= pm25 <= c_high:

            i_low = index[i]
            i_high = index[i + 1]

            aqi = (
                ((i_high - i_low) /
                 (c_high - c_low))
                * (pm25 - c_low)
            ) + i_low

            aqi = round(aqi, 1)

            if aqi <= 50:
                category = "Good"
            elif aqi <= 100:
                category = "Satisfactory"
            elif aqi <= 200:
                category = "Moderately Polluted"
            elif aqi <= 300:
                category = "Poor"
            elif aqi <= 400:
                category = "Very Poor"
            else:
                category = "Severe"

            return aqi, category

    return None, "Unavailable"


def enrich_environment_with_aqi(data):

    if not isinstance(data, dict):
        return data

    current = data.get(
        "current",
        {}
    )

    if not isinstance(current, dict):
        return data

    pm25 = current.get("pm2_5")

    aqi, category = calculate_pm25_indicative_aqi(
        pm25
    )

    current["aqi"] = aqi
    current["aqi_category"] = category
    current["aqi_basis"] = (
        "PM2.5-only indicative estimate; "
        "not official CPCB overall AQI"
    )

    data["current"] = current

    return data
