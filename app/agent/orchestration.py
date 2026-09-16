from typing import Any

from app.food.query import query_food
from app.nutrition.calculations import (
    calculate_bmr,
    calculate_macro_targets,
    calculate_tdee,
)
from app.profile.storage import format_profile_for_prompt, update_user_profile
from app.rag.flow import answer_question_with_rag


def _success(data: Any, message: str) -> dict[str, Any]:
    return {"status": "success", "data": data, "message": message}


def _error(message: str) -> dict[str, Any]:
    return {"status": "error", "data": None, "message": message}


def build_agent_system_prompt(profile_data: dict[str, Any]) -> dict[str, Any]:
    """[Agent-Ready] Build the system prompt with profile pre-injection."""
    try:
        profile_result = format_profile_for_prompt(profile_data)
        if profile_result["status"] == "error":
            return profile_result

        system_prompt = "\n".join(
            [
                "You are a personalized fitness and nutrition assistant.",
                profile_result["data"]["profile_text"],
                "",
                "Rules:",
                "- The user profile is pre-injected. Do not call a profile-read tool.",
                "- If the user updates profile fields, call update_user_profile.",
                "- If the user asks about BMR, TDEE, calorie targets, or macros, call the calculation tools.",
                "- Do not estimate nutrition numbers with the language model.",
                "- If the user asks about a specific food, call query_food.",
                "- If the user asks for knowledge-backed advice, call answer_question_with_rag.",
                "- Final answers should cite sources when RAG sources are available.",
                "- For medical, injury, diagnosis, treatment, or medication questions, suggest consulting a professional.",
            ]
        )
        return _success({"system_prompt": system_prompt}, "Agent system prompt built.")
    except Exception as exc:
        return _error(f"Failed to build agent system prompt: {exc}")


def create_agent_tools(
    database_url_or_path: str,
    food_csv_path: str = "data/food/foods.csv",
    rag_index_dir: str = "data/index",
) -> dict[str, Any]:
    """[Agent-Ready] Create LangChain tools for the delivered Agent-ready functions."""
    try:
        from langchain_core.tools import StructuredTool

        if not str(database_url_or_path).strip():
            raise ValueError("database_url_or_path cannot be empty")
        if not str(food_csv_path).strip():
            raise ValueError("food_csv_path cannot be empty")
        if not str(rag_index_dir).strip():
            raise ValueError("rag_index_dir cannot be empty")

        def update_user_profile_tool(user_id: str, patch: dict[str, Any]) -> dict[str, Any]:
            """Update the persisted user profile with a partial patch."""
            return update_user_profile(database_url_or_path, user_id, patch)

        def calculate_bmr_tool(profile_data: dict[str, Any]) -> dict[str, Any]:
            """Calculate BMR from structured profile data."""
            return calculate_bmr(profile_data)

        def calculate_tdee_tool(
            profile_data: dict[str, Any],
            activity_level: str | None = None,
        ) -> dict[str, Any]:
            """Calculate TDEE from structured profile data and optional activity level."""
            return calculate_tdee(profile_data, activity_level=activity_level)

        def calculate_macro_targets_tool(
            profile_data: dict[str, Any],
            goal: str | None = None,
            activity_level: str | None = None,
        ) -> dict[str, Any]:
            """Calculate calorie and macronutrient targets from profile data."""
            return calculate_macro_targets(
                profile_data,
                goal=goal,
                activity_level=activity_level,
            )

        def query_food_tool(
            food_name: str,
            amount_g: float | None = None,
        ) -> dict[str, Any]:
            """Query local food nutrition data by food name."""
            return query_food(food_name, amount_g=amount_g, csv_path=food_csv_path)

        def answer_question_with_rag_tool(
            question: str,
            profile_data: dict[str, Any],
            top_k: int = 5,
            use_chroma: bool = False,
        ) -> dict[str, Any]:
            """Answer a question with local RAG retrieval and source-grounding."""
            return answer_question_with_rag(
                question=question,
                profile_data=profile_data,
                index_dir=rag_index_dir,
                top_k=top_k,
                use_chroma=use_chroma,
            )

        tools = [
            StructuredTool.from_function(
                func=update_user_profile_tool,
                name="update_user_profile",
                description="Update the persisted user profile when the user says their profile changed.",
            ),
            StructuredTool.from_function(
                func=calculate_bmr_tool,
                name="calculate_bmr",
                description="Calculate BMR with the standard formula. Use for basal metabolism questions.",
            ),
            StructuredTool.from_function(
                func=calculate_tdee_tool,
                name="calculate_tdee",
                description="Calculate TDEE from BMR and activity level. Use for daily energy needs.",
            ),
            StructuredTool.from_function(
                func=calculate_macro_targets_tool,
                name="calculate_macro_targets",
                description="Calculate calorie, protein, carbohydrate, and fat targets. Use for macro questions.",
            ),
            StructuredTool.from_function(
                func=query_food_tool,
                name="query_food",
                description="Look up local CSV food nutrition data. Use for specific food nutrition questions.",
            ),
            StructuredTool.from_function(
                func=answer_question_with_rag_tool,
                name="answer_question_with_rag",
                description="Run the local RAG flow for source-grounded fitness or nutrition advice.",
            ),
        ]

        return _success(
            {
                "tools": tools,
                "tool_names": [tool.name for tool in tools],
            },
            "Agent tools created.",
        )
    except Exception as exc:
        return _error(f"Failed to create agent tools: {exc}")


