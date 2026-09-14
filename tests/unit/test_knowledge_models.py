from __future__ import annotations

from tech_ai.models.knowledge import KnowledgeCitation, KnowledgeSearchResult


def test_citation_projects_supported_metadata() -> None:
    result = KnowledgeSearchResult(
        record_id="id-1",
        text="texto",
        metadata={"focus": "Asma", "source_url": "https://example.test", "count": 2},
        distance=0.12,
    )

    citation = KnowledgeCitation.from_result(result, number=1)

    assert citation.as_dict() == {
        "citation": "[1]",
        "record_id": "id-1",
        "document_id": None,
        "chunk_id": "id-1",
        "distance": 0.12,
        "focus": "Asma",
        "source_url": "https://example.test",
    }
    assert result.as_dict()["text"] == "texto"
    assert result.as_dict()["chunk_id"] == "id-1"


def test_citation_ignores_non_string_optional_metadata() -> None:
    result = KnowledgeSearchResult("id-1", "texto", {"focus": 1}, 0.3)

    citation = KnowledgeCitation.from_result(result, number=1)

    assert citation.focus is None
    assert citation.source_url is None
    assert citation.chunk_id == "id-1"
    assert citation.document_id is None


def test_citation_uses_parent_record_and_chunk_metadata() -> None:
    result = KnowledgeSearchResult(
        record_id="chunk-2",
        text="texto",
        metadata={
            "document_id": "doc-pai",
            "chunk_id": "chunk-2",
            "focus": "Estresse",
            "source_url": "https://example.test/stress",
        },
        distance=0.4,
    )

    citation = KnowledgeCitation.from_result(result, number=2)

    assert citation.record_id == "doc-pai"
    assert citation.document_id == "doc-pai"
    assert citation.chunk_id == "chunk-2"
    assert result.as_dict()["record_id"] == "doc-pai"
    assert result.as_dict()["distance"] == 0.4


def test_citation_prefers_parent_record_id_over_document_id() -> None:
    result = KnowledgeSearchResult(
        record_id="chroma-id",
        text="texto",
        metadata={
            "document_id": "doc-pai",
            "parent_record_id": "registro-pai",
            "chunk_id": "registro-pai::chunk::0001",
            "focus": "Estresse",
            "source_url": "https://example.test/stress",
        },
        distance=0.34,
    )

    citation = KnowledgeCitation.from_result(result, number=1)
    payload = result.as_dict()

    assert citation.record_id == "registro-pai"
    assert citation.document_id == "doc-pai"
    assert citation.chunk_id == "registro-pai::chunk::0001"
    assert payload["record_id"] == "registro-pai"
    assert payload["chunk_id"] == "registro-pai::chunk::0001"
