from pathlib import Path
from typing import Any

from app.core.config import load_app_settings
from app.profile.storage import (
    create_user_profile,
    get_user_profile,
    update_user_profile,
)
from app.rag.flow import answer_question_with_rag
from app.retrieval.documents import ingest_documents


def _success(data: Any, message: str) -> dict[str, Any]:
    return {"status": "success", "data": data, "message": message}


def _error(message: str) -> dict[str, Any]:
    return {"status": "error", "data": None, "message": message}


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
) -> dict[str, Any]:
    """[Agent-Ready] Ask a RAG question from the UI without calling an external LLM."""
    try:
        return answer_question_with_rag(
            question=question,
            profile_data=profile_data,
            index_dir=str(index_dir),
            top_k=top_k,
            use_chroma=use_chroma,
        )
    except Exception as exc:
        return _error(f"Failed to ask question from UI: {exc}")
