"""Metadados persistidos de anexos e de suas análises."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

AttachmentModality = Literal["document", "image", "audio", "video"]
AnalysisStatus = Literal["pending", "processing", "completed", "failed"]


@dataclass(frozen=True, slots=True)
class AttachmentAnalysis:
    id: UUID
    status: AnalysisStatus
    processor_name: str
    processor_version: str
    attempt: int
    summary: str | None
    observations: tuple[str, ...]
    limitations: tuple[str, ...]
    error_code: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class StoredAttachment:
    id: UUID
    conversation_id: UUID
    original_name: str
    storage_key: str
    sha256: str
    modality: AttachmentModality
    content_type: str
    size_bytes: int
    created_at: datetime
    analysis: AttachmentAnalysis


@dataclass(frozen=True, slots=True)
class AttachmentView:
    id: UUID
    original_name: str
    modality: AttachmentModality
    content_type: str
    size_bytes: int
    created_at: datetime
    analysis: AttachmentAnalysis

    @classmethod
    def from_stored(cls, attachment: StoredAttachment) -> AttachmentView:
        return cls(
            attachment.id,
            attachment.original_name,
            attachment.modality,
            attachment.content_type,
            attachment.size_bytes,
            attachment.created_at,
            attachment.analysis,
        )
