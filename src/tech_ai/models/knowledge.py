"""Modelos internos da recuperação semântica."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MetadataValue = str | int | float | bool


def _string_metadata(metadata: dict[str, MetadataValue], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) and value else None


@dataclass(frozen=True, slots=True)
class KnowledgeSearchResult:
    """Documento recuperado do ChromaDB sem expor objetos do SDK."""

    record_id: str
    text: str
    metadata: dict[str, MetadataValue]
    distance: float

    @property
    def document_id(self) -> str | None:
        return _string_metadata(self.metadata, "document_id")

    @property
    def parent_record_id(self) -> str | None:
        return _string_metadata(self.metadata, "parent_record_id") or self.document_id

    @property
    def chunk_id(self) -> str:
        return _string_metadata(self.metadata, "chunk_id") or self.record_id

    @property
    def focus(self) -> str | None:
        return _string_metadata(self.metadata, "focus")

    @property
    def source_url(self) -> str | None:
        return _string_metadata(self.metadata, "source_url")

    def as_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.parent_record_id or self.record_id,
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "text": self.text,
            "metadata": self.metadata,
            "distance": self.distance,
            "focus": self.focus,
            "source_url": self.source_url,
        }


@dataclass(frozen=True, slots=True)
class KnowledgeCitation:
    """Referência pequena retornada ao consumidor junto da resposta."""

    number: int
    record_id: str
    distance: float
    focus: str | None
    source_url: str | None
    document_id: str | None = None
    chunk_id: str | None = None

    @classmethod
    def from_result(
        cls,
        result: KnowledgeSearchResult,
        *,
        number: int,
    ) -> KnowledgeCitation:
        parent_id = result.parent_record_id
        return cls(
            number=number,
            record_id=parent_id or result.record_id,
            distance=result.distance,
            focus=result.focus,
            source_url=result.source_url,
            document_id=result.document_id,
            chunk_id=result.chunk_id,
        )

    def as_dict(self) -> dict[str, str | float | None]:
        return {
            "citation": f"[{self.number}]",
            "record_id": self.record_id,
            "document_id": self.document_id,
            "chunk_id": self.chunk_id,
            "distance": self.distance,
            "focus": self.focus,
            "source_url": self.source_url,
        }
