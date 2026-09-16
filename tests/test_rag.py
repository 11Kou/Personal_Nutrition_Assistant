from app.rag.flow import (
    answer_question_with_rag,
    generate_answer,
    rerank_documents,
    rewrite_query,
)
from app.retrieval.documents import ingest_documents


def assert_result_shape(result):
    assert set(result.keys()) == {"status", "data", "message"}
    assert result["status"] in {"success", "error"}
    assert isinstance(result["message"], str)


def sample_profile():
    return {
        "user_id": "user-1",
        "goal": "fat_loss",
        "injuries": ["膝伤"],
        "diet_preferences": ["乳糖不耐"],
        "training_conditions": ["居家"],
    }


def sample_chunk(content="膝伤用户可以优先选择低冲击训练，例如固定自行车。", score=0.9):
    return {
        "content": content,
        "source": "knee.md",
        "score": score,
        "metadata": {
            "title": "膝关节康复指南",
            "actions": ["固定自行车"],
            "training_conditions": ["居家"],
        },
    }


def write_doc(path, title, body, extra_metadata=None):
    extra_metadata = extra_metadata or []
    metadata_lines = [
        "---",
        f"title: {title}",
        "training_conditions: [居家]",
        *extra_metadata,
        "---",
        "",
        f"# {title}",
        "",
        body,
    ]
    path.write_text("\n".join(metadata_lines), encoding="utf-8")


def test_rewrite_query_injects_profile_hints():
    result = rewrite_query("膝伤怎么训练？", sample_profile())

    assert_result_shape(result)
    assert result["status"] == "success"
    assert "膝伤怎么训练？" in result["data"]["query"]
    assert "injuries: 膝伤" in result["data"]["query"]


def test_rewrite_query_rejects_empty_question():
    result = rewrite_query(" ", sample_profile())

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None


def test_rerank_documents_returns_required_chunk_contract():
    chunks = [
        sample_chunk("固定自行车适合膝伤低冲击训练。", 0.5),
        sample_chunk("蛋白质需要结合体重计算。", 0.9),
    ]

    result = rerank_documents("膝伤 低冲击 固定自行车", chunks, top_k=1)

    assert_result_shape(result)
    assert result["status"] == "success"
    assert len(result["data"]) == 1
    assert set(result["data"][0].keys()) == {"content", "source", "score", "metadata"}
    assert "original_score" in result["data"][0]["metadata"]


def test_rerank_documents_rejects_bad_chunk_shape():
    result = rerank_documents("question", [{"content": "bad"}])

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None


def test_generate_answer_with_sources_and_warning():
    result = generate_answer("膝盖疼痛怎么训练？", [sample_chunk()], sample_profile())

    assert_result_shape(result)
    assert result["status"] == "success"
    assert "### 回答" in result["data"]["answer"]
    assert "### 关键依据" in result["data"]["answer"]
    assert "### 已结合用户画像" in result["data"]["answer"]
    assert "### 来源" in result["data"]["answer"]
    assert "[1]" in result["data"]["answer"]
    assert len(result["data"]["sources"]) == 1
    assert result["data"]["sources"][0]["title"] == "膝关节康复指南"
    assert result["data"]["warnings"]


def test_generate_answer_refuses_when_no_sources():
    result = generate_answer("这个问题知识库没有资料", [], sample_profile())

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["sources"] == []
    assert "没有在本地知识库中找到可靠来源" in result["data"]["answer"]


def test_generate_answer_includes_injected_calculations_and_foods():
    result = generate_answer(
        "训练后吃什么？",
        [sample_chunk("训练后可结合总热量目标安排蛋白质来源。")],
        sample_profile(),
        calculations=[{"name": "TDEE", "result": 2200}],
        foods=[{"matched_name": "鸡胸肉"}],
    )

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["used_calculations"] == [{"name": "TDEE", "result": 2200}]
    assert result["data"]["used_foods"] == [{"matched_name": "鸡胸肉"}]
    assert "已注入计算结果" in result["data"]["answer"]


def test_answer_question_with_rag_completes_flow(tmp_path):
    document_dir = tmp_path / "docs"
    index_dir = tmp_path / "index"
    document_dir.mkdir()
    write_doc(
        document_dir / "safe.md",
        "膝伤低冲击训练",
        "膝伤用户可以选择固定自行车、核心训练和上肢训练，避免疼痛加重。",
    )
    ingest_documents([document_dir], index_dir=index_dir, use_chroma=False)

    result = answer_question_with_rag(
        "膝伤用户怎么做居家训练？",
        sample_profile(),
        str(index_dir),
        use_chroma=False,
    )

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["sources"]
    assert "固定自行车" in result["data"]["answer"]
    assert "filters" in result["data"]


def test_answer_question_with_rag_filters_unsafe_retrieved_chunks(tmp_path):
    document_dir = tmp_path / "docs"
    index_dir = tmp_path / "index"
    document_dir.mkdir()
    write_doc(
        document_dir / "unsafe.md",
        "膝伤训练误区",
        "膝伤用户不应把深蹲和跳跃作为默认训练建议。",
        ["actions: [深蹲, 跳跃]"],
    )
    ingest_documents([document_dir], index_dir=index_dir, use_chroma=False)

    result = answer_question_with_rag(
        "膝伤能不能深蹲？",
        sample_profile(),
        str(index_dir),
        use_chroma=False,
    )

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["sources"] == []
    assert "没有在本地知识库中找到可靠来源" in result["data"]["answer"]


def test_answer_question_with_rag_returns_error_for_missing_index(tmp_path):
    result = answer_question_with_rag(
        "蛋白质怎么吃？",
        sample_profile(),
        str(tmp_path / "missing"),
        use_chroma=False,
    )

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None
