from app.agent.orchestration import (
    bind_tools_to_model,
    build_agent_system_prompt,
    create_agent_tools,
    create_deepseek_chat_model,
    prepare_agent_runtime,
)
from app.profile.storage import create_user_profile


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
        "injuries": ["膝伤"],
        "diet_preferences": ["乳糖不耐"],
        "training_conditions": ["居家"],
        "activity_level": "moderate",
    }


class FakeChatModel:
    def __init__(self):
        self.bound_tools = None

    def bind_tools(self, tools):
        self.bound_tools = tools
        return {"bound_tools": tools}


def test_build_agent_system_prompt_preinjects_profile():
    result = build_agent_system_prompt(sample_profile())

    assert_result_shape(result)
    assert result["status"] == "success"
    assert "Current user profile:" in result["data"]["system_prompt"]
    assert "Do not call a profile-read tool" in result["data"]["system_prompt"]
    assert "calculate_bmr" not in result["data"]["system_prompt"]
    assert "calculation tools" in result["data"]["system_prompt"]


def test_build_agent_system_prompt_rejects_invalid_profile():
    result = build_agent_system_prompt({"user_id": ""})

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None


def test_create_agent_tools_returns_expected_tool_names(tmp_path):
    result = create_agent_tools(
        database_url_or_path=str(tmp_path / "profiles.db"),
        food_csv_path="data/food/foods.csv",
        rag_index_dir=str(tmp_path / "index"),
    )

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["tool_names"] == [
        "update_user_profile",
        "calculate_bmr",
        "calculate_tdee",
        "calculate_macro_targets",
        "query_food",
        "answer_question_with_rag",
    ]


def test_agent_calculation_tool_invokes_agent_ready_function(tmp_path):
    tools_result = create_agent_tools(
        database_url_or_path=str(tmp_path / "profiles.db"),
        food_csv_path="data/food/foods.csv",
        rag_index_dir=str(tmp_path / "index"),
    )
    tool_by_name = {tool.name: tool for tool in tools_result["data"]["tools"]}

    result = tool_by_name["calculate_bmr"].invoke({"profile_data": sample_profile()})

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["result"] == 1679


def test_agent_food_tool_invokes_query_food(tmp_path):
    tools_result = create_agent_tools(
        database_url_or_path=str(tmp_path / "profiles.db"),
        food_csv_path="data/food/foods.csv",
        rag_index_dir=str(tmp_path / "index"),
    )
    tool_by_name = {tool.name: tool for tool in tools_result["data"]["tools"]}

    result = tool_by_name["query_food"].invoke({"food_name": "鸡胸肉", "amount_g": 100})

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["matched_name"] == "鸡胸肉"


def test_agent_update_profile_tool_invokes_storage(tmp_path):
    database_path = tmp_path / "profiles.db"
    create_user_profile(database_path, sample_profile())
    tools_result = create_agent_tools(
        database_url_or_path=str(database_path),
        food_csv_path="data/food/foods.csv",
        rag_index_dir=str(tmp_path / "index"),
    )
    tool_by_name = {tool.name: tool for tool in tools_result["data"]["tools"]}

    result = tool_by_name["update_user_profile"].invoke(
        {"user_id": "user-1", "patch": {"weight_kg": 70}}
    )

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["weight_kg"] == 70


def test_bind_tools_to_model_uses_bind_tools(tmp_path):
    tools_result = create_agent_tools(
        database_url_or_path=str(tmp_path / "profiles.db"),
        food_csv_path="data/food/foods.csv",
        rag_index_dir=str(tmp_path / "index"),
    )
    model = FakeChatModel()

    result = bind_tools_to_model(model, tools_result["data"]["tools"])

    assert_result_shape(result)
    assert result["status"] == "success"
    assert model.bound_tools == tools_result["data"]["tools"]
    assert result["data"]["model"]["bound_tools"] == tools_result["data"]["tools"]


def test_bind_tools_to_model_rejects_model_without_bind_tools(tmp_path):
    tools_result = create_agent_tools(
        database_url_or_path=str(tmp_path / "profiles.db"),
        food_csv_path="data/food/foods.csv",
        rag_index_dir=str(tmp_path / "index"),
    )

    result = bind_tools_to_model(object(), tools_result["data"]["tools"])

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None


def test_create_deepseek_chat_model_rejects_empty_api_key():
    result = create_deepseek_chat_model(api_key="")

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None


def test_prepare_agent_runtime_returns_prompt_and_tools(tmp_path):
    result = prepare_agent_runtime(
        profile_data=sample_profile(),
        database_url_or_path=str(tmp_path / "profiles.db"),
        food_csv_path="data/food/foods.csv",
        rag_index_dir=str(tmp_path / "index"),
    )

    assert_result_shape(result)
    assert result["status"] == "success"
    assert "Current user profile:" in result["data"]["system_prompt"]
    assert len(result["data"]["tools"]) == 6
    assert "update_user_profile" in result["data"]["tool_names"]
