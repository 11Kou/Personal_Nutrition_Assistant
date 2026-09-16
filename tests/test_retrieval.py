from app.retrieval.documents import (
    chunk_documents,
    ingest_documents,
    load_documents,
    parse_document,
    retrieve_documents,
)


def assert_result_shape(result):
    assert set(result.keys()) == {"status", "data", "message"}
    assert result["status"] in {"success", "error"}
    assert isinstance(result["message"], str)


def write_markdown(path, title="Knee guide", body=None):
    body = body or "膝伤用户应避免深蹲和跳跃。固定自行车和低冲击训练更合适。"
    path.write_text(
        "\n".join(
            [
                "---",
                f"title: {title}",
                "topic: training",
                "contraindicated_actions: [深蹲, 跳跃]",
                "equipment: [自行车]",
                "---",
                "",
                f"# {title}",
                "",
                body,
            ]
        ),
        encoding="utf-8",
    )


def test_parse_document_reads_markdown_front_matter(tmp_path):
    path = tmp_path / "knee.md"
    write_markdown(path)

    result = parse_document(path)

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["metadata"]["title"] == "Knee guide"
    assert result["data"]["metadata"]["contraindicated_actions"] == ["深蹲", "跳跃"]
    assert "膝伤用户" in result["data"]["content"]


def test_parse_document_rejects_missing_file(tmp_path):
    result = parse_document(tmp_path / "missing.md")

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None


def test_load_documents_reads_directory(tmp_path):
    write_markdown(tmp_path / "one.md", title="one")
    (tmp_path / "two.txt").write_text("蛋白质摄入应结合体重计算。", encoding="utf-8")

    result = load_documents([tmp_path])

    assert_result_shape(result)
    assert result["status"] == "success"
    assert len(result["data"]["documents"]) == 2


def test_chunk_documents_creates_stable_chunk_shape(tmp_path):
    path = tmp_path / "knee.md"
    write_markdown(path, body="a" * 220)
    document = parse_document(path)["data"]

    result = chunk_documents([document], chunk_size=100, chunk_overlap=20)

    assert_result_shape(result)
    assert result["status"] == "success"
    chunks = result["data"]["chunks"]
    assert len(chunks) >= 2
    assert set(chunks[0].keys()) == {"id", "content", "source", "metadata"}
    assert chunks[0]["metadata"]["chunk_index"] == 0


def test_chunk_documents_rejects_bad_overlap(tmp_path):
    path = tmp_path / "knee.md"
    write_markdown(path)
    document = parse_document(path)["data"]

    result = chunk_documents([document], chunk_size=100, chunk_overlap=100)

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None


def test_ingest_documents_writes_bm25_index(tmp_path):
    document_dir = tmp_path / "docs"
    index_dir = tmp_path / "index"
    document_dir.mkdir()
    write_markdown(document_dir / "knee.md")

    result = ingest_documents([document_dir], index_dir=index_dir, use_chroma=False)

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["document_count"] == 1
    assert result["data"]["chunk_count"] >= 1
    assert (index_dir / "bm25_index.json").exists()


def test_retrieve_documents_returns_required_chunk_contract(tmp_path):
    document_dir = tmp_path / "docs"
    index_dir = tmp_path / "index"
    document_dir.mkdir()
    write_markdown(document_dir / "knee.md")
    ingest_documents([document_dir], index_dir=index_dir, use_chroma=False)

    result = retrieve_documents("膝伤 低冲击 训练", index_dir=index_dir, use_chroma=False)

    assert_result_shape(result)
    assert result["status"] == "success"
    assert len(result["data"]) >= 1
    first = result["data"][0]
    assert set(first.keys()) == {"content", "source", "score", "metadata"}
    assert isinstance(first["score"], float)


def test_retrieve_documents_applies_metadata_filters(tmp_path):
    document_dir = tmp_path / "docs"
    index_dir = tmp_path / "index"
    document_dir.mkdir()
    write_markdown(document_dir / "knee.md")
    ingest_documents([document_dir], index_dir=index_dir, use_chroma=False)

    result = retrieve_documents(
        "深蹲 膝伤",
        index_dir=index_dir,
        filters={"exclude_contraindicated_actions": ["深蹲"]},
        use_chroma=False,
    )

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"] == []


def test_retrieve_documents_does_not_drop_untagged_chunks_for_required_filters(tmp_path):
    document_dir = tmp_path / "docs"
    index_dir = tmp_path / "index"
    document_dir.mkdir()
    (document_dir / "home.md").write_text(
        "# 居家训练\n居家锻炼可以结合核心训练和低冲击有氧。",
        encoding="utf-8",
    )
    ingest_documents([document_dir], index_dir=index_dir, use_chroma=False)

    result = retrieve_documents(
        "居家 锻炼",
        index_dir=index_dir,
        filters={"required_training_conditions": ["居家"]},
        use_chroma=False,
    )

    assert_result_shape(result)
    assert result["status"] == "success"
    assert len(result["data"]) == 1


def test_retrieve_documents_rejects_empty_query(tmp_path):
    result = retrieve_documents(" ", index_dir=tmp_path, use_chroma=False)

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None


def test_retrieve_documents_returns_error_for_missing_index(tmp_path):
    result = retrieve_documents("protein", index_dir=tmp_path, use_chroma=False)

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None
