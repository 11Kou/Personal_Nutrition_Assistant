from pathlib import Path
from typing import Any, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Application settings loaded from environment variables or a .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PNA_",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Personal Nutrition Assistant"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = True

    database_url: str = "sqlite:///data/app.db"
    data_dir: Path = Path("data")
    food_csv_path: Path = Path("data/food/foods.csv")
    documents_dir: Path = Path("data/documents")
    chroma_dir: Path = Path("data/chroma")

    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str | None = Field(default=None, repr=False)
    llm_model: str = "deepseek-chat"

    embedding_model_name: str = "BAAI/bge-small-zh-v1.5"
    reranker_model_name: str = "BAAI/bge-reranker-base"
    reranker_fallback_enabled: bool = True


def _serialize_settings(settings: AppSettings) -> dict[str, Any]:
    data = settings.model_dump()
    for key, value in data.items():
        if isinstance(value, Path):
            data[key] = str(value)
    return data


def _normalize_overrides(overrides: dict[str, Any] | None) -> dict[str, Any]:
    if overrides is None:
        return {}
    if not isinstance(overrides, dict):
        raise TypeError("overrides must be a dictionary when provided")
    return overrides


def load_app_settings(
    env_file: str | Path | None = ".env",
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """[Agent-Ready] Load application settings with optional explicit overrides."""
    try:
        settings = AppSettings(_env_file=env_file, **_normalize_overrides(overrides))
        return {
            "status": "success",
            "data": _serialize_settings(settings),
            "message": "Application settings loaded.",
        }
    except Exception as exc:
        return {
            "status": "error",
            "data": None,
            "message": f"Failed to load application settings: {exc}",
        }


def get_project_paths(settings_data: dict[str, Any]) -> dict[str, Any]:
    """[Agent-Ready] Return the configured project storage paths."""
    try:
        if not isinstance(settings_data, dict):
            raise TypeError("settings_data must be a dictionary")

        required_keys = ["data_dir", "food_csv_path", "documents_dir", "chroma_dir"]
        missing_keys = [key for key in required_keys if key not in settings_data]
        if missing_keys:
            raise ValueError(f"Missing required path settings: {', '.join(missing_keys)}")

        paths = {key: str(Path(settings_data[key])) for key in required_keys}
        return {
            "status": "success",
            "data": paths,
            "message": "Project paths resolved.",
        }
    except Exception as exc:
        return {
            "status": "error",
            "data": None,
            "message": f"Failed to resolve project paths: {exc}",
        }
