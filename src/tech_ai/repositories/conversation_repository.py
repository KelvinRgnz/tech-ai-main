"""Contrato de mensagens sempre vinculado ao proprietário do paciente."""

from typing import Protocol
from uuid import UUID

from tech_ai.models.conversation import ConversationMessage


class ConversationRepository(Protocol):
    def append(self, owner: str, patient_id: UUID, message: ConversationMessage) -> bool: ...

    def list_messages(
        self, owner: str, patient_id: UUID, *, limit: int
    ) -> tuple[ConversationMessage, ...] | None: ...
