from app.nutrition.calculations import (
    calculate_bmr,
    calculate_macro_targets,
    calculate_tdee,
)


def assert_result_shape(result):
    assert set(result.keys()) == {"status", "data", "message"}
    assert result["status"] in {"success", "error"}
    assert isinstance(result["message"], str)


def sample_profile():
    return {
        "user_id": "user-1",
        "height_cm": 175,
        "weight_kg": 72,
        "body_fat_percent": 18,
        "age": 28,
        "sex": "male",
        "goal": "fat_loss",
        "injuries": ["knee pain"],
        "diet_preferences": ["lactose intolerant"],
        "training_conditions": ["home", "dumbbell"],
        "activity_level": "moderate",
    }


def test_calculate_bmr_for_male_profile():
    result = calculate_bmr(sample_profile())

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["result"] == 1679
    assert result["data"]["unit"] == "kcal/day"
    assert "Mifflin-St Jeor" in result["data"]["formula"]


def test_calculate_bmr_for_female_profile():
    profile = sample_profile()
    profile["sex"] = "female"

    result = calculate_bmr(profile)

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["result"] == 1513
    assert result["data"]["inputs"]["sex_offset"] == -161


def test_calculate_bmr_for_other_profile_uses_neutral_offset():
    profile = sample_profile()
    profile["sex"] = "other"

    result = calculate_bmr(profile)

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["result"] == 1596
    assert result["data"]["inputs"]["sex_offset"] == -78


def test_calculate_bmr_rejects_invalid_profile():
    profile = sample_profile()
    profile["weight_kg"] = 0

    result = calculate_bmr(profile)

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None


def test_calculate_tdee_uses_profile_activity_level():
    result = calculate_tdee(sample_profile())

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["result"] == 2602
    assert result["data"]["inputs"]["activity_level"] == "moderate"
    assert result["data"]["inputs"]["activity_factor"] == 1.55


def test_calculate_tdee_accepts_activity_override():
    result = calculate_tdee(sample_profile(), activity_level="light")

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["result"] == 2309
    assert result["data"]["inputs"]["activity_level"] == "light"


def test_calculate_tdee_rejects_unknown_activity_level():
    result = calculate_tdee(sample_profile(), activity_level="extreme")

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None


def test_calculate_macro_targets_for_fat_loss():
    result = calculate_macro_targets(sample_profile())

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["result"] == {
        "calories_kcal": 2212,
        "protein_g": 129.6,
        "carbs_g": 293.8,
        "fat_g": 57.6,
    }
    assert result["data"]["inputs"]["goal"] == "fat_loss"


def test_calculate_macro_targets_accepts_goal_override():
    result = calculate_macro_targets(sample_profile(), goal="muscle_gain")

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["result"]["calories_kcal"] == 2862
    assert result["data"]["result"]["protein_g"] == 129.6
    assert result["data"]["result"]["fat_g"] == 64.8


def test_calculate_macro_targets_rejects_unknown_goal():
    result = calculate_macro_targets(sample_profile(), goal="cut_fast")

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None


def test_calculate_macro_targets_rejects_non_dict_profile():
    result = calculate_macro_targets(None)

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None
