"""Histórico persistente das perguntas e respostas por paciente."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from tech_ai.errors import PatientNotFoundError, PatientValidationError
from tech_ai.models.conversation import ConversationMessage, MessageRole
from tech_ai.repositories.conversation_repository import ConversationRepository


class ConversationService:
    def __init__(self, repository: ConversationRepository) -> None:
        self._repository = repository

    def append(
        self,
        owner: str,
        patient_id: UUID,
        *,
        role: MessageRole,
        content: str,
        payload: dict[str, Any] | None = None,
    ) -> ConversationMessage:
        normalized = content.strip()
        if not normalized or len(normalized) > 20_000:
            raise PatientValidationError("Mensagem vazia ou maior que 20.000 caracteres.")
        message = ConversationMessage(
            id=uuid4(),
            conversation_id=UUID(int=0),
            role=role,
            content=normalized,
            payload=payload,
            created_at=datetime.now(UTC),
        )
        if not self._repository.append(owner, patient_id, message):
            raise PatientNotFoundError("Paciente não encontrado.")
        return message

    def list_messages(
        self, owner: str, patient_id: UUID, *, limit: int = 200
    ) -> tuple[ConversationMessage, ...]:
        if not 1 <= limit <= 500:
            raise PatientValidationError("Limite de mensagens inválido.")
        messages = self._repository.list_messages(owner, patient_id, limit=limit)
        if messages is None:
            raise PatientNotFoundError("Paciente não encontrado.")
        return messages
