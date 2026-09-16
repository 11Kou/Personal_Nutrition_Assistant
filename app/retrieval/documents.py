import json
import math
import re
from collections import Counter
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any


def _success(data: Any, message: str) -> dict[str, Any]:
    return {"status": "success", "data": data, "message": message}


def _error(message: str) -> dict[str, Any]:
    return {"status": "error", "data": None, "message": message}


def _supported_document_paths(path: Path) -> list[Path]:
    supported_suffixes = {".md", ".txt", ".pdf"}
    if path.is_file() and path.suffix.lower() in supported_suffixes:
        return [path]
    if path.is_dir():
        return sorted(
            item
            for item in path.rglob("*")
            if item.is_file() and item.suffix.lower() in supported_suffixes
        )
    raise ValueError(f"Unsupported document path: {path}")


def _parse_scalar(value: str) -> Any:
    stripped = value.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        inner = stripped[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("'\"") for item in inner.split(",")]
    if stripped.lower() in {"true", "false"}:
        return stripped.lower() == "true"
    return stripped.strip("'\"")


def _parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text

    lines = text.splitlines()
    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break
    if end_index is None:
        return {}, text

    metadata: dict[str, Any] = {}
    current_list_key: str | None = None
    for line in lines[1:end_index]:
        if not line.strip():
            continue
        if line.startswith("  -") and current_list_key:
            metadata.setdefault(current_list_key, []).append(line.split("-", 1)[1].strip())
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            clean_key = key.strip()
            clean_value = value.strip()
            if clean_value == "":
                metadata[clean_key] = []
                current_list_key = clean_key
            else:
                metadata[clean_key] = _parse_scalar(clean_value)
                current_list_key = None

    body = "\n".join(lines[end_index + 1 :]).strip()
    return metadata, body


def _read_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise RuntimeError("pypdf is required to parse PDF files") from exc

    reader = PdfReader(str(path))
    page_texts = []
    for page in reader.pages:
        page_texts.append(page.extract_text() or "")
    return "\n".join(page_texts).strip()


def _stable_chunk_id(source: str, chunk_index: int, content: str) -> str:
    digest = sha256(f"{source}:{chunk_index}:{content}".encode("utf-8")).hexdigest()
    return digest[:24]


def _tokenize(text: str) -> list[str]:
    normalized = text.lower()
    return re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", normalized)


def _chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap cannot be negative")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    compact_text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if not compact_text:
        raise ValueError("document content cannot be empty")

    chunks = []
    start = 0
    while start < len(compact_text):
        end = min(start + chunk_size, len(compact_text))
        chunks.append(compact_text[start:end].strip())
        if end == len(compact_text):
            break
        start = max(end - chunk_overlap, 0)
    return [chunk for chunk in chunks if chunk]


def _index_path(index_dir: str | Path) -> Path:
    return Path(index_dir) / "bm25_index.json"


