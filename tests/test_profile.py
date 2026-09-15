from app.profile.storage import (
    create_user_profile,
    delete_user_profile,
    format_profile_for_prompt,
    get_user_profile,
    initialize_profile_storage,
    list_user_profiles,
    update_user_profile,
)


def assert_result_shape(result):
    assert set(result.keys()) == {"status", "data", "message"}
    assert result["status"] in {"success", "error"}
    assert isinstance(result["message"], str)


def sample_profile(user_id="user-1"):
    return {
        "user_id": user_id,
        "height_cm": 175,
        "weight_kg": 72,
        "body_fat_percent": 18,
        "age": 28,
        "sex": "male",
        "goal": "fat_loss",
        "injuries": ["knee pain", "knee pain", " "],
        "diet_preferences": ["lactose intolerant"],
        "training_conditions": ["home", "dumbbell"],
        "activity_level": "moderate",
    }


def test_initialize_profile_storage_creates_database(tmp_path):
    database_path = tmp_path / "profiles.db"
    result = initialize_profile_storage(database_path)

    assert_result_shape(result)
    assert result["status"] == "success"
    assert database_path.exists()


def test_create_and_get_user_profile(tmp_path):
    database_path = tmp_path / "profiles.db"
    create_result = create_user_profile(database_path, sample_profile())
    get_result = get_user_profile(database_path, "user-1")

    assert_result_shape(create_result)
    assert_result_shape(get_result)
    assert create_result["status"] == "success"
    assert get_result["status"] == "success"
    assert get_result["data"]["user_id"] == "user-1"
    assert get_result["data"]["injuries"] == ["knee pain"]


def test_create_user_profile_rejects_invalid_input(tmp_path):
    database_path = tmp_path / "profiles.db"
    invalid_profile = sample_profile()
    invalid_profile["weight_kg"] = -1

    result = create_user_profile(database_path, invalid_profile)

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None


def test_create_user_profile_rejects_duplicate_user_id(tmp_path):
    database_path = tmp_path / "profiles.db"

    first_result = create_user_profile(database_path, sample_profile())
    second_result = create_user_profile(database_path, sample_profile())

    assert_result_shape(first_result)
    assert_result_shape(second_result)
    assert first_result["status"] == "success"
    assert second_result["status"] == "error"


def test_update_user_profile_accepts_partial_patch(tmp_path):
    database_path = tmp_path / "profiles.db"
    create_user_profile(database_path, sample_profile())

    result = update_user_profile(
        database_path,
        "user-1",
        {"weight_kg": 70, "goal": "maintenance", "injuries": ["ankle"]},
    )

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["weight_kg"] == 70
    assert result["data"]["goal"] == "maintenance"
    assert result["data"]["injuries"] == ["ankle"]


def test_update_user_profile_rejects_invalid_patch(tmp_path):
    database_path = tmp_path / "profiles.db"
    create_user_profile(database_path, sample_profile())

    result = update_user_profile(database_path, "user-1", {"age": 0})

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None


def test_update_user_profile_returns_error_for_missing_user(tmp_path):
    database_path = tmp_path / "profiles.db"

    result = update_user_profile(database_path, "missing", {"weight_kg": 70})

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None


def test_list_user_profiles_returns_profiles_in_order(tmp_path):
    database_path = tmp_path / "profiles.db"
    create_user_profile(database_path, sample_profile("user-b"))
    create_user_profile(database_path, sample_profile("user-a"))

    result = list_user_profiles(database_path)

    assert_result_shape(result)
    assert result["status"] == "success"
    assert [profile["user_id"] for profile in result["data"]] == ["user-a", "user-b"]


def test_delete_user_profile_removes_existing_profile(tmp_path):
    database_path = tmp_path / "profiles.db"
    create_user_profile(database_path, sample_profile())

    delete_result = delete_user_profile(database_path, "user-1")
    get_result = get_user_profile(database_path, "user-1")

    assert_result_shape(delete_result)
    assert_result_shape(get_result)
    assert delete_result["status"] == "success"
    assert get_result["status"] == "error"


def test_get_user_profile_rejects_empty_user_id(tmp_path):
    database_path = tmp_path / "profiles.db"

    result = get_user_profile(database_path, " ")

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None


def test_format_profile_for_prompt_returns_prompt_text():
    result = format_profile_for_prompt(sample_profile())

    assert_result_shape(result)
    assert result["status"] == "success"
    assert "Current user profile:" in result["data"]["profile_text"]
    assert "knee pain" in result["data"]["profile_text"]
    assert "lactose intolerant" in result["data"]["profile_text"]


def test_format_profile_for_prompt_rejects_invalid_profile():
    result = format_profile_for_prompt({"user_id": ""})

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None
