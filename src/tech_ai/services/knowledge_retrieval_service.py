"""Caso de uso de recuperação semântica do MedQuAD."""

from __future__ import annotations

from tech_ai.errors import KnowledgeRetrievalError, TranslationError
from tech_ai.integrations.embeddings.client import EmbeddingClient
from tech_ai.integrations.translation.client import TranslationClient
from tech_ai.integrations.translation.documents import localize_search_result
from tech_ai.integrations.translation.language import looks_english, looks_portuguese
from tech_ai.models.knowledge import KnowledgeSearchResult
from tech_ai.repositories.knowledge_repository import KnowledgeRepository


class KnowledgeRetrievalService:
    """Coordena embedding da pergunta e busca somente-leitura no ChromaDB."""

    def __init__(
        self,
        embedding_client: EmbeddingClient,
        repository: KnowledgeRepository,
        *,
        max_distance: float | None = None,
        translator: TranslationClient | None = None,
    ) -> None:
        if max_distance is not None and max_distance <= 0:
            raise KnowledgeRetrievalError("max_distance deve ser maior que zero.")
        self._embedding_client = embedding_client
        self._repository = repository
        self._max_distance = max_distance
        self._translator = translator

    def search(self, query: str, *, limit: int) -> tuple[KnowledgeSearchResult, ...]:
        normalized_query = query.strip()
        if not normalized_query:
            raise KnowledgeRetrievalError("A consulta semântica não pode ser vazia.")
        if limit <= 0:
            raise KnowledgeRetrievalError("limit deve ser maior que zero.")
        try:
            retrieval_query = self._retrieval_query(normalized_query)
            embeddings = self._embedding_client.embed([retrieval_query])
            if len(embeddings) != 1:
                raise KnowledgeRetrievalError(
                    "O provedor não retornou exatamente um embedding para a consulta."
                )
            results = self._repository.query(embeddings[0], limit=limit)
            if self._max_distance is not None:
                results = tuple(
                    result for result in results if result.distance <= self._max_distance
                )
            return tuple(self._localize(result) for result in results)
        except TranslationError as error:
            raise KnowledgeRetrievalError(str(error)) from error

    def _retrieval_query(self, query: str) -> str:
        if self._translator is None or looks_english(query) or not looks_portuguese(query):
            return query
        translated = self._translator.translate(query, source="pt", target="en").strip()
        return translated or query

    def _localize(self, result: KnowledgeSearchResult) -> KnowledgeSearchResult:
        if self._translator is None:
            return result
        return localize_search_result(result, self._translator)
