"""Endpoints autenticados para pacientes fictícios e conversa única."""

from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from tech_ai.errors import (
    ConfigurationError,
    DatabaseConnectionError,
    PatientNotFoundError,
    PatientValidationError,
)
from tech_ai.models.auth import AuthUser
from tech_ai.models.patient import PatientConversation
from tech_ai.services.patient_service import PatientService


class CreatePatientRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    display_name: str = Field(min_length=1, max_length=120)


def patient_router(
    current_user: Callable[[Request], AuthUser],
    service_factory: Callable[[], PatientService],
) -> APIRouter:
    router = APIRouter(prefix="/api/patients", tags=["patients"])

    def execute[T](operation: Callable[[PatientService], T]) -> T:
        try:
            return operation(service_factory())
        except PatientNotFoundError:
            raise HTTPException(404, "Paciente não encontrado.") from None
        except PatientValidationError as error:
            raise HTTPException(422, str(error)) from None
        except (ConfigurationError, DatabaseConnectionError):
            raise HTTPException(
                503, "Persistência indisponível. Verifique configuração e migrações."
            ) from None

    @router.post("", status_code=201)
    def create(
        body: CreatePatientRequest, user: AuthUser = Depends(current_user)
    ) -> PatientConversation:
        return execute(lambda service: service.create(user.username, body.display_name))

    @router.get("")
    def list_patients(
        user: AuthUser = Depends(current_user),
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> tuple[PatientConversation, ...]:
        return execute(
            lambda service: service.list_for_owner(user.username, limit=limit, offset=offset)
        )

    @router.get("/{patient_id}/conversation")
    def get_conversation(
        patient_id: UUID, user: AuthUser = Depends(current_user)
    ) -> PatientConversation:
        return execute(lambda service: service.get(user.username, patient_id))

    return router