def _load_index(index_dir: str | Path) -> dict[str, Any]:
    path = _index_path(index_dir)
    if not path.exists():
        raise FileNotFoundError(f"BM25 index not found: {path}")
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _save_index(index_dir: str | Path, chunks: list[dict[str, Any]]) -> Path:
    directory = Path(index_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = _index_path(directory)
    payload = {
        "created_at": datetime.now(UTC).isoformat(),
        "chunk_count": len(chunks),
        "chunks": chunks,
    }
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    return path


def _hash_embedding(text: str, dimensions: int = 64) -> list[float]:
    values = [0.0] * dimensions
    tokens = _tokenize(text) or [text]
    for token in tokens:
        digest = sha256(token.encode("utf-8")).digest()
        slot = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1 if digest[4] % 2 == 0 else -1
        values[slot] += sign
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


def _sentence_transformer_embeddings(
    texts: list[str],
    embedding_model_name: str,
) -> list[list[float]]:
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:
        raise RuntimeError("sentence-transformers is required for this embedding strategy") from exc

    model = SentenceTransformer(embedding_model_name)
    vectors = model.encode(texts, normalize_embeddings=True)
    return [vector.tolist() for vector in vectors]


def _embed_texts(
    texts: list[str],
    embedding_strategy: str,
    embedding_model_name: str,
) -> list[list[float]]:
    if embedding_strategy == "hash":
        return [_hash_embedding(text) for text in texts]
    if embedding_strategy == "sentence_transformer":
        return _sentence_transformer_embeddings(texts, embedding_model_name)
    raise ValueError("embedding_strategy must be one of: hash, sentence_transformer")


def _metadata_for_chroma(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    chroma_metadata: dict[str, str | int | float | bool] = {}
    for key, value in metadata.items():
        if isinstance(value, str | int | float | bool):
            chroma_metadata[key] = value
        else:
            chroma_metadata[key] = json.dumps(value, ensure_ascii=False)
    return chroma_metadata


def _store_chunks_in_chroma(
    chunks: list[dict[str, Any]],
    index_dir: str | Path,
    collection_name: str,
    embedding_strategy: str,
    embedding_model_name: str,
) -> dict[str, Any]:
    try:
        import chromadb
    except Exception as exc:
        return {
            "stored": False,
            "message": f"Chroma skipped: chromadb is not installed ({exc})",
        }

    if not chunks:
        return {"stored": False, "message": "Chroma skipped: no chunks to store"}

    chroma_dir = Path(index_dir) / "chroma"
    client = chromadb.PersistentClient(path=str(chroma_dir))
    collection = client.get_or_create_collection(name=collection_name)
    documents = [chunk["content"] for chunk in chunks]
    embeddings = _embed_texts(documents, embedding_strategy, embedding_model_name)

    collection.upsert(
        ids=[chunk["id"] for chunk in chunks],
        documents=documents,
        embeddings=embeddings,
        metadatas=[_metadata_for_chroma(chunk["metadata"]) for chunk in chunks],
    )
    return {
        "stored": True,
        "message": f"Stored {len(chunks)} chunks in Chroma.",
    }


def _bm25_scores(query: str, chunks: list[dict[str, Any]]) -> dict[str, float]:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return {}

    tokenized_docs = [_tokenize(chunk["content"]) for chunk in chunks]
    doc_count = len(tokenized_docs)
    if doc_count == 0:
        return {}

    doc_freq = Counter()
    for tokens in tokenized_docs:
        doc_freq.update(set(tokens))

    avg_doc_len = sum(len(tokens) for tokens in tokenized_docs) / doc_count
    avg_doc_len = avg_doc_len or 1
    k1 = 1.5
    b = 0.75
    scores: dict[str, float] = {}

    for chunk, doc_tokens in zip(chunks, tokenized_docs, strict=True):
        token_counts = Counter(doc_tokens)
        doc_len = len(doc_tokens) or 1
        score = 0.0
        for token in query_tokens:
            if token_counts[token] == 0:
                continue
            idf = math.log((doc_count - doc_freq[token] + 0.5) / (doc_freq[token] + 0.5) + 1)
            numerator = token_counts[token] * (k1 + 1)
            denominator = token_counts[token] + k1 * (1 - b + b * doc_len / avg_doc_len)
            score += idf * numerator / denominator
        if score > 0:
            scores[chunk["id"]] = score
    return scores


def _query_chroma_scores(
    query: str,
    index_dir: str | Path,
    collection_name: str,
    embedding_strategy: str,
    embedding_model_name: str,
    top_k: int,
) -> dict[str, float]:
    try:
        import chromadb
    except Exception:
        return {}

    chroma_dir = Path(index_dir) / "chroma"
    if not chroma_dir.exists():
        return {}

    try:
        client = chromadb.PersistentClient(path=str(chroma_dir))
        collection = client.get_collection(name=collection_name)
        query_embedding = _embed_texts([query], embedding_strategy, embedding_model_name)[0]
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=max(top_k * 3, top_k),
            include=["distances"],
        )
    except Exception:
        return {}

    ids = result.get("ids", [[]])[0]
    distances = result.get("distances", [[]])[0]
    return {
        chunk_id: 1 / (1 + float(distance))
        for chunk_id, distance in zip(ids, distances, strict=False)
    }


def _normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    max_score = max(scores.values()) or 1.0
    return {key: value / max_score for key, value in scores.items()}


def _metadata_values(metadata: dict[str, Any], key: str) -> list[str]:
    value = metadata.get(key)
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).lower() for item in value]
    return [str(value).lower()]


