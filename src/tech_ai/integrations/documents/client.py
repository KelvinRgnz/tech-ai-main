"""Contrato independente de provedor para OCR documental."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class OcrPage:
    number: int
    text: str


@dataclass(frozen=True, slots=True)
class OcrResult:
    text: str
    pages: tuple[OcrPage, ...]


class DocumentReader(Protocol):
    def read(self, path: Path, *, content_type: str) -> OcrResult: ...
