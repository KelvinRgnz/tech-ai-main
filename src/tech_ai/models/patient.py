"""Paciente fictício e sua conversa única."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PatientConversation:
    id: UUID
    conversation_id: UUID
    display_name: str
    created_at: datetime
    fictional: bool = True
