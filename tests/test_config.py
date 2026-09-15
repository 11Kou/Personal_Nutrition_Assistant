from pathlib import Path

from app.core.config import get_project_paths, load_app_settings


def assert_result_shape(result):
    assert set(result.keys()) == {"status", "data", "message"}
    assert result["status"] in {"success", "error"}
    assert isinstance(result["message"], str)


def test_load_app_settings_with_defaults():
    result = load_app_settings(env_file=None)

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["app_name"] == "Personal Nutrition Assistant"
    assert result["data"]["llm_base_url"] == "https://api.deepseek.com"
    assert result["data"]["embedding_model_name"] == "BAAI/bge-small-zh-v1.5"
    assert result["data"]["reranker_model_name"] == "BAAI/bge-reranker-base"


def test_load_app_settings_with_overrides():
    result = load_app_settings(
        env_file=None,
        overrides={
            "environment": "test",
            "debug": False,
            "data_dir": Path("tmp_data"),
        },
    )

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["environment"] == "test"
    assert result["data"]["debug"] is False
    assert result["data"]["data_dir"] == "tmp_data"


def test_load_app_settings_returns_error_for_invalid_overrides():
    result = load_app_settings(env_file=None, overrides="bad input")

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None


def test_get_project_paths_with_valid_settings():
    settings_result = load_app_settings(env_file=None)
    result = get_project_paths(settings_result["data"])

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"] == {
        "data_dir": "data",
        "food_csv_path": "data\\food\\foods.csv",
        "documents_dir": "data\\documents",
        "chroma_dir": "data\\chroma",
    }


def test_get_project_paths_returns_error_for_missing_keys():
    result = get_project_paths({"data_dir": "data"})

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None


def test_get_project_paths_returns_error_for_wrong_input_type():
    result = get_project_paths(None)

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None
