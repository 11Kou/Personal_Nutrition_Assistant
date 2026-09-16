import json
from typing import Any


def _success(data: Any, message: str) -> dict[str, Any]:
    return {"status": "success", "data": data, "message": message}


def _error(message: str) -> dict[str, Any]:
    return {"status": "error", "data": None, "message": message}


def _normalize_text(value: Any) -> str:
    return str(value).strip().lower()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple | set):
        return list(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
        return [value]
    return [value]


def _clean_unique(values: list[Any]) -> list[str]:
    cleaned_values = []
    seen = set()
    for value in values:
        cleaned = str(value).strip()
        if cleaned and cleaned not in seen:
            cleaned_values.append(cleaned)
            seen.add(cleaned)
    return cleaned_values


def _profile_terms(profile_data: dict[str, Any], key: str) -> list[str]:
    return [_normalize_text(item) for item in _as_list(profile_data.get(key))]


def _contains_any_text(text: str, terms: list[str]) -> list[str]:
    normalized_text = _normalize_text(text)
    return [term for term in terms if term and _normalize_text(term) in normalized_text]


def _metadata_values(metadata: dict[str, Any], keys: list[str]) -> list[str]:
    values = []
    for key in keys:
        values.extend(str(item) for item in _as_list(metadata.get(key)))
    return values


def _matched_metadata_terms(
    metadata: dict[str, Any],
    keys: list[str],
    terms: list[str],
) -> list[str]:
    values_text = " ".join(_metadata_values(metadata, keys))
    return _contains_any_text(values_text, terms)


def _injury_rules(injuries: list[str]) -> dict[str, list[str]]:
    rules = {
        "knee": {
            "aliases": ["knee", "膝", "膝伤", "膝痛", "膝关节"],
            "actions": [
                "深蹲",
                "跳跃",
                "跑步",
                "冲刺跑",
                "长距离跑",
                "波比跳",
                "跳箱",
                "深弓步",
                "squat",
                "jump",
                "running",
                "sprint",
                "burpee",
                "box jump",
                "lunge",
            ],
        },
        "shoulder": {
            "aliases": ["shoulder", "肩", "肩伤", "肩痛", "肩关节"],
            "actions": [
                "肩推",
                "推举",
                "过顶推举",
                "颈后推举",
                "双杠臂屈伸",
                "overhead press",
                "shoulder press",
                "dip",
            ],
        },
        "back": {
            "aliases": ["back", "spine", "腰", "背", "腰痛", "腰伤", "脊柱"],
            "actions": [
                "硬拉",
                "大重量深蹲",
                "负重体前屈",
                "仰卧起坐",
                "deadlift",
                "heavy squat",
                "loaded flexion",
                "sit-up",
            ],
        },
        "ankle": {
            "aliases": ["ankle", "踝", "脚踝", "踝伤", "踝痛"],
            "actions": [
                "跳跃",
                "跑步",
                "冲刺跑",
                "跳箱",
                "波比跳",
                "jump",
                "running",
                "sprint",
                "box jump",
                "burpee",
            ],
        },
    }

    excluded_actions = []
    for injury in injuries:
        for rule in rules.values():
            if any(alias in injury for alias in rule["aliases"]):
                excluded_actions.extend(rule["actions"])
    return {"exclude_actions": _clean_unique(excluded_actions)}


def _diet_rules(diet_preferences: list[str]) -> dict[str, list[str]]:
    rules = {
        "lactose": {
            "aliases": ["lactose", "乳糖", "乳糖不耐", "不耐乳", "奶制品不耐"],
            "foods": [
                "乳制品",
                "奶类",
                "牛奶",
                "酸奶",
                "奶酪",
                "乳清",
                "milk",
                "yogurt",
                "cheese",
                "whey",
                "dairy",
                "lactose",
            ],
        },
        "vegetarian": {
            "aliases": ["vegetarian", "素食"],
            "foods": [
                "鸡胸肉",
                "牛肉",
                "猪肉",
                "鱼",
                "三文鱼",
                "虾",
                "meat",
                "beef",
                "pork",
                "fish",
                "salmon",
                "shrimp",
            ],
        },
        "vegan": {
            "aliases": ["vegan", "纯素"],
            "foods": [
                "鸡胸肉",
                "牛肉",
                "猪肉",
                "鱼",
                "三文鱼",
                "虾",
                "鸡蛋",
                "牛奶",
                "酸奶",
                "奶酪",
                "乳清",
                "meat",
                "fish",
                "egg",
                "milk",
                "dairy",
                "whey",
            ],
        },
    }

    excluded_foods = []
    for preference in diet_preferences:
        for rule in rules.values():
            if any(alias in preference for alias in rule["aliases"]):
                excluded_foods.extend(rule["foods"])
    return {"exclude_foods": _clean_unique(excluded_foods)}


def _training_rules(training_conditions: list[str]) -> dict[str, list[str]]:
    excluded_equipment = []
    required_training_conditions = []

    for condition in training_conditions:
        if any(alias in condition for alias in ["home", "居家", "家里"]):
            required_training_conditions.extend(["home", "居家"])
            excluded_equipment.extend(["史密斯机", "腿举机", "龙门架", "gym machine"])
        if any(alias in condition for alias in ["no equipment", "无器械", "徒手"]):
            required_training_conditions.extend(["bodyweight", "徒手", "无器械"])
            excluded_equipment.extend(["哑铃", "杠铃", "壶铃", "器械", "dumbbell", "barbell"])
        if any(alias in condition for alias in ["dumbbell", "哑铃"]):
            required_training_conditions.extend(["dumbbell", "哑铃"])

    return {
        "exclude_equipment": _clean_unique(excluded_equipment),
        "required_training_conditions": _clean_unique(required_training_conditions),
    }


def _build_detection_terms(filters: dict[str, list[str]]) -> list[str]:
    terms = []
    for key in ["exclude_actions", "exclude_foods", "exclude_equipment"]:
        terms.extend(filters.get(key, []))
    return _clean_unique(terms)


def _extract_chunks(chunks_or_result: Any) -> list[dict[str, Any]]:
    if isinstance(chunks_or_result, dict):
        if chunks_or_result.get("status") == "success" and isinstance(
            chunks_or_result.get("data"), list
        ):
            return chunks_or_result["data"]
        raise ValueError("chunks_or_result must be a chunk list or successful retrieval result")
    if isinstance(chunks_or_result, list):
        return chunks_or_result
    raise TypeError("chunks_or_result must be a list or retrieval result dictionary")


def _validate_chunk_shape(chunk: dict[str, Any]) -> None:
    if not isinstance(chunk, dict):
        raise TypeError("each chunk must be a dictionary")
    missing_keys = {"content", "source", "score", "metadata"} - set(chunk.keys())
    if missing_keys:
        raise ValueError(f"chunk missing required keys: {', '.join(sorted(missing_keys))}")
    if not isinstance(chunk["metadata"], dict):
        raise TypeError("chunk metadata must be a dictionary")


def _removal_reason(chunk: dict[str, Any], filters: dict[str, list[str]]) -> dict[str, Any] | None:
    metadata = chunk.get("metadata", {})
    content = str(chunk.get("content", ""))

    checks = [
        {
            "label": "禁忌动作",
            "terms": filters.get("exclude_actions", []),
            "metadata_keys": ["actions", "contraindicated_actions", "movement_tags"],
        },
        {
            "label": "禁忌食物",
            "terms": filters.get("exclude_foods", []),
            "metadata_keys": ["foods", "food_tags", "ingredients", "diet_tags"],
        },
        {
            "label": "不适合器械",
            "terms": filters.get("exclude_equipment", []),
            "metadata_keys": ["equipment", "required_equipment", "equipment_tags"],
        },
    ]

    for check in checks:
        terms = check["terms"]
        metadata_matches = _matched_metadata_terms(metadata, check["metadata_keys"], terms)
        content_matches = _contains_any_text(content, terms)
        matched_terms = _clean_unique(metadata_matches + content_matches)
        if matched_terms:
            return {
                "reason": f"包含{check['label']}：{', '.join(matched_terms)}",
                "matched_terms": matched_terms,
            }

    required_conditions = filters.get("required_training_conditions", [])
    if required_conditions:
        metadata_matches = _matched_metadata_terms(
            metadata,
            ["training_conditions", "conditions", "training_environment"],
            required_conditions,
        )
        metadata_has_condition_field = any(
            key in metadata
            for key in ["training_conditions", "conditions", "training_environment"]
        )
        if metadata_has_condition_field and not metadata_matches:
            return {
                "reason": f"训练条件不匹配：需要 {', '.join(required_conditions)}",
                "matched_terms": [],
            }

    return None


def build_filters(profile_data: dict[str, Any]) -> dict[str, Any]:
    """[Agent-Ready] Build structured retrieval filters from a user profile."""
    try:
        if not isinstance(profile_data, dict):
            raise TypeError("profile_data must be a dictionary")

        injuries = _profile_terms(profile_data, "injuries")
        diet_preferences = _profile_terms(profile_data, "diet_preferences")
        training_conditions = _profile_terms(profile_data, "training_conditions")

        filters = {
            **_injury_rules(injuries),
            **_diet_rules(diet_preferences),
            **_training_rules(training_conditions),
        }
        filters["exclude_terms"] = _build_detection_terms(filters)
        filters["exclude_metadata"] = {
            "actions": filters["exclude_actions"],
            "contraindicated_actions": filters["exclude_actions"],
            "foods": filters["exclude_foods"],
            "food_tags": filters["exclude_foods"],
            "equipment": filters["exclude_equipment"],
            "required_equipment": filters["exclude_equipment"],
        }

        return _success(filters, "Profile filters built.")
    except Exception as exc:
        return _error(f"Failed to build profile filters: {exc}")


def filter_by_profile(
    chunks_or_result: list[dict[str, Any]] | dict[str, Any],
    profile_data: dict[str, Any],
) -> dict[str, Any]:
    """[Agent-Ready] Remove retrieved chunks that conflict with the user profile."""
    try:
        chunks = _extract_chunks(chunks_or_result)
        filters_result = build_filters(profile_data)
        if filters_result["status"] == "error":
            return filters_result

        filters = filters_result["data"]
        safe_chunks = []
        removed_chunks = []

        for chunk in chunks:
            _validate_chunk_shape(chunk)
            reason = _removal_reason(chunk, filters)
            if reason:
                removed_chunks.append(
                    {
                        "source": chunk["source"],
                        "score": chunk["score"],
                        "reason": reason["reason"],
                        "matched_terms": reason["matched_terms"],
                        "metadata": chunk["metadata"],
                    }
                )
            else:
                safe_chunks.append(chunk)

        return _success(
            {
                "safe_chunks": safe_chunks,
                "removed_chunks": removed_chunks,
            },
            f"Profile filtering kept {len(safe_chunks)} chunks and removed {len(removed_chunks)} chunks.",
        )
    except Exception as exc:
        return _error(f"Failed to filter chunks by profile: {exc}")
