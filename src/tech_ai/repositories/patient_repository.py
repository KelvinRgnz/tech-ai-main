"""Contrato de persistência com escopo obrigatório de usuário."""

from typing import Protocol
from uuid import UUID

from tech_ai.models.patient import PatientConversation


class PatientRepository(Protocol):
    def create(self, owner: str, patient: PatientConversation) -> None: ...

    def list_for_owner(
        self, owner: str, *, limit: int, offset: int
    ) -> tuple[PatientConversation, ...]: ...

    def get(self, owner: str, patient_id: UUID) -> PatientConversation | None: ...
