"""Contrato mínimo de tradução usado na recuperação e na apresentação."""

from __future__ import annotations

from typing import Protocol


class TranslationClient(Protocol):
    """Traduz texto sem expor HTTP, Argos ou outro SDK ao serviço."""

    def translate(self, text: str, *, source: str, target: str) -> str: ...
