from app.safety.profile_filters import build_filters, filter_by_profile


def assert_result_shape(result):
    assert set(result.keys()) == {"status", "data", "message"}
    assert result["status"] in {"success", "error"}
    assert isinstance(result["message"], str)


def sample_profile():
    return {
        "user_id": "user-1",
        "injuries": ["膝伤"],
        "diet_preferences": ["乳糖不耐"],
        "training_conditions": ["居家", "哑铃"],
    }


def safe_chunk():
    return {
        "content": "上肢训练和核心训练通常可以作为低冲击训练方向。",
        "source": "safe.md",
        "score": 0.91,
        "metadata": {
            "actions": ["核心训练"],
            "food_tags": [],
            "training_conditions": ["居家", "哑铃"],
        },
    }


def test_build_filters_from_profile():
    result = build_filters(sample_profile())

    assert_result_shape(result)
    assert result["status"] == "success"
    assert "深蹲" in result["data"]["exclude_actions"]
    assert "乳制品" in result["data"]["exclude_foods"]
    assert "史密斯机" in result["data"]["exclude_equipment"]
    assert "居家" in result["data"]["required_training_conditions"]
    assert "深蹲" in result["data"]["exclude_terms"]


def test_build_filters_returns_empty_lists_for_no_restrictions():
    result = build_filters(
        {
            "injuries": [],
            "diet_preferences": [],
            "training_conditions": [],
        }
    )

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["exclude_actions"] == []
    assert result["data"]["exclude_foods"] == []
    assert result["data"]["exclude_equipment"] == []
    assert result["data"]["required_training_conditions"] == []


def test_build_filters_rejects_wrong_input_type():
    result = build_filters(None)

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None


def test_filter_by_profile_keeps_safe_chunks():
    result = filter_by_profile([safe_chunk()], sample_profile())

    assert_result_shape(result)
    assert result["status"] == "success"
    assert len(result["data"]["safe_chunks"]) == 1
    assert result["data"]["removed_chunks"] == []


def test_filter_by_profile_removes_chunk_by_metadata_action():
    chunk = safe_chunk()
    chunk["metadata"]["actions"] = ["深蹲"]

    result = filter_by_profile([chunk], sample_profile())

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["safe_chunks"] == []
    assert "禁忌动作" in result["data"]["removed_chunks"][0]["reason"]
    assert "深蹲" in result["data"]["removed_chunks"][0]["matched_terms"]


def test_filter_by_profile_removes_chunk_by_content_when_metadata_misses_it():
    chunk = safe_chunk()
    chunk["content"] = "这个计划包含跳跃和冲刺跑。"
    chunk["metadata"] = {"actions": []}

    result = filter_by_profile([chunk], sample_profile())

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["safe_chunks"] == []
    assert "跳跃" in result["data"]["removed_chunks"][0]["matched_terms"]


def test_filter_by_profile_removes_food_conflict():
    chunk = safe_chunk()
    chunk["content"] = "训练后可以喝牛奶或乳清补充蛋白质。"
    chunk["metadata"] = {"food_tags": []}

    result = filter_by_profile([chunk], sample_profile())

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["safe_chunks"] == []
    assert "禁忌食物" in result["data"]["removed_chunks"][0]["reason"]


def test_filter_by_profile_removes_equipment_conflict():
    chunk = safe_chunk()
    chunk["metadata"]["required_equipment"] = ["史密斯机"]

    result = filter_by_profile([chunk], sample_profile())

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["safe_chunks"] == []
    assert "不适合器械" in result["data"]["removed_chunks"][0]["reason"]


def test_filter_by_profile_accepts_retrieval_result_shape():
    retrieval_result = {
        "status": "success",
        "data": [safe_chunk()],
        "message": "Retrieved 1 documents.",
    }

    result = filter_by_profile(retrieval_result, sample_profile())

    assert_result_shape(result)
    assert result["status"] == "success"
    assert len(result["data"]["safe_chunks"]) == 1


def test_filter_by_profile_rejects_bad_chunk_shape():
    result = filter_by_profile([{"content": "bad"}], sample_profile())

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None
