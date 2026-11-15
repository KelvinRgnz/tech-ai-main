"""Contrato independente de provedor para análise textual."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SentimentConfidence:
    positive: float
    neutral: float
    negative: float


@dataclass(frozen=True, slots=True)
class TextAnalysis:
    sentiment: str
    confidence: SentimentConfidence
    key_phrases: tuple[str, ...]


class TextAnalyzer(Protocol):
    def analyze(self, text: str, *, language: str = "pt-BR") -> TextAnalysis: ...
