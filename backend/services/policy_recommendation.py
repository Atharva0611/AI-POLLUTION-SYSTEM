def policy_and_recommendation(
    pm25,
    temperature,
    rainfall,
    humidity,
    wind_speed
):

    policy = []
    recommendation = []

    # PM2.5
    if pm25 >= 90:
        policy.append(
            "High-pollution response: strengthen air-quality monitoring and emission-source control."
        )
        recommendation.append(
            "Reduce prolonged outdoor exposure."
        )
        recommendation.append(
            "Inspect traffic, construction and dust sources."
        )

    elif pm25 >= 60:
        policy.append(
            "Elevated pollution response: increase monitoring and local emission-control measures."
        )
        recommendation.append(
            "Limit unnecessary prolonged outdoor activity."
        )

    elif pm25 >= 35:
        policy.append(
            "Enhanced monitoring recommended for elevated PM2.5."
        )
        recommendation.append(
            "Continue routine monitoring and source inspection."
        )

    else:
        policy.append(
            "Routine air-quality monitoring."
        )
        recommendation.append(
            "Normal outdoor activity with routine monitoring."
        )

    # Heat
    if temperature >= 35:
        policy.append(
            "Heat-exposure precautions should be activated."
        )
        recommendation.append(
            "Stay hydrated and reduce prolonged outdoor exposure."
        )

    # Rain
    if rainfall >= 10:
        policy.append(
            "Heavy-rain monitoring should include drainage and waterlogging."
        )
        recommendation.append(
            "Monitor flooding, drainage and traffic conditions."
        )

    # Low wind
    if wind_speed <= 2 and pm25 >= 60:
        policy.append(
            "Increase short-term pollution monitoring because dispersion may be limited."
        )
        recommendation.append(
            "Closely monitor nearby emission sources."
        )

    return {
        "policy": list(dict.fromkeys(policy)),
        "recommendations": list(
            dict.fromkeys(recommendation)
        )
    }


if __name__ == "__main__":

    result = policy_and_recommendation(
        pm25=84.22,
        temperature=18.9,
        rainfall=0,
        humidity=95,
        wind_speed=2.39
    )

    print("\nPOLICY")
    print("-" * 60)

    for x in result["policy"]:
        print("-", x)

    print("\nRECOMMENDATIONS")
    print("-" * 60)

    for x in result["recommendations"]:
        print("-", x)
