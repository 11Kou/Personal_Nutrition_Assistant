from app.food.query import query_food


def assert_result_shape(result):
    assert set(result.keys()) == {"status", "data", "message"}
    assert result["status"] in {"success", "error"}
    assert isinstance(result["message"], str)


def test_query_food_returns_per_100g_for_exact_chinese_name():
    result = query_food("鸡胸肉")

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["matched_name"] == "鸡胸肉"
    assert result["data"]["per_100g"] == {
        "calories_kcal": 120.0,
        "protein_g": 22.5,
        "carbs_g": 0.0,
        "fat_g": 2.6,
    }
    assert result["data"]["source"] == "local_food_csv"


def test_query_food_matches_english_alias():
    result = query_food("chicken breast")

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["matched_name"] == "鸡胸肉"
    assert result["data"]["match"]["type"] == "exact_alias"


def test_query_food_matches_partial_alias():
    result = query_food("milk")

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["matched_name"] == "牛奶"
    assert "dairy" in result["data"]["tags"]


def test_query_food_returns_amount_scaled_values():
    result = query_food("燕麦", amount_g=50)

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["amount_g"] == 50.0
    assert result["data"]["per_amount"] == {
        "calories_kcal": 194.5,
        "protein_g": 8.45,
        "carbs_g": 33.15,
        "fat_g": 3.45,
    }


def test_query_food_rejects_empty_name():
    result = query_food(" ")

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None


def test_query_food_rejects_zero_amount():
    result = query_food("鸡蛋", amount_g=0)

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None


def test_query_food_returns_error_for_missing_food():
    result = query_food("不存在的食物")

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None


def test_query_food_returns_error_for_missing_csv(tmp_path):
    missing_csv = tmp_path / "missing.csv"

    result = query_food("鸡蛋", csv_path=missing_csv)

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None


def test_query_food_returns_error_for_invalid_csv(tmp_path):
    bad_csv = tmp_path / "foods.csv"
    bad_csv.write_text("food_name,calories_kcal\nbad,1\n", encoding="utf-8")

    result = query_food("bad", csv_path=bad_csv)

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None
