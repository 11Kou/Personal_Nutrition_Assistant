import csv
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


def _success(data: Any, message: str) -> dict[str, Any]:
    return {"status": "success", "data": data, "message": message}


def _error(message: str) -> dict[str, Any]:
    return {"status": "error", "data": None, "message": message}


def _normalize_text(value: Any) -> str:
    return "".join(str(value).lower().strip().split())


def _parse_tags(value: str) -> list[str]:
    return [item.strip() for item in value.split("|") if item.strip()]


def _parse_float(row: dict[str, str], key: str) -> float:
    raw_value = str(row.get(key, "")).strip()
    if raw_value == "":
        raise ValueError(f"Missing numeric field: {key}")
    return float(raw_value)


def _validate_amount(amount_g: float | int | None) -> float | None:
    if amount_g is None:
        return None
    if not isinstance(amount_g, int | float):
        raise TypeError("amount_g must be a number when provided")
    if amount_g <= 0:
        raise ValueError("amount_g must be greater than 0")
    return float(amount_g)


def _read_food_rows(csv_path: str | Path) -> list[dict[str, str]]:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Food CSV not found: {path}")
    if not path.is_file():
        raise ValueError(f"Food CSV path is not a file: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required_columns = {
            "food_name",
            "aliases",
            "category",
            "calories_kcal",
            "protein_g",
            "carbs_g",
            "fat_g",
            "tags",
            "source",
        }
        fieldnames = set(reader.fieldnames or [])
        missing_columns = sorted(required_columns - fieldnames)
        if missing_columns:
            raise ValueError(f"Food CSV missing columns: {', '.join(missing_columns)}")
        return [row for row in reader if str(row.get("food_name", "")).strip()]


def _build_food_record(row: dict[str, str], amount_g: float | None) -> dict[str, Any]:
    per_100g = {
        "calories_kcal": _parse_float(row, "calories_kcal"),
        "protein_g": _parse_float(row, "protein_g"),
        "carbs_g": _parse_float(row, "carbs_g"),
        "fat_g": _parse_float(row, "fat_g"),
    }

    data = {
        "food_name": row["food_name"].strip(),
        "matched_name": row["food_name"].strip(),
        "category": row["category"].strip(),
        "per_100g": per_100g,
        "tags": _parse_tags(row["tags"]),
        "source": row["source"].strip() or "local_food_csv",
    }

    if amount_g is not None:
        ratio = amount_g / 100
        data["amount_g"] = amount_g
        data["per_amount"] = {
            key: round(value * ratio, 2) for key, value in per_100g.items()
        }

    return data


def _score_row(query_text: str, row: dict[str, str]) -> tuple[float, str]:
    normalized_query = _normalize_text(query_text)
    normalized_name = _normalize_text(row["food_name"])
    aliases = _parse_tags(row.get("aliases", ""))
    normalized_aliases = [_normalize_text(alias) for alias in aliases]

    if normalized_query == normalized_name:
        return 1.0, "exact_name"
    if normalized_query in normalized_aliases:
        return 0.98, "exact_alias"
    if normalized_query and normalized_query in normalized_name:
        return 0.9, "partial_name"
    if any(normalized_query and normalized_query in alias for alias in normalized_aliases):
        return 0.88, "partial_alias"

    name_score = SequenceMatcher(None, normalized_query, normalized_name).ratio()
    alias_score = max(
        [SequenceMatcher(None, normalized_query, alias).ratio() for alias in normalized_aliases],
        default=0,
    )
    best_score = max(name_score, alias_score)
    if best_score >= 0.55:
        return best_score, "fuzzy"
    return 0, "no_match"


def _find_best_match(
    food_name: str,
    rows: list[dict[str, str]],
) -> tuple[dict[str, str] | None, float, str]:
    best_row = None
    best_score = 0.0
    best_match_type = "no_match"
    for row in rows:
        score, match_type = _score_row(food_name, row)
        if score > best_score:
            best_row = row
            best_score = score
            best_match_type = match_type
    return best_row, best_score, best_match_type


def _suggest_foods(food_name: str, rows: list[dict[str, str]]) -> list[str]:
    scored_rows = []
    for row in rows:
        score, _ = _score_row(food_name, row)
        if score > 0:
            scored_rows.append((score, row["food_name"].strip()))
    scored_rows.sort(reverse=True)
    return [name for _, name in scored_rows[:3]]


def query_food(
    food_name: str,
    amount_g: float | int | None = None,
    csv_path: str | Path = "data/food/foods.csv",
) -> dict[str, Any]:
    """[Agent-Ready] Query local CSV nutrition data, returning per-100g by default."""
    try:
        cleaned_food_name = str(food_name).strip()
        if not cleaned_food_name:
            raise ValueError("food_name cannot be empty")

        validated_amount = _validate_amount(amount_g)
        rows = _read_food_rows(csv_path)
        if not rows:
            raise ValueError("Food CSV has no food rows")

        matched_row, score, match_type = _find_best_match(cleaned_food_name, rows)
        if matched_row is None or score <= 0:
            suggestions = _suggest_foods(cleaned_food_name, rows)
            suggestion_text = ", ".join(suggestions) if suggestions else "none"
            return _error(f"Food not found. Suggestions: {suggestion_text}")

        record = _build_food_record(matched_row, validated_amount)
        record["query"] = cleaned_food_name
        record["match"] = {
            "type": match_type,
            "score": round(score, 3),
        }

        return _success(record, "Food nutrition data found.")
    except Exception as exc:
        return _error(f"Failed to query food: {exc}")
