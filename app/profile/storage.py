import json
import sqlite3
from pathlib import Path
from typing import Any

from app.profile.models import UserProfile, UserProfilePatch


def _success(data: Any, message: str) -> dict[str, Any]:
    return {"status": "success", "data": data, "message": message}


def _error(message: str) -> dict[str, Any]:
    return {"status": "error", "data": None, "message": message}


def _resolve_sqlite_path(database_url_or_path: str | Path) -> Path:
    raw_value = str(database_url_or_path).strip()
    if not raw_value:
        raise ValueError("database_url_or_path cannot be empty")
    if raw_value == ":memory:":
        raise ValueError("Use a file path for profile storage so data persists across calls")
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


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id TEXT PRIMARY KEY,
            height_cm REAL NOT NULL,
            weight_kg REAL NOT NULL,
            body_fat_percent REAL,
            age INTEGER NOT NULL,
            sex TEXT NOT NULL,
            goal TEXT NOT NULL,
            injuries TEXT NOT NULL,
            medical_conditions TEXT NOT NULL DEFAULT '[]',
            medications TEXT NOT NULL DEFAULT '[]',
            diet_preferences TEXT NOT NULL,
            training_conditions TEXT NOT NULL,
            activity_level TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    existing_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(user_profiles)")
    }
    if "medical_conditions" not in existing_columns:
        connection.execute(
            "ALTER TABLE user_profiles ADD COLUMN medical_conditions TEXT NOT NULL DEFAULT '[]'"
        )
    if "medications" not in existing_columns:
        connection.execute(
            "ALTER TABLE user_profiles ADD COLUMN medications TEXT NOT NULL DEFAULT '[]'"
        )
    connection.commit()


def _profile_to_row(profile: UserProfile) -> dict[str, Any]:
    data = profile.model_dump()
    return {
        **data,
        "injuries": json.dumps(data["injuries"], ensure_ascii=False),
        "medical_conditions": json.dumps(data["medical_conditions"], ensure_ascii=False),
        "medications": json.dumps(data["medications"], ensure_ascii=False),
        "diet_preferences": json.dumps(data["diet_preferences"], ensure_ascii=False),
        "training_conditions": json.dumps(data["training_conditions"], ensure_ascii=False),
    }


def _loads_list(value: Any) -> list[str]:
    if value is None:
        return []
    parsed_value = json.loads(value)
    if not isinstance(parsed_value, list):
        return []
    return parsed_value


