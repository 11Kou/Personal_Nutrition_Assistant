from pathlib import Path
import sqlite3
from typing import Any

from app.core.config import load_app_settings
from app.profile.storage import (
    create_user_profile,
    get_user_profile,
    list_user_profiles,
    update_user_profile,
)
from app.llm.deepseek import generate_deepseek_rag_answer
from app.rag.flow import answer_question_with_rag
from app.retrieval.documents import ingest_documents


def _success(data: Any, message: str) -> dict[str, Any]:
    return {"status": "success", "data": data, "message": message}


def _error(message: str) -> dict[str, Any]:
    return {"status": "error", "data": None, "message": message}


def _resolve_sqlite_path(database_url_or_path: str | Path) -> Path:
    raw_value = str(database_url_or_path).strip()
    if not raw_value:
        raise ValueError("database_url_or_path cannot be empty")
    if raw_value.startswith("sqlite:///"):
        raw_value = raw_value.removeprefix("sqlite:///")
    if raw_value.startswith("sqlite://"):
        raise ValueError("Only sqlite:/// file URLs are supported")
    return Path(raw_value)


def _connect(database_url_or_path: str | Path) -> sqlite3.Connection:
    database_path = _resolve_sqlite_path(database_url_or_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


def _ensure_question_history_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ui_question_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            question TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.commit()


def get_ui_settings(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """[Agent-Ready] Load settings needed by the Streamlit UI."""
    try:
        settings_result = load_app_settings(overrides=overrides)
        if settings_result["status"] == "error":
            return settings_result
        settings = settings_result["data"]
        return _success(
            {
                "database_url": settings["database_url"],
                "documents_dir": settings["documents_dir"],
                "chroma_dir": settings["chroma_dir"],
                "food_csv_path": settings["food_csv_path"],
                "llm_base_url": settings["llm_base_url"],
                "llm_api_key": settings["llm_api_key"],
                "llm_model": settings["llm_model"],
            },
            "UI settings loaded.",
        )
    except Exception as exc:
        return _error(f"Failed to load UI settings: {exc}")


def save_profile_from_form(
    database_url_or_path: str,
    profile_data: dict[str, Any],
) -> dict[str, Any]:
    """[Agent-Ready] Create or update a user profile from UI form data."""
    try:
        user_id = str(profile_data.get("user_id", "")).strip()
        if not user_id:
            raise ValueError("user_id cannot be empty")

        existing_result = get_user_profile(database_url_or_path, user_id)
        if existing_result["status"] == "success":
            patch = {key: value for key, value in profile_data.items() if key != "user_id"}
            return update_user_profile(database_url_or_path, user_id, patch)
        return create_user_profile(database_url_or_path, profile_data)
    except Exception as exc:
        return _error(f"Failed to save profile from form: {exc}")


def load_profile_for_ui(database_url_or_path: str, user_id: str) -> dict[str, Any]:
    """[Agent-Ready] Load a profile for display in the UI."""
    try:
        return get_user_profile(database_url_or_path, user_id)
    except Exception as exc:
        return _error(f"Failed to load profile for UI: {exc}")


def record_question_from_ui(
    database_url_or_path: str | Path,
    user_id: str,
    question: str,
) -> dict[str, Any]:
    """[Agent-Ready] Persist a question for the UI profile list."""
    try:
        cleaned_user_id = str(user_id).strip()
        cleaned_question = str(question).strip()
        if not cleaned_user_id:
            raise ValueError("user_id cannot be empty")
        if not cleaned_question:
            raise ValueError("question cannot be empty")

        with _connect(database_url_or_path) as connection:
            _ensure_question_history_schema(connection)
            connection.execute(
                "INSERT INTO ui_question_history (user_id, question) VALUES (?, ?)",
                (cleaned_user_id, cleaned_question),
            )
            connection.commit()

        return _success(
            {"user_id": cleaned_user_id, "question": cleaned_question},
            "Question recorded.",
        )
    except Exception as exc:
        return _error(f"Failed to record question: {exc}")


def list_profile_sidebar_items(
    database_url_or_path: str | Path,
    questions_per_user: int = 3,
) -> dict[str, Any]:
    """[Agent-Ready] List profile IDs with recent UI question history."""
    try:
        if questions_per_user <= 0:
            raise ValueError("questions_per_user must be greater than 0")

        profiles_result = list_user_profiles(database_url_or_path)
        if profiles_result["status"] == "error":
            return profiles_result

        with _connect(database_url_or_path) as connection:
            _ensure_question_history_schema(connection)
            rows = connection.execute(
                """
                SELECT user_id, question, created_at
                FROM ui_question_history
                ORDER BY datetime(created_at) DESC, id DESC
                """
            ).fetchall()

        questions_by_user: dict[str, list[dict[str, str]]] = {}
        for row in rows:
            user_questions = questions_by_user.setdefault(row["user_id"], [])
            if len(user_questions) < questions_per_user:
                user_questions.append(
                    {
                        "question": row["question"],
                        "created_at": row["created_at"],
                    }
                )

        items = [
            {
                "user_id": profile["user_id"],
                "recent_questions": questions_by_user.get(profile["user_id"], []),
            }
            for profile in profiles_result["data"]
        ]
        return _success(items, "Profile sidebar items loaded.")
    except Exception as exc:
        return _error(f"Failed to list profile sidebar items: {exc}")


def ingest_documents_from_ui(
    document_paths: list[str | Path],
    index_dir: str | Path,
    use_chroma: bool = False,
) -> dict[str, Any]:
    """[Agent-Ready] Ingest local documents from the UI document page."""
    try:
        return ingest_documents(
            document_paths=document_paths,
            index_dir=index_dir,
            use_chroma=use_chroma,
            embedding_strategy="hash",
        )
    except Exception as exc:
        return _error(f"Failed to ingest documents from UI: {exc}")


def ask_question_from_ui(
    question: str,
    profile_data: dict[str, Any],
    index_dir: str | Path,
    top_k: int = 5,
    use_chroma: bool = False,
    use_llm: bool = False,
    llm_api_key: str | None = None,
    llm_base_url: str = "https://api.deepseek.com",
    llm_model: str = "deepseek-flash",
    database_url_or_path: str | Path | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """[Agent-Ready] Ask a RAG question from the UI without calling an external LLM."""
    try:
        result = answer_question_with_rag(
            question=question,
            profile_data=profile_data,
            index_dir=str(index_dir),
            top_k=top_k,
            use_chroma=use_chroma,
        )
        if result["status"] == "success" and use_llm:
            llm_result = generate_deepseek_rag_answer(
                question=question,
                profile_data=profile_data,
                rag_data=result["data"],
                api_key=llm_api_key or "",
                base_url=llm_base_url,
                model_name=llm_model,
            )
            if llm_result["status"] == "error":
                return llm_result
            result["data"]["rag_template_answer"] = result["data"]["answer"]
            result["data"]["answer"] = llm_result["data"]["answer"]
            result["data"]["llm"] = {
                "used_llm": llm_result["data"]["used_llm"],
                "model_name": llm_result["data"]["model_name"],
            }
            result["message"] = llm_result["message"]

        if (
            result["status"] == "success"
            and database_url_or_path is not None
            and user_id is not None
        ):
            history_result = record_question_from_ui(
                database_url_or_path,
                user_id=user_id,
                question=question,
            )
            if history_result["status"] == "success":
                result["data"]["question_recorded"] = True
            else:
                result["data"]["question_recorded"] = False
                result["data"]["question_record_error"] = history_result["message"]
        return result
    except Exception as exc:
        return _error(f"Failed to ask question from UI: {exc}")
