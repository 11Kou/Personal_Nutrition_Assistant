import json
import re
from pathlib import Path
from typing import Any

from app.food.query import query_food
from app.nutrition.calculations import (
    calculate_bmi,
    calculate_bmr,
    calculate_macro_targets,
    calculate_tdee,
)
from app.rag.flow import answer_question_with_rag
from app.retrieval.documents import retrieve_documents
from app.safety.profile_filters import build_filters, filter_by_profile


def _success(data: Any, message: str) -> dict[str, Any]:
    return {"status": "success", "data": data, "message": message}


def _error(message: str) -> dict[str, Any]:
    return {"status": "error", "data": None, "message": message}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple | set):
        return list(value)
    return [value]


def _case_passed(results: list[bool]) -> bool:
    return bool(results) and all(results)


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def _source_matches(source: str, expected_sources: list[str]) -> bool:
    normalized_source = str(source).replace("\\", "/").lower()
    return any(str(expected).replace("\\", "/").lower() in normalized_source for expected in expected_sources)


def _content_has_keywords(content: str, expected_keywords: list[str]) -> bool:
    normalized_content = str(content).lower()
    return all(str(keyword).lower() in normalized_content for keyword in expected_keywords)


def _extract_citation_numbers(answer: str) -> list[int]:
    numbers = []
    for match in re.finditer(r"\[(\d+)\]", str(answer)):
        numbers.append(int(match.group(1)))
    return numbers


def _calculation_result(case: dict[str, Any]) -> dict[str, Any]:
    metric = str(case.get("metric", "")).strip()
    profile = case.get("profile", {})
    if metric == "bmi":
        return calculate_bmi(profile)
    if metric == "bmr":
        return calculate_bmr(profile)
    if metric == "tdee":
        return calculate_tdee(profile, activity_level=case.get("activity_level"))
    if metric == "macros":
        return calculate_macro_targets(
            profile,
            goal=case.get("goal"),
            activity_level=case.get("activity_level"),
        )
    return _error("metric must be one of: bmi, bmr, tdee, macros")


def _numeric_close(actual: Any, expected: Any, tolerance: float) -> bool:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        checks = []
        for key, expected_value in expected.items():
            if key not in actual:
                checks.append(False)
                continue
            checks.append(_numeric_close(actual[key], expected_value, tolerance))
        return _case_passed(checks)
    if not isinstance(actual, int | float) or not isinstance(expected, int | float):
        return actual == expected
    return abs(float(actual) - float(expected)) <= tolerance


