from typing import Literal

from pydantic import BaseModel, Field, field_validator


class UserProfile(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    height_cm: float = Field(gt=0, le=300)
    weight_kg: float = Field(gt=0, le=500)
    body_fat_percent: float | None = Field(default=None, ge=0, le=80)
    age: int = Field(ge=1, le=120)
    sex: Literal["male", "female", "other"]
    goal: Literal["muscle_gain", "fat_loss", "maintenance", "wellness"]
    injuries: list[str] = Field(default_factory=list)
    diet_preferences: list[str] = Field(default_factory=list)
    training_conditions: list[str] = Field(default_factory=list)
    activity_level: Literal[
        "sedentary",
        "light",
        "moderate",
        "active",
        "very_active",
    ] = "moderate"

    @field_validator("user_id")
    @classmethod
    def clean_user_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("user_id cannot be empty")
        return cleaned

    @field_validator("injuries", "diet_preferences", "training_conditions")
    @classmethod
    def clean_text_list(cls, values: list[str]) -> list[str]:
        cleaned_values = []
        seen = set()
        for value in values:
            cleaned = str(value).strip()
            if cleaned and cleaned not in seen:
                cleaned_values.append(cleaned)
                seen.add(cleaned)
        return cleaned_values


class UserProfilePatch(BaseModel):
    height_cm: float | None = Field(default=None, gt=0, le=300)
    weight_kg: float | None = Field(default=None, gt=0, le=500)
    body_fat_percent: float | None = Field(default=None, ge=0, le=80)
    age: int | None = Field(default=None, ge=1, le=120)
    sex: Literal["male", "female", "other"] | None = None
    goal: Literal["muscle_gain", "fat_loss", "maintenance", "wellness"] | None = None
    injuries: list[str] | None = None
    diet_preferences: list[str] | None = None
    training_conditions: list[str] | None = None
    activity_level: Literal[
        "sedentary",
        "light",
        "moderate",
        "active",
        "very_active",
    ] | None = None

    @field_validator("injuries", "diet_preferences", "training_conditions")
    @classmethod
    def clean_optional_text_list(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        cleaned_values = []
        seen = set()
        for value in values:
            cleaned = str(value).strip()
            if cleaned and cleaned not in seen:
                cleaned_values.append(cleaned)
                seen.add(cleaned)
        return cleaned_values
