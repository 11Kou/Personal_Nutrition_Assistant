import re
from typing import Any

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


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", str(text).lower())


def _extract_chunks(chunks_or_result: Any) -> list[dict[str, Any]]:
    if isinstance(chunks_or_result, dict):
        if chunks_or_result.get("status") == "success" and isinstance(
            chunks_or_result.get("data"), list
        ):
            return chunks_or_result["data"]
        raise ValueError("chunks_or_result must be a chunk list or successful result")
    if isinstance(chunks_or_result, list):
        return chunks_or_result
    raise TypeError("chunks_or_result must be a list or result dictionary")


def _validate_chunk(chunk: dict[str, Any]) -> None:
    if not isinstance(chunk, dict):
        raise TypeError("each chunk must be a dictionary")
    missing_keys = {"content", "source", "score", "metadata"} - set(chunk.keys())
    if missing_keys:
        raise ValueError(f"chunk missing required keys: {', '.join(sorted(missing_keys))}")
    if not isinstance(chunk["metadata"], dict):
        raise TypeError("chunk metadata must be a dictionary")


def _safe_snippet(content: str, max_chars: int = 180) -> str:
    compact = re.sub(r"\s+", " ", str(content)).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def _profile_hints(profile_data: dict[str, Any]) -> list[str]:
    hints = []
    for key in ["goal", "injuries", "diet_preferences", "training_conditions"]:
        value = profile_data.get(key)
        if isinstance(value, list) and value:
            hints.append(f"{key}: {', '.join(str(item) for item in value)}")
        elif value:
            hints.append(f"{key}: {value}")
    return hints


def _medical_warnings(question: str) -> list[str]:
    terms = [
        "疼痛",
        "受伤",
        "疾病",
        "治疗",
        "诊断",
        "用药",
        "糖尿病",
        "高血压",
        "肾病",
        "痛风",
        "injury",
        "pain",
        "disease",
        "diagnosis",
        "treatment",
    ]
    normalized_question = str(question).lower()
    if any(term.lower() in normalized_question for term in terms):
        return ["涉及疾病、伤病、诊断、治疗或用药时，请咨询医生、物理治疗师或注册营养师。"]
    return []


