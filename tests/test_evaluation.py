from pathlib import Path

from app.evaluation.runner import (
    evaluate_filter_cases,
    evaluate_food_cases,
    evaluate_numeric_cases,
    evaluate_retrieval_cases,
    load_eval_cases,
    run_evaluation,
)
from app.retrieval.documents import ingest_documents


def assert_result_shape(result):
    assert set(result.keys()) == {"status", "data", "message"}
    assert result["status"] in {"success", "error"}
    assert isinstance(result["message"], str)


def write_eval_file(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines), encoding="utf-8")


def sample_profile():
    return {
        "height_cm": 175,
        "weight_kg": 72,
        "age": 28,
        "sex": "male",
        "goal": "fat_loss",
        "activity_level": "moderate",
        "injuries": ["膝伤"],
        "diet_preferences": [],
        "training_conditions": ["居家"],
    }


def test_load_eval_cases_loads_jsonl(tmp_path):
    eval_path = tmp_path / "eval.jsonl"
    write_eval_file(
        eval_path,
        [
            '{"id":"case-1","category":"numeric","question":"计算 BMR","metric":"bmr","profile":{"height_cm":175,"weight_kg":72,"age":28,"sex":"male","goal":"fat_loss"},"expected":{"value":1679}}'
        ],
    )

    result = load_eval_cases(eval_path)

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["case_count"] == 1


def test_load_eval_cases_rejects_missing_file(tmp_path):
    result = load_eval_cases(tmp_path / "missing.jsonl")

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None


def test_load_default_eval_set_has_required_size():
    result = load_eval_cases("data/evaluation/eval_set.jsonl")

    assert_result_shape(result)
    assert result["status"] == "success"
    assert 50 <= result["data"]["case_count"] <= 100


def test_evaluate_numeric_cases_reports_accuracy():
    cases = [
        {
            "id": "numeric-1",
            "category": "numeric",
            "question": "计算 BMR",
            "metric": "bmr",
            "profile": sample_profile(),
            "expected": {"value": 1679},
        },
        {
            "id": "numeric-2",
            "category": "numeric",
            "question": "计算 TDEE",
            "metric": "tdee",
            "profile": sample_profile(),
            "expected": {"value": 2602},
        },
    ]

    result = evaluate_numeric_cases(cases)

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["accuracy"] == 1.0


def test_evaluate_numeric_cases_handles_error_case():
    cases = [
        {
            "id": "bad-numeric",
            "category": "numeric",
            "question": "计算",
            "metric": "unknown",
            "profile": sample_profile(),
            "expected": {"value": 1},
        }
    ]

    result = evaluate_numeric_cases(cases)

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["accuracy"] == 0.0


def test_evaluate_food_cases_reports_accuracy():
    cases = [
        {
            "id": "food-1",
            "category": "food",
            "question": "chicken breast",
            "expected": {"matched_name": "鸡胸肉"},
        },
        {
            "id": "food-2",
            "category": "food",
            "question": "不存在的食物",
            "expected": {"should_error": True},
        },
    ]

    result = evaluate_food_cases(cases)

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["accuracy"] == 1.0


def test_evaluate_filter_cases_reports_contraindication_accuracy():
    cases = [
        {
            "id": "filter-1",
            "category": "filtering",
            "question": "膝伤过滤深蹲",
            "profile": sample_profile(),
            "chunk": {
                "content": "建议深蹲。",
                "source": "eval.md",
                "score": 0.9,
                "metadata": {"actions": ["深蹲"]},
            },
            "expected": {"should_remove": True},
        },
        {
            "id": "filter-2",
            "category": "filtering",
            "question": "膝伤保留低冲击",
            "profile": sample_profile(),
            "chunk": {
                "content": "建议固定自行车。",
                "source": "eval.md",
                "score": 0.9,
                "metadata": {"actions": ["固定自行车"]},
            },
            "expected": {"should_remove": False},
        },
    ]

    result = evaluate_filter_cases(cases)

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["accuracy"] == 1.0


def test_evaluate_retrieval_cases_reports_top_k_hit_rate(tmp_path):
    docs_dir = tmp_path / "docs"
    index_dir = tmp_path / "index"
    docs_dir.mkdir()
    (docs_dir / "knee.md").write_text(
        "---\ntitle: 膝伤训练\n---\n膝伤用户可以选择固定自行车和低冲击训练。",
        encoding="utf-8",
    )
    ingest_documents([docs_dir], index_dir=index_dir, use_chroma=False)
    cases = [
        {
            "id": "retrieval-1",
            "category": "retrieval",
            "question": "膝伤低冲击训练",
            "expected": {
                "source_contains": ["knee.md"],
                "content_keywords": ["固定自行车"],
            },
        }
    ]

    result = evaluate_retrieval_cases(cases, index_dir=index_dir, use_chroma=False)

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["top_k_hit_rate"] == 1.0


def test_run_evaluation_returns_summary(tmp_path):
    docs_dir = tmp_path / "docs"
    index_dir = tmp_path / "index"
    eval_path = tmp_path / "eval.jsonl"
    docs_dir.mkdir()
    (docs_dir / "knee.md").write_text(
        "---\ntitle: 膝伤训练\n---\n膝伤用户可以选择固定自行车和低冲击训练。",
        encoding="utf-8",
    )
    ingest_documents([docs_dir], index_dir=index_dir, use_chroma=False)
    write_eval_file(
        eval_path,
        [
            '{"id":"retrieval-1","category":"retrieval","question":"膝伤低冲击训练","expected":{"source_contains":["knee.md"],"content_keywords":["固定自行车"]}}',
            '{"id":"numeric-1","category":"numeric","question":"计算 BMR","metric":"bmr","profile":{"height_cm":175,"weight_kg":72,"age":28,"sex":"male","goal":"fat_loss"},"expected":{"value":1679}}',
            '{"id":"food-1","category":"food","question":"鸡胸肉","expected":{"matched_name":"鸡胸肉"}}',
            '{"id":"filter-1","category":"filtering","question":"膝伤过滤深蹲","profile":{"injuries":["膝伤"],"diet_preferences":[],"training_conditions":[]},"chunk":{"content":"建议深蹲。","source":"eval.md","score":0.9,"metadata":{"actions":["深蹲"]}},"expected":{"should_remove":true}}',
            '{"id":"hallucination-1","category":"hallucination","question":"膝伤低冲击训练","profile":{"injuries":["膝伤"],"diet_preferences":[],"training_conditions":["居家"]},"expected":{"requires_valid_citations":true}}',
            '{"id":"multistep-1","category":"multistep","question":"膝伤减脂怎么练","metric":"bmr","profile":{"height_cm":175,"weight_kg":72,"age":28,"sex":"male","goal":"fat_loss","injuries":["膝伤"],"diet_preferences":[],"training_conditions":["居家"]},"expected":{"requires_calculation":true,"requires_retrieval":true,"requires_filters":true}}',
        ],
    )

    result = run_evaluation(eval_path, index_dir=index_dir, use_chroma=False)

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["summary"]["case_count"] == 6
    assert "retrieval_top_5_hit_rate" in result["data"]["summary"]

