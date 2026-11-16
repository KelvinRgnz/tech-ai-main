"""Mensagens persistidas na conversa de um paciente fictício."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

MessageRole = Literal["user", "assistant"]


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    payload: dict[str, Any] | None
    created_at: datetime
