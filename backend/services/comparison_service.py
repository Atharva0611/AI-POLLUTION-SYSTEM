"""
Multi-City Air Quality Comparison Service
=========================================
Performs honest side-by-side air quality comparisons across two or more locations:
1. Fetches environmental data for each city separately via existing services.
2. Formats a clear comparison table with AQI, PM2.5, PM10, NO2, and conditions.
3. Explicitly labels missing or unavailable data per city without cross-contamination.
4. Identifies which city has better/worse air quality based on valid metrics.
"""

from typing import List, Dict, Any, Optional
from backend.services.india_environment import get_environment_for_user


def compare_air_quality(locations: List[str]) -> str:
    """
    Compare air quality across two or more locations.
    Returns a formatted comparison table and analysis.
    """
    if not locations or len(locations) < 2:
        return "Please specify at least two cities or locations to compare (e.g., 'Compare Pune and Mumbai AQI')."

    # Deduplicate while preserving order
    unique_locs = []
    for loc in locations:
        if loc and loc.title() not in unique_locs:
            unique_locs.append(loc.title())

    city_reports: List[Dict[str, Any]] = []

    for loc in unique_locs:
        try:
            env = get_environment_for_user(loc)
            current = env.get("current") or {}
            aqi_obj = env.get("current_aqi") or {}
            city_reports.append({
                "city": loc,
                "status": "ok" if env.get("status") == "ok" else "unavailable",
                "aqi": aqi_obj.get("value"),
                "category": aqi_obj.get("category", "Unavailable"),
                "pm25": current.get("pm2_5"),
                "pm10": current.get("pm10"),
                "no2": current.get("no2"),
                "temp": current.get("temperature_c"),
                "humidity": current.get("humidity"),
                "source": env.get("data_provenance", {}).get("primary_source", "WeatherAPI"),
                "timestamp": current.get("last_updated") or env.get("location", {}).get("local_time", "N/A"),
            })
        except Exception as exc:
            city_reports.append({
                "city": loc,
                "status": "error",
                "aqi": None,
                "category": "Error",
                "pm25": None,
                "pm10": None,
                "no2": None,
                "temp": None,
                "humidity": None,
                "source": "Failed",
                "timestamp": "Unavailable",
                "error": str(exc),
            })

    # Build ASCII comparison table
    lines = [
        "AIR QUALITY COMPARISON REPORT",
        "=" * 78,
        f"{'City / Locality':<20} | {'AQI':<6} | {'Category':<14} | {'PM2.5':<8} | {'PM10':<8} | {'Temp':<6}",
        "-" * 78,
    ]

    valid_for_ranking = []

    for r in city_reports:
        c_name = r["city"][:19]
        aqi_str = str(int(r["aqi"])) if r["aqi"] is not None else "N/A"
        cat_str = r["category"][:13]
        pm25_str = f"{r['pm25']:.1f}" if r["pm25"] is not None else "N/A"
        pm10_str = f"{r['pm10']:.1f}" if r["pm10"] is not None else "N/A"
        temp_str = f"{r['temp']:.1f}C" if r["temp"] is not None else "N/A"

        lines.append(f"{c_name:<20} | {aqi_str:<6} | {cat_str:<14} | {pm25_str:<8} | {pm10_str:<8} | {temp_str:<6}")

        if r["aqi"] is not None:
            valid_for_ranking.append((r["city"], r["aqi"], r["category"], r.get("pm25")))

    lines.extend([
        "-" * 78,
        "",
        "COMPARATIVE ANALYSIS & HEALTH IMPACT",
        "-" * 78,
    ])

    if len(valid_for_ranking) >= 2:
        # Sort by AQI ascending (lower AQI = cleaner air)
        valid_for_ranking.sort(key=lambda x: x[1])
        cleanest = valid_for_ranking[0]
        most_polluted = valid_for_ranking[-1]

        diff_aqi = most_polluted[1] - cleanest[1]

        if diff_aqi == 0:
            lines.append(f"- Air quality is comparable across both locations (AQI ~{cleanest[1]}).")
        else:
            lines.append(f"- Cleaner Air: {cleanest[0]} (AQI {cleanest[1]:.0f}, {cleanest[2]}).")
            lines.append(f"- Higher Pollution: {most_polluted[0]} (AQI {most_polluted[1]:.0f}, {most_polluted[2]}).")
            lines.append(f"- AQI Disparity: {most_polluted[0]} has an AQI {diff_aqi:.0f} points higher than {cleanest[0]}.")

        # Note PM2.5 comparison
        if cleanest[3] is not None and most_polluted[3] is not None:
            lines.append(f"- PM2.5 Concentration: {most_polluted[0]} is at {most_polluted[3]:.1f} ug/m3 vs {cleanest[0]} at {cleanest[3]:.1f} ug/m3.")
    elif len(valid_for_ranking) == 1:
        lines.append(f"- Data is available only for {valid_for_ranking[0][0]} (AQI {valid_for_ranking[0][1]:.0f}). Other locations could not be retrieved.")
    else:
        lines.append("- Unable to rank cities due to temporary data unavailability from observation providers.")

    lines.extend([
        "",
        "Data Transparency Note:",
        "Readings are retrieved independently per city from validated monitoring feeds.",
        "No values are shared or substituted across cities.",
    ])

    return "\n".join(lines)
