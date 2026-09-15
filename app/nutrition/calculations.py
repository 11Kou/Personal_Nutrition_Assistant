from typing import Any


def _success(data: Any, message: str) -> dict[str, Any]:
    return {"status": "success", "data": data, "message": message}


def _error(message: str) -> dict[str, Any]:
    return {"status": "error", "data": None, "message": message}


def _required_number(profile_data: dict[str, Any], key: str) -> float:
    if key not in profile_data:
        raise ValueError(f"Missing required profile field: {key}")
    value = profile_data[key]
    if not isinstance(value, int | float):
        raise TypeError(f"{key} must be a number")
    if value <= 0:
        raise ValueError(f"{key} must be greater than 0")
    return float(value)


def _required_text(profile_data: dict[str, Any], key: str) -> str:
    if key not in profile_data:
        raise ValueError(f"Missing required profile field: {key}")
    value = str(profile_data[key]).strip()
    if not value:
        raise ValueError(f"{key} cannot be empty")
    return value


def _activity_factor(activity_level: str) -> float:
    factors = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9,
    }
    if activity_level not in factors:
        allowed_values = ", ".join(factors.keys())
        raise ValueError(f"activity_level must be one of: {allowed_values}")
    return factors[activity_level]


def _goal_macro_rule(goal: str) -> dict[str, float | str]:
    rules = {
        "fat_loss": {
            "calorie_multiplier": 0.85,
            "protein_g_per_kg": 1.8,
            "fat_g_per_kg": 0.8,
            "description": "15% calorie deficit for fat loss",
        },
        "muscle_gain": {
            "calorie_multiplier": 1.1,
            "protein_g_per_kg": 1.8,
            "fat_g_per_kg": 0.9,
            "description": "10% calorie surplus for muscle gain",
        },
        "maintenance": {
            "calorie_multiplier": 1.0,
            "protein_g_per_kg": 1.6,
            "fat_g_per_kg": 0.8,
            "description": "maintenance calories",
        },
        "wellness": {
            "calorie_multiplier": 1.0,
            "protein_g_per_kg": 1.4,
            "fat_g_per_kg": 0.8,
            "description": "balanced intake for general wellness",
        },
    }
    if goal not in rules:
        allowed_values = ", ".join(rules.keys())
        raise ValueError(f"goal must be one of: {allowed_values}")
    return rules[goal]


def _parse_profile_for_calculation(profile_data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(profile_data, dict):
        raise TypeError("profile_data must be a dictionary")

    age = _required_number(profile_data, "age")
    if age > 120:
        raise ValueError("age must be less than or equal to 120")

    return {
        "height_cm": _required_number(profile_data, "height_cm"),
        "weight_kg": _required_number(profile_data, "weight_kg"),
        "age": age,
        "sex": _required_text(profile_data, "sex"),
        "goal": _required_text(profile_data, "goal"),
        "activity_level": str(profile_data.get("activity_level", "moderate")).strip()
        or "moderate",
    }


def calculate_bmr(profile_data: dict[str, Any]) -> dict[str, Any]:
    """[Agent-Ready] Calculate BMR with the Mifflin-St Jeor equation."""
    try:
        profile = _parse_profile_for_calculation(profile_data)
        sex_offsets = {"male": 5, "female": -161, "other": -78}
        sex = profile["sex"]
        if sex not in sex_offsets:
            raise ValueError("sex must be one of: male, female, other")

        raw_bmr = (
            10 * profile["weight_kg"]
            + 6.25 * profile["height_cm"]
            - 5 * profile["age"]
            + sex_offsets[sex]
        )
        result = round(raw_bmr)

        return _success(
            {
                "name": "BMR",
                "formula": "Mifflin-St Jeor: 10*weight_kg + 6.25*height_cm - 5*age + sex_offset",
                "inputs": {
                    "weight_kg": profile["weight_kg"],
                    "height_cm": profile["height_cm"],
                    "age": profile["age"],
                    "sex": sex,
                    "sex_offset": sex_offsets[sex],
                },
                "result": result,
                "unit": "kcal/day",
            },
            "BMR calculated.",
        )
    except Exception as exc:
        return _error(f"Failed to calculate BMR: {exc}")


def calculate_tdee(
    profile_data: dict[str, Any],
    activity_level: str | None = None,
) -> dict[str, Any]:
    """[Agent-Ready] Calculate TDEE from BMR and activity level."""
    try:
        profile = _parse_profile_for_calculation(profile_data)
        selected_activity_level = (
            str(activity_level).strip() if activity_level is not None else profile["activity_level"]
        )
        factor = _activity_factor(selected_activity_level)

        bmr_result = calculate_bmr(profile_data)
        if bmr_result["status"] == "error":
            return bmr_result

        bmr = bmr_result["data"]["result"]
        tdee = round(bmr * factor)

        return _success(
            {
                "name": "TDEE",
                "formula": "TDEE = BMR * activity_factor",
                "inputs": {
                    "bmr_kcal_per_day": bmr,
                    "activity_level": selected_activity_level,
                    "activity_factor": factor,
                },
                "result": tdee,
                "unit": "kcal/day",
            },
            "TDEE calculated.",
        )
    except Exception as exc:
        return _error(f"Failed to calculate TDEE: {exc}")


def calculate_macro_targets(
    profile_data: dict[str, Any],
    goal: str | None = None,
    activity_level: str | None = None,
) -> dict[str, Any]:
    """[Agent-Ready] Calculate daily calorie and macronutrient targets."""
    try:
        profile = _parse_profile_for_calculation(profile_data)
        selected_goal = str(goal).strip() if goal is not None else profile["goal"]
        rule = _goal_macro_rule(selected_goal)

        tdee_result = calculate_tdee(profile_data, activity_level=activity_level)
        if tdee_result["status"] == "error":
            return tdee_result

        weight_kg = profile["weight_kg"]
        tdee = tdee_result["data"]["result"]
        target_calories = round(tdee * float(rule["calorie_multiplier"]))
        protein_g = round(weight_kg * float(rule["protein_g_per_kg"]), 1)
        fat_g = round(weight_kg * float(rule["fat_g_per_kg"]), 1)
        carbs_g = round(max((target_calories - protein_g * 4 - fat_g * 9) / 4, 0), 1)

        return _success(
            {
                "name": "Macro Targets",
                "formula": "target_calories = TDEE * goal_multiplier; protein = weight_kg * protein_g_per_kg; fat = weight_kg * fat_g_per_kg; carbs = remaining_calories / 4",
                "inputs": {
                    "weight_kg": weight_kg,
                    "goal": selected_goal,
                    "tdee_kcal_per_day": tdee,
                    "calorie_multiplier": rule["calorie_multiplier"],
                    "protein_g_per_kg": rule["protein_g_per_kg"],
                    "fat_g_per_kg": rule["fat_g_per_kg"],
                },
                "result": {
                    "calories_kcal": target_calories,
                    "protein_g": protein_g,
                    "carbs_g": carbs_g,
                    "fat_g": fat_g,
                },
                "unit": "per day",
                "note": rule["description"],
            },
            "Macronutrient targets calculated.",
        )
    except Exception as exc:
        return _error(f"Failed to calculate macro targets: {exc}")
