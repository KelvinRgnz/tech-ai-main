"""Análise de sentimento e frases-chave com Azure AI Language."""

from __future__ import annotations

import importlib
from threading import BoundedSemaphore
from typing import Any, cast

from tech_ai.errors import ConfigurationError, LanguageAnalysisError
from tech_ai.integrations.language.client import (
    SentimentConfidence,
    TextAnalysis,
)


def _azure_types() -> tuple[Any, Any]:
    try:
        textanalytics = importlib.import_module("azure.ai.textanalytics")
        credentials = importlib.import_module("azure.core.credentials")
    except ImportError as error:
        raise ConfigurationError(
            "O cliente Azure Language não está instalado. Execute: uv sync --extra azure"
        ) from error
    return textanalytics.TextAnalyticsClient, credentials.AzureKeyCredential


class AzureLanguageAnalyzer:
    def __init__(
        self,
        *,
        key: str,
        endpoint: str,
        max_concurrent_requests: int = 1,
        max_characters: int = 5_000,
    ) -> None:
        if not key.strip() or not endpoint.startswith("https://"):
            raise ConfigurationError("Credenciais do Azure Language inválidas.")
        if max_concurrent_requests <= 0 or max_characters <= 0:
            raise ConfigurationError("Limites do Azure Language devem ser positivos.")
        self._key = key
        self._endpoint = endpoint.rstrip("/")
        self._max_characters = max_characters
        self._semaphore = BoundedSemaphore(max_concurrent_requests)

    def analyze(self, text: str, *, language: str = "pt-BR") -> TextAnalysis:
        normalized = " ".join(text.split())
        if not normalized:
            raise LanguageAnalysisError("A transcrição está vazia para análise textual.")
        if len(normalized) > self._max_characters:
            raise LanguageAnalysisError("A transcrição excede o limite textual da POC.")
        with self._semaphore:
            return self._analyze(normalized, language=language)

    def _analyze(self, text: str, *, language: str) -> TextAnalysis:
        client_type, credential_type = _azure_types()
        try:
            client = client_type(
                endpoint=self._endpoint,
                credential=credential_type(self._key),
            )
            sentiment_result = client.analyze_sentiment(
                [text], language=language, show_opinion_mining=False
            )[0]
            phrases_result = client.extract_key_phrases([text], language=language)[0]
            if sentiment_result.is_error or phrases_result.is_error:
                raise LanguageAnalysisError(
                    "O Azure Language não conseguiu analisar a transcrição."
                )
            scores = sentiment_result.confidence_scores
            return TextAnalysis(
                sentiment=cast(str, sentiment_result.sentiment),
                confidence=SentimentConfidence(
                    positive=float(scores.positive),
                    neutral=float(scores.neutral),
                    negative=float(scores.negative),
                ),
                key_phrases=tuple(
                    phrase.strip()
                    for phrase in phrases_result.key_phrases
                    if phrase.strip()
                ),
            )
        except (ConfigurationError, LanguageAnalysisError):
            raise
        except Exception as error:
            raise LanguageAnalysisError(
                "O Azure Language não concluiu a análise textual."
            ) from error