def load_eval_cases(eval_path: str | Path) -> dict[str, Any]:
    """[Agent-Ready] Load JSONL evaluation cases from disk."""
    try:
        path = Path(eval_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Evaluation file not found: {path}")

        cases = []
        with path.open("r", encoding="utf-8-sig") as file:
            for line_number, line in enumerate(file, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                case = json.loads(stripped)
                if not isinstance(case, dict):
                    raise ValueError(f"Line {line_number} is not a JSON object")
                for key in ["id", "category", "question", "expected"]:
                    if key not in case:
                        raise ValueError(f"Line {line_number} missing required key: {key}")
                cases.append(case)

        if not cases:
            raise ValueError("Evaluation file contains no cases")

        return _success({"cases": cases, "case_count": len(cases)}, f"Loaded {len(cases)} cases.")
    except Exception as exc:
        return _error(f"Failed to load evaluation cases: {exc}")


def evaluate_retrieval_cases(
    cases: list[dict[str, Any]],
    index_dir: str | Path,
    top_k: int = 5,
    use_chroma: bool = False,
) -> dict[str, Any]:
    """[Agent-Ready] Measure retrieval Top-k hit rate against expected sources or keywords."""
    try:
        details = []
        hits = []
        for case in cases:
            expected = case.get("expected", {})
            result = retrieve_documents(
                query=case["question"],
                index_dir=index_dir,
                filters=case.get("filters"),
                top_k=top_k,
                use_chroma=use_chroma,
            )
            if result["status"] == "error":
                details.append({"id": case["id"], "passed": False, "message": result["message"]})
                hits.append(0.0)
                continue

            chunks = result["data"]
            expected_sources = _as_list(expected.get("source_contains"))
            expected_keywords = _as_list(expected.get("content_keywords"))
            source_checks = [
                any(_source_matches(chunk["source"], [expected_source]) for chunk in chunks)
                for expected_source in expected_sources
            ]
            keyword_checks = [
                any(_content_has_keywords(chunk["content"], [keyword]) for chunk in chunks)
                for keyword in expected_keywords
            ]
            passed = _case_passed(source_checks + keyword_checks)
            hits.append(1.0 if passed else 0.0)
            details.append(
                {
                    "id": case["id"],
                    "passed": passed,
                    "retrieved_count": len(chunks),
                    "top_sources": [chunk["source"] for chunk in chunks[:top_k]],
                }
            )

        return _success(
            {
                "case_count": len(cases),
                "top_k": top_k,
                "top_k_hit_rate": _mean(hits),
                "details": details,
            },
            "Retrieval evaluation completed.",
        )
    except Exception as exc:
        return _error(f"Failed to evaluate retrieval cases: {exc}")


def evaluate_numeric_cases(cases: list[dict[str, Any]], tolerance: float = 0.01) -> dict[str, Any]:
    """[Agent-Ready] Measure numeric calculation accuracy against expected formula outputs."""
    try:
        details = []
        passed_values = []
        for case in cases:
            expected_value = case.get("expected", {}).get("value")
            result = _calculation_result(case)
            if result["status"] == "error":
                details.append({"id": case["id"], "passed": False, "message": result["message"]})
                passed_values.append(0.0)
                continue

            actual_value = result["data"]["result"]
            passed = _numeric_close(actual_value, expected_value, tolerance)
            passed_values.append(1.0 if passed else 0.0)
            details.append(
                {
                    "id": case["id"],
                    "metric": case.get("metric"),
                    "passed": passed,
                    "actual": actual_value,
                    "expected": expected_value,
                }
            )

        return _success(
            {
                "case_count": len(cases),
                "accuracy": _mean(passed_values),
                "details": details,
            },
            "Numeric calculation evaluation completed.",
        )
    except Exception as exc:
        return _error(f"Failed to evaluate numeric cases: {exc}")


def evaluate_filter_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """[Agent-Ready] Measure profile-based contraindication filtering accuracy."""
    try:
        details = []
        passed_values = []
        for case in cases:
            profile = case.get("profile", {})
            chunk = case.get("chunk")
            if not isinstance(chunk, dict):
                raise ValueError(f"Case {case.get('id')} missing chunk dictionary")

            result = filter_by_profile([chunk], profile)
            if result["status"] == "error":
                details.append({"id": case["id"], "passed": False, "message": result["message"]})
                passed_values.append(0.0)
                continue

            should_remove = bool(case.get("expected", {}).get("should_remove"))
            removed = len(result["data"]["removed_chunks"]) == 1
            passed = removed == should_remove
            passed_values.append(1.0 if passed else 0.0)
            details.append(
                {
                    "id": case["id"],
                    "passed": passed,
                    "expected_removed": should_remove,
                    "actual_removed": removed,
                    "removed_chunks": result["data"]["removed_chunks"],
                }
            )

        return _success(
            {
                "case_count": len(cases),
                "accuracy": _mean(passed_values),
                "details": details,
            },
            "Profile filter evaluation completed.",
        )
    except Exception as exc:
        return _error(f"Failed to evaluate filter cases: {exc}")


def evaluate_food_cases(
    cases: list[dict[str, Any]],
    csv_path: str | Path = "data/food/foods.csv",
) -> dict[str, Any]:
    """[Agent-Ready] Measure structured food query accuracy."""
    try:
        details = []
        passed_values = []
        for case in cases:
            result = query_food(
                case["question"],
                amount_g=case.get("amount_g"),
                csv_path=csv_path,
            )
            expected = case.get("expected", {})
            should_error = bool(expected.get("should_error"))
            if should_error:
                passed = result["status"] == "error"
                actual_name = None
            elif result["status"] == "success":
                actual_name = result["data"]["matched_name"]
                passed = actual_name == expected.get("matched_name")
            else:
                passed = False
                actual_name = None

            passed_values.append(1.0 if passed else 0.0)
            details.append(
                {
                    "id": case["id"],
                    "passed": passed,
                    "actual": actual_name,
                    "expected": expected,
                    "message": result["message"],
                }
            )

        return _success(
            {
                "case_count": len(cases),
                "accuracy": _mean(passed_values),
                "details": details,
            },
            "Food query evaluation completed.",
        )
    except Exception as exc:
        return _error(f"Failed to evaluate food cases: {exc}")


def evaluate_hallucination_cases(
    cases: list[dict[str, Any]],
    index_dir: str | Path,
    top_k: int = 5,
    use_chroma: bool = False,
) -> dict[str, Any]:
    """[Agent-Ready] Estimate citation hallucination rate by validating answer citations."""
    try:
        details = []
        valid_values = []
        for case in cases:
            result = answer_question_with_rag(
                question=case["question"],
                profile_data=case.get("profile", {}),
                index_dir=str(index_dir),
                top_k=top_k,
                use_chroma=use_chroma,
            )
            if result["status"] == "error":
                details.append({"id": case["id"], "passed": False, "message": result["message"]})
                valid_values.append(0.0)
                continue

            answer = result["data"]["answer"]
            sources = result["data"]["sources"]
            citations = _extract_citation_numbers(answer)
            source_indexes = set(range(1, len(sources) + 1))
            citations_are_valid = all(citation in source_indexes for citation in citations)
            has_required_citation = bool(citations) if sources else not citations
            sources_are_valid = all(source.get("source") for source in sources)
            passed = citations_are_valid and has_required_citation and sources_are_valid
            valid_values.append(1.0 if passed else 0.0)
            details.append(
                {
                    "id": case["id"],
                    "passed": passed,
                    "citation_numbers": citations,
                    "source_count": len(sources),
                }
            )

        return _success(
            {
                "case_count": len(cases),
                "citation_validity_rate": _mean(valid_values),
                "hallucination_rate": round(1 - _mean(valid_values), 4),
                "details": details,
            },
            "Hallucination evaluation completed.",
        )
    except Exception as exc:
        return _error(f"Failed to evaluate hallucination cases: {exc}")


def evaluate_multistep_cases(
    cases: list[dict[str, Any]],
    index_dir: str | Path,
    csv_path: str | Path = "data/food/foods.csv",
    top_k: int = 5,
    use_chroma: bool = False,
) -> dict[str, Any]:
    """[Agent-Ready] Check multi-step cases that require several module outputs."""
    try:
        details = []
        passed_values = []
        for case in cases:
            expected = case.get("expected", {})
            checks = []
            messages = []

            if expected.get("requires_calculation"):
                calculation_result = _calculation_result(case)
                checks.append(calculation_result["status"] == "success")
                messages.append(calculation_result["message"])

            if expected.get("requires_food"):
                food_result = query_food(
                    expected.get("food_name", case["question"]),
                    amount_g=case.get("amount_g"),
                    csv_path=csv_path,
                )
                checks.append(food_result["status"] == "success")
                messages.append(food_result["message"])

            if expected.get("requires_retrieval"):
                retrieval_result = retrieve_documents(
                    query=case["question"],
                    index_dir=index_dir,
                    top_k=top_k,
                    use_chroma=use_chroma,
                )
                checks.append(retrieval_result["status"] == "success" and bool(retrieval_result["data"]))
                messages.append(retrieval_result["message"])

            if expected.get("requires_filters"):
                filters_result = build_filters(case.get("profile", {}))
                checks.append(filters_result["status"] == "success")
                messages.append(filters_result["message"])

            passed = _case_passed(checks)
            passed_values.append(1.0 if passed else 0.0)
            details.append({"id": case["id"], "passed": passed, "messages": messages})

        return _success(
            {
                "case_count": len(cases),
                "accuracy": _mean(passed_values),
                "details": details,
            },
            "Multi-step evaluation completed.",
        )
    except Exception as exc:
        return _error(f"Failed to evaluate multi-step cases: {exc}")


def run_evaluation(
    eval_path: str | Path,
    index_dir: str | Path,
    csv_path: str | Path = "data/food/foods.csv",
    top_k: int = 5,
    use_chroma: bool = False,
) -> dict[str, Any]:
    """[Agent-Ready] Run the full offline evaluation suite."""
    try:
        load_result = load_eval_cases(eval_path)
        if load_result["status"] == "error":
            return load_result

        cases = load_result["data"]["cases"]
        grouped_cases: dict[str, list[dict[str, Any]]] = {}
        for case in cases:
            grouped_cases.setdefault(str(case["category"]), []).append(case)

        metric_results = {
            "retrieval": evaluate_retrieval_cases(
                grouped_cases.get("retrieval", []),
                index_dir=index_dir,
                top_k=top_k,
                use_chroma=use_chroma,
            ),
            "numeric": evaluate_numeric_cases(grouped_cases.get("numeric", [])),
            "filtering": evaluate_filter_cases(grouped_cases.get("filtering", [])),
            "food": evaluate_food_cases(grouped_cases.get("food", []), csv_path=csv_path),
            "hallucination": evaluate_hallucination_cases(
                grouped_cases.get("hallucination", []),
                index_dir=index_dir,
                top_k=top_k,
                use_chroma=use_chroma,
            ),
            "multistep": evaluate_multistep_cases(
                grouped_cases.get("multistep", []),
                index_dir=index_dir,
                csv_path=csv_path,
                top_k=top_k,
                use_chroma=use_chroma,
            ),
        }

        failed_metrics = [
            name for name, result in metric_results.items() if result["status"] == "error"
        ]
        if failed_metrics:
            raise ValueError(f"Metric groups failed: {', '.join(failed_metrics)}")

        summary = {
            "case_count": len(cases),
            "category_counts": {
                category: len(category_cases)
                for category, category_cases in sorted(grouped_cases.items())
            },
            "retrieval_top_5_hit_rate": metric_results["retrieval"]["data"]["top_k_hit_rate"],
            "numeric_accuracy": metric_results["numeric"]["data"]["accuracy"],
            "contraindication_filter_accuracy": metric_results["filtering"]["data"]["accuracy"],
            "food_query_accuracy": metric_results["food"]["data"]["accuracy"],
            "citation_hallucination_rate": metric_results["hallucination"]["data"][
                "hallucination_rate"
            ],
            "multistep_accuracy": metric_results["multistep"]["data"]["accuracy"],
        }

        return _success(
            {
                "summary": summary,
                "metrics": metric_results,
            },
            "Evaluation suite completed.",
        )
    except Exception as exc:
        return _error(f"Failed to run evaluation: {exc}")