def bind_tools_to_model(model: Any, tools: list[Any]) -> dict[str, Any]:
    """[Agent-Ready] Bind LangChain tools to a chat model with bind_tools."""
    try:
        if model is None:
            raise ValueError("model cannot be None")
        if not hasattr(model, "bind_tools"):
            raise TypeError("model must provide a bind_tools method")
        if not isinstance(tools, list) or not tools:
            raise ValueError("tools must be a non-empty list")

        bound_model = model.bind_tools(tools)
        return _success({"model": bound_model}, "Tools bound to model.")
    except Exception as exc:
        return _error(f"Failed to bind tools to model: {exc}")


def create_deepseek_chat_model(
    api_key: str,
    base_url: str = "https://api.deepseek.com",
    model_name: str = "deepseek-chat",
    temperature: float = 0,
) -> dict[str, Any]:
    """[Agent-Ready] Create a DeepSeek OpenAI-compatible LangChain chat model."""
    try:
        if not str(api_key).strip():
            raise ValueError("api_key cannot be empty")
        if not str(base_url).strip():
            raise ValueError("base_url cannot be empty")
        if not str(model_name).strip():
            raise ValueError("model_name cannot be empty")

        from langchain_openai import ChatOpenAI

        model = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model_name,
            temperature=temperature,
        )
        return _success({"model": model}, "DeepSeek chat model created.")
    except Exception as exc:
        return _error(f"Failed to create DeepSeek chat model: {exc}")


def prepare_agent_runtime(
    profile_data: dict[str, Any],
    database_url_or_path: str,
    food_csv_path: str = "data/food/foods.csv",
    rag_index_dir: str = "data/index",
) -> dict[str, Any]:
    """[Agent-Ready] Prepare profile-injected prompt and LangChain tools for an agent runtime."""
    try:
        prompt_result = build_agent_system_prompt(profile_data)
        if prompt_result["status"] == "error":
            return prompt_result

        tools_result = create_agent_tools(
            database_url_or_path=database_url_or_path,
            food_csv_path=food_csv_path,
            rag_index_dir=rag_index_dir,
        )
        if tools_result["status"] == "error":
            return tools_result

        return _success(
            {
                "system_prompt": prompt_result["data"]["system_prompt"],
                "tools": tools_result["data"]["tools"],
                "tool_names": tools_result["data"]["tool_names"],
            },
            "Agent runtime prepared.",
        )
    except Exception as exc:
        return _error(f"Failed to prepare agent runtime: {exc}")
