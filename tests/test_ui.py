from app.ui.actions import (
    ask_question_from_ui,
    get_ui_settings,
    ingest_documents_from_ui,
    load_profile_for_ui,
    save_profile_from_form,
)


def assert_result_shape(result):
    assert set(result.keys()) == {"status", "data", "message"}
    assert result["status"] in {"success", "error"}
    assert isinstance(result["message"], str)


def sample_profile(user_id="demo-user"):
    return {
        "user_id": user_id,
        "height_cm": 175,
        "weight_kg": 72,
        "body_fat_percent": 18,
        "age": 28,
        "sex": "male",
        "goal": "fat_loss",
        "injuries": ["膝伤"],
        "diet_preferences": ["乳糖不耐"],
        "training_conditions": ["居家"],
        "activity_level": "moderate",
    }


def write_doc(path):
    path.write_text(
        "\n".join(
            [
                "---",
                "title: 膝伤训练",
                "training_conditions: [居家]",
                "---",
                "# 膝伤训练",
                "膝伤用户可以选择固定自行车和核心训练，避免疼痛加重。",
            ]
        ),
        encoding="utf-8",
    )


def test_get_ui_settings_returns_required_paths(tmp_path):
    result = get_ui_settings(
        overrides={
            "database_url": f"sqlite:///{tmp_path / 'app.db'}",
            "documents_dir": tmp_path / "docs",
            "chroma_dir": tmp_path / "chroma",
            "food_csv_path": "data/food/foods.csv",
        }
    )

    assert_result_shape(result)
    assert result["status"] == "success"
    assert set(result["data"].keys()) == {
        "database_url",
        "documents_dir",
        "chroma_dir",
        "food_csv_path",
    }


def test_save_profile_from_form_creates_and_updates_profile(tmp_path):
    database_path = tmp_path / "profiles.db"

    create_result = save_profile_from_form(str(database_path), sample_profile())
    update_data = sample_profile()
    update_data["weight_kg"] = 70
    update_result = save_profile_from_form(str(database_path), update_data)

    assert_result_shape(create_result)
    assert_result_shape(update_result)
    assert create_result["status"] == "success"
    assert update_result["status"] == "success"
    assert update_result["data"]["weight_kg"] == 70


def test_save_profile_from_form_rejects_missing_user_id(tmp_path):
    profile = sample_profile("")

    result = save_profile_from_form(str(tmp_path / "profiles.db"), profile)

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None


def test_load_profile_for_ui_returns_saved_profile(tmp_path):
    database_path = tmp_path / "profiles.db"
    save_profile_from_form(str(database_path), sample_profile())

    result = load_profile_for_ui(str(database_path), "demo-user")

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["user_id"] == "demo-user"


def test_ingest_documents_from_ui_indexes_directory(tmp_path):
    docs_dir = tmp_path / "docs"
    index_dir = tmp_path / "index"
    docs_dir.mkdir()
    write_doc(docs_dir / "knee.md")

    result = ingest_documents_from_ui([docs_dir], index_dir=index_dir, use_chroma=False)

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["chunk_count"] >= 1


def test_ask_question_from_ui_returns_rag_answer(tmp_path):
    docs_dir = tmp_path / "docs"
    index_dir = tmp_path / "index"
    docs_dir.mkdir()
    write_doc(docs_dir / "knee.md")
    ingest_documents_from_ui([docs_dir], index_dir=index_dir, use_chroma=False)

    result = ask_question_from_ui(
        question="膝伤用户怎么训练？",
        profile_data=sample_profile(),
        index_dir=index_dir,
        use_chroma=False,
    )

    assert_result_shape(result)
    assert result["status"] == "success"
    assert "固定自行车" in result["data"]["answer"]
    assert result["data"]["sources"]


def test_ask_question_from_ui_rejects_missing_index(tmp_path):
    result = ask_question_from_ui(
        question="膝伤用户怎么训练？",
        profile_data=sample_profile(),
        index_dir=tmp_path / "missing",
        use_chroma=False,
    )

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None