def _row_to_profile(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    profile_data = {
        "user_id": data["user_id"],
        "height_cm": data["height_cm"],
        "weight_kg": data["weight_kg"],
        "body_fat_percent": data["body_fat_percent"],
        "age": data["age"],
        "sex": data["sex"],
        "goal": data["goal"],
        "injuries": _loads_list(data.get("injuries")),
        "medical_conditions": _loads_list(data.get("medical_conditions")),
        "medications": _loads_list(data.get("medications")),
        "diet_preferences": _loads_list(data.get("diet_preferences")),
        "training_conditions": _loads_list(data.get("training_conditions")),
        "activity_level": data["activity_level"],
    }
    return UserProfile.model_validate(profile_data).model_dump()


def initialize_profile_storage(database_url_or_path: str | Path) -> dict[str, Any]:
    """[Agent-Ready] Initialize the SQLite table for user profiles."""
    try:
        database_path = _resolve_sqlite_path(database_url_or_path)
        with _connect(database_path) as connection:
            _ensure_schema(connection)
        return _success(
            {"database_path": str(database_path)},
            "Profile storage initialized.",
        )
    except Exception as exc:
        return _error(f"Failed to initialize profile storage: {exc}")


def create_user_profile(
    database_url_or_path: str | Path,
    profile_data: dict[str, Any],
) -> dict[str, Any]:
    """[Agent-Ready] Create a user profile in SQLite."""
    try:
        profile = UserProfile.model_validate(profile_data)
        row = _profile_to_row(profile)

        with _connect(database_url_or_path) as connection:
            _ensure_schema(connection)
            connection.execute(
                """
                INSERT INTO user_profiles (
                    user_id,
                    height_cm,
                    weight_kg,
                    body_fat_percent,
                    age,
                    sex,
                    goal,
                    injuries,
                    medical_conditions,
                    medications,
                    diet_preferences,
                    training_conditions,
                    activity_level
                )
                VALUES (
                    :user_id,
                    :height_cm,
                    :weight_kg,
                    :body_fat_percent,
                    :age,
                    :sex,
                    :goal,
                    :injuries,
                    :medical_conditions,
                    :medications,
                    :diet_preferences,
                    :training_conditions,
                    :activity_level
                )
                """,
                row,
            )
            connection.commit()

        return _success(profile.model_dump(), "User profile created.")
    except sqlite3.IntegrityError:
        return _error("Failed to create user profile: user_id already exists")
    except Exception as exc:
        return _error(f"Failed to create user profile: {exc}")


def get_user_profile(database_url_or_path: str | Path, user_id: str) -> dict[str, Any]:
    """[Agent-Ready] Read a user profile from SQLite."""
    try:
        cleaned_user_id = str(user_id).strip()
        if not cleaned_user_id:
            raise ValueError("user_id cannot be empty")

        with _connect(database_url_or_path) as connection:
            _ensure_schema(connection)
            row = connection.execute(
                "SELECT * FROM user_profiles WHERE user_id = ?",
                (cleaned_user_id,),
            ).fetchone()

        if row is None:
            return _error("User profile not found.")

        return _success(_row_to_profile(row), "User profile loaded.")
    except Exception as exc:
        return _error(f"Failed to load user profile: {exc}")


def update_user_profile(
    database_url_or_path: str | Path,
    user_id: str,
    patch: dict[str, Any],
) -> dict[str, Any]:
    """[Agent-Ready] Update a user profile with a partial patch."""
    try:
        current_result = get_user_profile(database_url_or_path, user_id)
        if current_result["status"] == "error":
            return current_result

        patch_model = UserProfilePatch.model_validate(patch)
        patch_data = patch_model.model_dump(exclude_unset=True)
        if not patch_data:
            return _success(current_result["data"], "No profile changes provided.")

        updated_profile = UserProfile.model_validate(
            {**current_result["data"], **patch_data}
        )
        row = _profile_to_row(updated_profile)

        with _connect(database_url_or_path) as connection:
            _ensure_schema(connection)
            connection.execute(
                """
                UPDATE user_profiles
                SET
                    height_cm = :height_cm,
                    weight_kg = :weight_kg,
                    body_fat_percent = :body_fat_percent,
                    age = :age,
                    sex = :sex,
                    goal = :goal,
                    injuries = :injuries,
                    medical_conditions = :medical_conditions,
                    medications = :medications,
                    diet_preferences = :diet_preferences,
                    training_conditions = :training_conditions,
                    activity_level = :activity_level,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = :user_id
                """,
                row,
            )
            connection.commit()

        return _success(updated_profile.model_dump(), "User profile updated.")
    except Exception as exc:
        return _error(f"Failed to update user profile: {exc}")


def delete_user_profile(database_url_or_path: str | Path, user_id: str) -> dict[str, Any]:
    """[Agent-Ready] Delete a user profile from SQLite."""
    try:
        cleaned_user_id = str(user_id).strip()
        if not cleaned_user_id:
            raise ValueError("user_id cannot be empty")

        with _connect(database_url_or_path) as connection:
            _ensure_schema(connection)
            cursor = connection.execute(
                "DELETE FROM user_profiles WHERE user_id = ?",
                (cleaned_user_id,),
            )
            connection.commit()

        if cursor.rowcount == 0:
            return _error("User profile not found.")

        return _success({"user_id": cleaned_user_id}, "User profile deleted.")
    except Exception as exc:
        return _error(f"Failed to delete user profile: {exc}")


def list_user_profiles(database_url_or_path: str | Path) -> dict[str, Any]:
    """[Agent-Ready] List all user profiles from SQLite."""
    try:
        with _connect(database_url_or_path) as connection:
            _ensure_schema(connection)
            rows = connection.execute(
                "SELECT * FROM user_profiles ORDER BY user_id"
            ).fetchall()

        profiles = [_row_to_profile(row) for row in rows]
        return _success(profiles, "User profiles listed.")
    except Exception as exc:
        return _error(f"Failed to list user profiles: {exc}")


def format_profile_for_prompt(profile_data: dict[str, Any]) -> dict[str, Any]:
    """[Agent-Ready] Format a user profile as text for system prompt injection."""
    try:
        profile = UserProfile.model_validate(profile_data)
        data = profile.model_dump()
        body_fat_text = (
            f"{data['body_fat_percent']}%"
            if data["body_fat_percent"] is not None
            else "not provided; do not infer or use body fat percentage"
        )

        profile_text = "\n".join(
            [
                "Current user profile:",
                f"- User ID: {data['user_id']}",
                f"- Age: {data['age']}",
                f"- Sex: {data['sex']}",
                f"- Height: {data['height_cm']} cm",
                f"- Weight: {data['weight_kg']} kg",
                f"- Body fat percent: {body_fat_text}",
                f"- Goal: {data['goal']}",
                f"- Activity level: {data['activity_level']}",
                f"- Injuries or contraindications: {', '.join(data['injuries']) or 'none'}",
                f"- Medical conditions: {', '.join(data['medical_conditions']) or 'none'}",
                f"- Medications: {', '.join(data['medications']) or 'none'}",
                f"- Diet preferences: {', '.join(data['diet_preferences']) or 'none'}",
                f"- Training conditions: {', '.join(data['training_conditions']) or 'none'}",
            ]
        )

        return _success({"profile_text": profile_text}, "Profile prompt text formatted.")
    except Exception as exc:
        return _error(f"Failed to format profile for prompt: {exc}")
