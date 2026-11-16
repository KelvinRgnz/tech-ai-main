"""Criação e consulta de pacientes fictícios do usuário autenticado."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from tech_ai.errors import PatientNotFoundError, PatientValidationError
from tech_ai.models.patient import PatientConversation
from tech_ai.repositories.patient_repository import PatientRepository


class PatientService:
    def __init__(self, repository: PatientRepository) -> None:
        self._repository = repository

    def create(self, owner: str, display_name: str) -> PatientConversation:
        name = display_name.strip()
        if not 1 <= len(name) <= 120:
            raise PatientValidationError("Informe um nome fictício de até 120 caracteres.")
        patient = PatientConversation(uuid4(), uuid4(), name, datetime.now(UTC))
        self._repository.create(owner, patient)
        return patient

    def list_for_owner(
        self, owner: str, *, limit: int = 50, offset: int = 0
    ) -> tuple[PatientConversation, ...]:
        if not 1 <= limit <= 100 or offset < 0:
            raise PatientValidationError("Paginação inválida.")
        return self._repository.list_for_owner(owner, limit=limit, offset=offset)

    def get(self, owner: str, patient_id: UUID) -> PatientConversation:
        patient = self._repository.get(owner, patient_id)
        if patient is None:
            raise PatientNotFoundError("Paciente não encontrado.")
        return patient