def _format_sources(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources = []
    for index, chunk in enumerate(chunks, start=1):
        metadata = chunk.get("metadata", {})
        title = (
            metadata.get("title")
            or metadata.get("source_title")
            or metadata.get("file_name")
            or chunk["source"]
        )
        sources.append(
            {
                "index": index,
                "title": str(title),
                "source": chunk["source"],
                "snippet": _safe_snippet(chunk["content"]),
                "score": chunk["score"],
                "metadata": metadata,
            }
        )
    return sources


def _format_optional_evidence(name: str, items: Any) -> list[str]:
    values = _as_list(items)
    if not values:
        return []
    lines = [f"{name}："]
    for item in values:
        if isinstance(item, dict):
            lines.append(f"- {item}")
        else:
            lines.append(f"- {item}")
    return lines


def rewrite_query(question: str, profile_data: dict[str, Any]) -> dict[str, Any]:
    """[Agent-Ready] Rewrite a user question with lightweight profile hints for retrieval."""
    try:
        cleaned_question = str(question).strip()
        if not cleaned_question:
            raise ValueError("question cannot be empty")
        if not isinstance(profile_data, dict):
            raise TypeError("profile_data must be a dictionary")

        hints = _profile_hints(profile_data)
        rewritten_query = cleaned_question
        if hints:
            rewritten_query = f"{cleaned_question}\n用户画像：{'; '.join(hints)}"

        return _success(
            {
                "query": rewritten_query,
                "original_question": cleaned_question,
                "profile_hints": hints,
            },
            "Query rewritten.",
        )
    except Exception as exc:
        return _error(f"Failed to rewrite query: {exc}")


def rerank_documents(
    question: str,
    chunks_or_result: list[dict[str, Any]] | dict[str, Any],
    top_k: int = 5,
) -> dict[str, Any]:
    """[Agent-Ready] Rerank retrieved chunks with keyword overlap and existing scores."""
    try:
        cleaned_question = str(question).strip()
        if not cleaned_question:
            raise ValueError("question cannot be empty")
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        chunks = _extract_chunks(chunks_or_result)
        question_tokens = set(_tokenize(cleaned_question))
        reranked_chunks = []

        for chunk in chunks:
            _validate_chunk(chunk)
            content_tokens = set(_tokenize(chunk["content"]))
            overlap = len(question_tokens & content_tokens)
            overlap_score = overlap / max(len(question_tokens), 1)
            original_score = float(chunk["score"])
            rerank_score = round(0.75 * original_score + 0.25 * overlap_score, 6)
            reranked_chunk = {
                "content": chunk["content"],
                "source": chunk["source"],
                "score": rerank_score,
                "metadata": {
                    **chunk["metadata"],
                    "original_score": original_score,
                    "rerank_overlap_score": round(overlap_score, 6),
                },
            }
            reranked_chunks.append(reranked_chunk)

        reranked_chunks.sort(key=lambda item: item["score"], reverse=True)
        return _success(reranked_chunks[:top_k], f"Reranked {len(reranked_chunks[:top_k])} chunks.")
    except Exception as exc:
        return _error(f"Failed to rerank documents: {exc}")


def generate_answer(
    question: str,
    chunks_or_result: list[dict[str, Any]] | dict[str, Any],
    profile_data: dict[str, Any] | None = None,
    calculations: Any = None,
    foods: Any = None,
) -> dict[str, Any]:
    """[Agent-Ready] Generate a source-grounded answer from retrieved chunks."""
    try:
        cleaned_question = str(question).strip()
        if not cleaned_question:
            raise ValueError("question cannot be empty")

        chunks = _extract_chunks(chunks_or_result)
        for chunk in chunks:
            _validate_chunk(chunk)

        warnings = _medical_warnings(cleaned_question)
        if not chunks:
            return _success(
                {
                    "answer": "没有在本地知识库中找到可靠来源，因此我不能基于 RAG 资料给出确定回答。",
                    "sources": [],
                    "warnings": warnings,
                    "used_calculations": _as_list(calculations),
                    "used_foods": _as_list(foods),
                },
                "No reliable sources found.",
            )

        sources = _format_sources(chunks)
        answer_lines = [
            "根据本地知识库检索到的资料，可以参考以下信息：",
        ]
        for source in sources:
            answer_lines.append(f"[{source['index']}] {source['snippet']}")

        if profile_data:
            hints = _profile_hints(profile_data)
            if hints:
                answer_lines.append(f"已结合用户画像：{'; '.join(hints)}。")

        answer_lines.extend(_format_optional_evidence("已注入计算结果", calculations))
        answer_lines.extend(_format_optional_evidence("已注入食物数据", foods))
        if warnings:
            answer_lines.extend(warnings)

        return _success(
            {
                "answer": "\n".join(answer_lines),
                "sources": sources,
                "warnings": warnings,
                "used_calculations": _as_list(calculations),
                "used_foods": _as_list(foods),
            },
            "Source-grounded answer generated.",
        )
    except Exception as exc:
        return _error(f"Failed to generate answer: {exc}")


def answer_question_with_rag(
    question: str,
    profile_data: dict[str, Any],
    index_dir: str,
    top_k: int = 5,
    use_chroma: bool = False,
    calculations: Any = None,
    foods: Any = None,
) -> dict[str, Any]:
    """[Agent-Ready] Run the RAG flow: rewrite, filter, retrieve, safety-check, rerank, answer."""
    try:
        query_result = rewrite_query(question, profile_data)
        if query_result["status"] == "error":
            return query_result

        filters_result = build_filters(profile_data)
        if filters_result["status"] == "error":
            return filters_result

        retrieval_result = retrieve_documents(
            query=query_result["data"]["query"],
            index_dir=index_dir,
            filters=filters_result["data"],
            top_k=max(top_k * 2, top_k),
            use_chroma=use_chroma,
        )
        if retrieval_result["status"] == "error":
            return retrieval_result

        safe_result = filter_by_profile(retrieval_result, profile_data)
        if safe_result["status"] == "error":
            return safe_result

        rerank_result = rerank_documents(
            question,
            safe_result["data"]["safe_chunks"],
            top_k=top_k,
        )
        if rerank_result["status"] == "error":
            return rerank_result

        answer_result = generate_answer(
            question,
            rerank_result["data"],
            profile_data=profile_data,
            calculations=calculations,
            foods=foods,
        )
        if answer_result["status"] == "error":
            return answer_result

        answer_data = {
            **answer_result["data"],
            "query": query_result["data"],
            "filters": filters_result["data"],
            "removed_chunks": safe_result["data"]["removed_chunks"],
        }
        return _success(answer_data, "RAG answer flow completed.")
    except Exception as exc:
        return _error(f"Failed to answer question with RAG: {exc}")
