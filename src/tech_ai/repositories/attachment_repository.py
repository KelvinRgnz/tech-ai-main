"""Contratos de persistência e armazenamento dos anexos."""

from collections.abc import AsyncIterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from tech_ai.models.attachment import AttachmentAnalysis, StoredAttachment


@dataclass(frozen=True, slots=True)
class TemporaryAttachment:
    path: Path
    size_bytes: int
    sha256: str
    header: bytes


class AttachmentRepository(Protocol):
    def create(self, owner: str, patient_id: UUID, attachment: StoredAttachment) -> bool: ...

    def list_for_patient(
        self, owner: str, patient_id: UUID
    ) -> tuple[StoredAttachment, ...] | None: ...

    def get(
        self, owner: str, patient_id: UUID, attachment_id: UUID
    ) -> StoredAttachment | None: ...

    def complete_analysis(
        self,
        owner: str,
        patient_id: UUID,
        attachment_id: UUID,
        analysis: AttachmentAnalysis,
    ) -> bool: ...


class AttachmentStorage(Protocol):
    async def write_temporary(
        self, chunks: AsyncIterable[bytes], *, max_bytes: int
    ) -> TemporaryAttachment: ...

    def promote(self, temporary: TemporaryAttachment, *, storage_key: str) -> None: ...

    def remove(self, storage_key: str) -> None: ...

    def resolve(self, storage_key: str) -> Path: ...
