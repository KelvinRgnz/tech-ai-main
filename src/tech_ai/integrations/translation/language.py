"""Heurísticas leves para decidir se um texto já está em inglês ou português."""

from __future__ import annotations

import re

_PORTUGUESE_CHARS = re.compile(r"[áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ]")
_WORD_PATTERN = re.compile(r"[^\W\d_]+", flags=re.UNICODE)
_ENGLISH_MARKERS = frozenset(
    {
        "the",
        "and",
        "is",
        "are",
        "was",
        "were",
        "this",
        "that",
        "with",
        "from",
        "have",
        "what",
        "how",
        "when",
        "which",
        "symptoms",
        "disease",
        "stress",
        "diabetes",
        "causes",
        "managed",
    }
)
_PORTUGUESE_MARKERS = frozenset(
    {
        "que",
        "não",
        "nao",
        "uma",
        "para",
        "com",
        "quais",
        "sintomas",
        "doença",
        "doenca",
        "estresse",
        "causa",
        "causas",
        "sobre",
        "como",
        "quando",
    }
)


def _marker_counts(text: str) -> tuple[int, int, int]:
    words = [match.group(0).casefold() for match in _WORD_PATTERN.finditer(text)]
    english = sum(1 for word in words if word in _ENGLISH_MARKERS)
    portuguese = sum(1 for word in words if word in _PORTUGUESE_MARKERS)
    return len(words), english, portuguese


def looks_english(text: str) -> bool:
    word_count, english, portuguese = _marker_counts(text)
    if word_count < 3:
        return False
    return english >= 2 and english > portuguese


def looks_portuguese(text: str) -> bool:
    if _PORTUGUESE_CHARS.search(text):
        return True
    word_count, english, portuguese = _marker_counts(text)
    if word_count < 3:
        return False
    return portuguese >= 2 and portuguese >= english