def _overlaps(metadata: dict[str, Any], key: str, expected_values: Any) -> bool:
    values = _metadata_values(metadata, key)
    if not values:
        return False
    expected = expected_values if isinstance(expected_values, list) else [expected_values]
    expected = [str(item).lower() for item in expected]
    return any(item in values for item in expected)


def _passes_filters(chunk: dict[str, Any], filters: dict[str, Any] | None) -> bool:
    if not filters:
        return True

    metadata = chunk.get("metadata", {})
    content = str(chunk.get("content", "")).lower()

    for term in filters.get("exclude_terms", []):
        if str(term).lower() in content:
            return False

    for key, expected_values in filters.get("include_metadata", {}).items():
        if not _overlaps(metadata, key, expected_values):
            return False

    for key, expected_values in filters.get("exclude_metadata", {}).items():
        if _overlaps(metadata, key, expected_values):
            return False

    for key, expected_values in filters.items():
        if key.startswith("exclude_") and key not in {"exclude_terms", "exclude_metadata"}:
            metadata_key = key.removeprefix("exclude_")
            if _overlaps(metadata, metadata_key, expected_values):
                return False
        if key.startswith("required_"):
            metadata_key = key.removeprefix("required_")
            metadata_values = _metadata_values(metadata, metadata_key)
            if metadata_values and not _overlaps(metadata, metadata_key, expected_values):
                return False

    return True


def parse_document(file_path: str | Path) -> dict[str, Any]:
    """[Agent-Ready] Parse a .md, .txt, or .pdf document into structured text."""
    try:
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Document file not found: {path}")

        suffix = path.suffix.lower()
        if suffix in {".md", ".txt"}:
            raw_text = path.read_text(encoding="utf-8-sig")
        elif suffix == ".pdf":
            raw_text = _read_pdf_text(path)
        else:
            raise ValueError("Only .md, .txt, and .pdf files are supported")

        front_matter, content = _parse_front_matter(raw_text)
        if not content.strip():
            raise ValueError("Document has no extractable text")

        metadata = {
            **front_matter,
            "source": str(path),
            "file_name": path.name,
            "file_type": suffix.removeprefix("."),
        }

        return _success(
            {
                "content": content.strip(),
                "source": str(path),
                "metadata": metadata,
            },
            "Document parsed.",
        )
    except Exception as exc:
        return _error(f"Failed to parse document: {exc}")


def load_documents(document_paths: list[str | Path]) -> dict[str, Any]:
    """[Agent-Ready] Load supported documents from files or directories."""
    try:
        if not isinstance(document_paths, list) or not document_paths:
            raise ValueError("document_paths must be a non-empty list")

        paths: list[Path] = []
        for item in document_paths:
            paths.extend(_supported_document_paths(Path(item)))

        documents = []
        errors = []
        for path in paths:
            result = parse_document(path)
            if result["status"] == "success":
                documents.append(result["data"])
            else:
                errors.append({"path": str(path), "message": result["message"]})

        if not documents:
            raise ValueError(f"No documents loaded. Errors: {errors}")

        return _success(
            {
                "documents": documents,
                "errors": errors,
            },
            f"Loaded {len(documents)} documents.",
        )
    except Exception as exc:
        return _error(f"Failed to load documents: {exc}")


