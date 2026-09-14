from __future__ import annotations

from collections.abc import Sequence

import pytest

from tech_ai.errors import KnowledgeRetrievalError, TranslationError
from tech_ai.models.knowledge import KnowledgeSearchResult
from tech_ai.services.knowledge_retrieval_service import KnowledgeRetrievalService


class StubEmbeddingClient:
    def __init__(self, embeddings: tuple[tuple[float, ...], ...]) -> None:
        self.embeddings = embeddings
        self.received: Sequence[str] = ()

    def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        self.received = texts
        return self.embeddings


class StubKnowledgeRepository:
    def __init__(self, results: tuple[KnowledgeSearchResult, ...] = ()) -> None:
        self.results = results
        self.received_embedding: Sequence[float] = ()
        self.received_limit = 0

    def query(
        self,
        embedding: Sequence[float],
        *,
        limit: int,
    ) -> tuple[KnowledgeSearchResult, ...]:
        self.received_embedding = embedding
        self.received_limit = limit
        return self.results


def test_search_embeds_normalized_query_and_queries_repository() -> None:
    expected = (
        KnowledgeSearchResult("id-1", "texto", {"focus": "asma"}, 0.1),
    )
    embedding = StubEmbeddingClient(((0.1, 0.2),))
    repository = StubKnowledgeRepository(expected)

    result = KnowledgeRetrievalService(embedding, repository).search("  asma  ", limit=3)

    assert result == expected
    assert embedding.received == ["asma"]
    assert repository.received_embedding == (0.1, 0.2)
    assert repository.received_limit == 3


@pytest.mark.parametrize(("query", "limit"), [(" ", 1), ("asma", 0)])
def test_search_rejects_invalid_input(query: str, limit: int) -> None:
    service = KnowledgeRetrievalService(StubEmbeddingClient(((1.0,),)), StubKnowledgeRepository())

    with pytest.raises(KnowledgeRetrievalError):
        service.search(query, limit=limit)


def test_search_rejects_unexpected_embedding_count() -> None:
    service = KnowledgeRetrievalService(StubEmbeddingClient(()), StubKnowledgeRepository())

    with pytest.raises(KnowledgeRetrievalError, match="exatamente um"):
        service.search("asma", limit=1)


def test_search_filters_results_above_maximum_distance() -> None:
    results = (
        KnowledgeSearchResult("close", "texto", {}, 0.3),
        KnowledgeSearchResult("limit", "texto", {}, 0.55),
        KnowledgeSearchResult("far", "texto", {}, 0.56),
    )
    service = KnowledgeRetrievalService(
        StubEmbeddingClient(((1.0,),)),
        StubKnowledgeRepository(results),
        max_distance=0.55,
    )

    assert [result.record_id for result in service.search("asma", limit=3)] == [
        "close",
        "limit",
    ]


class StubTranslator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def translate(self, text: str, *, source: str, target: str) -> str:
        self.calls.append((text, source, target))
        if target == "en":
            return "What is stress?"
        return f"PT {text}"


def test_search_translates_portuguese_query_and_localizes_evidence() -> None:
    english = KnowledgeSearchResult(
        record_id="id-1",
        text="Medical topic: Stress\nQuestion: What is stress?\nAnswer: Stress is a response.",
        metadata={"focus": "Stress", "source_url": "https://example.test/stress"},
        distance=0.2,
    )
    embedding = StubEmbeddingClient(((0.4,),))
    translator = StubTranslator()
    service = KnowledgeRetrievalService(
        embedding,
        StubKnowledgeRepository((english,)),
        translator=translator,
    )

    results = service.search("O que é estresse?", limit=1)

    assert embedding.received == ["What is stress?"]
    assert results[0].text == (
        "Tópico médico: PT Stress\nPergunta: PT What is stress?\nResposta: PT Stress is a response."
    )
    assert results[0].focus == "PT Stress"
    assert ("O que é estresse?", "pt", "en") in translator.calls


def test_search_keeps_english_query_for_embedding() -> None:
    embedding = StubEmbeddingClient(((0.4,),))
    translator = StubTranslator()
    service = KnowledgeRetrievalService(
        embedding,
        StubKnowledgeRepository(()),
        translator=translator,
    )

    service.search("What is stress?", limit=1)

    assert embedding.received == ["What is stress?"]
    assert all(source != "pt" for _text, source, _target in translator.calls)


def test_search_wraps_translation_failures() -> None:
    class BrokenTranslator:
        def translate(self, text: str, *, source: str, target: str) -> str:
            del text, source, target
            raise TranslationError("falha de tradução")

    service = KnowledgeRetrievalService(
        StubEmbeddingClient(((0.4,),)),
        StubKnowledgeRepository(()),
        translator=BrokenTranslator(),
    )

    with pytest.raises(KnowledgeRetrievalError, match="falha de tradução"):
        service.search("O que é estresse?", limit=1)


def test_retrieval_service_rejects_invalid_maximum_distance() -> None:
    with pytest.raises(KnowledgeRetrievalError, match="max_distance"):
        KnowledgeRetrievalService(
            StubEmbeddingClient(((1.0,),)),
            StubKnowledgeRepository(),
            max_distance=0,
        )