def chunk_documents(
    documents: list[dict[str, Any]],
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> dict[str, Any]:
    """[Agent-Ready] Split parsed documents into retrieval chunks."""
    try:
        if not isinstance(documents, list) or not documents:
            raise ValueError("documents must be a non-empty list")

        chunks = []
        for document in documents:
            content = str(document.get("content", "")).strip()
            source = str(document.get("source", "")).strip()
            metadata = document.get("metadata", {})
            if not source:
                raise ValueError("each document must include source")
            for index, chunk_text in enumerate(_chunk_text(content, chunk_size, chunk_overlap)):
                chunk_metadata = {
                    **metadata,
                    "chunk_index": index,
                    "source": source,
                }
                chunks.append(
                    {
                        "id": _stable_chunk_id(source, index, chunk_text),
                        "content": chunk_text,
                        "source": source,
                        "metadata": chunk_metadata,
                    }
                )

        return _success({"chunks": chunks}, f"Created {len(chunks)} chunks.")
    except Exception as exc:
        return _error(f"Failed to chunk documents: {exc}")


def ingest_documents(
    document_paths: list[str | Path],
    index_dir: str | Path,
    collection_name: str = "rag_documents",
    chunk_size: int = 800,
    chunk_overlap: int = 120,
    use_chroma: bool = True,
    embedding_strategy: str = "hash",
    embedding_model_name: str = "BAAI/bge-small-zh-v1.5",
) -> dict[str, Any]:
    """[Agent-Ready] Parse, chunk, and index documents for BM25 and optional Chroma retrieval."""
    try:
        load_result = load_documents(document_paths)
        if load_result["status"] == "error":
            return load_result

        chunk_result = chunk_documents(
            load_result["data"]["documents"],
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        if chunk_result["status"] == "error":
            return chunk_result

        chunks = chunk_result["data"]["chunks"]
        bm25_path = _save_index(index_dir, chunks)
        chroma_status = {"stored": False, "message": "Chroma disabled."}
        if use_chroma:
            chroma_status = _store_chunks_in_chroma(
                chunks,
                index_dir=index_dir,
                collection_name=collection_name,
                embedding_strategy=embedding_strategy,
                embedding_model_name=embedding_model_name,
            )

        return _success(
            {
                "document_count": len(load_result["data"]["documents"]),
                "chunk_count": len(chunks),
                "bm25_index_path": str(bm25_path),
                "chroma": chroma_status,
                "load_errors": load_result["data"]["errors"],
            },
            f"Indexed {len(chunks)} chunks. {chroma_status['message']}",
        )
    except Exception as exc:
        return _error(f"Failed to ingest documents: {exc}")


def retrieve_documents(
    query: str,
    index_dir: str | Path,
    filters: dict[str, Any] | None = None,
    top_k: int = 5,
    collection_name: str = "rag_documents",
    use_chroma: bool = True,
    embedding_strategy: str = "hash",
    embedding_model_name: str = "BAAI/bge-small-zh-v1.5",
) -> dict[str, Any]:
    """[Agent-Ready] Retrieve chunks with BM25 plus optional Chroma vector scores."""
    try:
        cleaned_query = str(query).strip()
        if not cleaned_query:
            raise ValueError("query cannot be empty")
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        index = _load_index(index_dir)
        chunks = index.get("chunks", [])
        if not chunks:
            raise ValueError("BM25 index contains no chunks")

        candidate_chunks = [chunk for chunk in chunks if _passes_filters(chunk, filters)]
        if not candidate_chunks:
            return _success([], "No documents matched the filters.")

        bm25 = _normalize_scores(_bm25_scores(cleaned_query, candidate_chunks))
        vector = {}
        if use_chroma:
            vector = _normalize_scores(
                _query_chroma_scores(
                    cleaned_query,
                    index_dir=index_dir,
                    collection_name=collection_name,
                    embedding_strategy=embedding_strategy,
                    embedding_model_name=embedding_model_name,
                    top_k=top_k,
                )
            )

        scored_chunks = []
        for chunk in candidate_chunks:
            chunk_id = chunk["id"]
            score = 0.7 * bm25.get(chunk_id, 0) + 0.3 * vector.get(chunk_id, 0)
            if score > 0:
                scored_chunks.append(
                    {
                        "content": chunk["content"],
                        "source": chunk["source"],
                        "score": round(score, 6),
                        "metadata": chunk["metadata"],
                    }
                )

        scored_chunks.sort(key=lambda item: item["score"], reverse=True)
        return _success(
            scored_chunks[:top_k],
            f"Retrieved {min(len(scored_chunks), top_k)} documents.",
        )
    except Exception as exc:
        return _error(f"Failed to retrieve documents: {exc}")
