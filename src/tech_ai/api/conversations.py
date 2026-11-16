"""Leitura autenticada do histórico persistido de uma conversa."""

from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from tech_ai.errors import (
    ConfigurationError,
    DatabaseConnectionError,
    PatientNotFoundError,
    PatientValidationError,
)
from tech_ai.models.auth import AuthUser
from tech_ai.models.conversation import ConversationMessage
from tech_ai.services.conversation_service import ConversationService


def conversation_router(
    current_user: Callable[[Request], AuthUser],
    service_factory: Callable[[], ConversationService],
) -> APIRouter:
    router = APIRouter(prefix="/api/patients", tags=["conversations"])

    @router.get("/{patient_id}/messages")
    def list_messages(
        patient_id: UUID,
        user: AuthUser = Depends(current_user),
        limit: int = Query(default=200, ge=1, le=500),
    ) -> tuple[ConversationMessage, ...]:
        try:
            return service_factory().list_messages(user.username, patient_id, limit=limit)
        except PatientNotFoundError:
            raise HTTPException(404, "Paciente não encontrado.") from None
        except PatientValidationError as error:
            raise HTTPException(422, str(error)) from None
        except (ConfigurationError, DatabaseConnectionError):
            raise HTTPException(503, "Histórico indisponível.") from None

    @router.delete("/{patient_id}/messages")
    def clear_messages(
        patient_id: UUID,
        user: AuthUser = Depends(current_user),
    ) -> dict[str, int]:
        try:
            deleted = service_factory().clear_messages(user.username, patient_id)
        except PatientNotFoundError:
            raise HTTPException(404, "Paciente não encontrado.") from None
        except (ConfigurationError, DatabaseConnectionError):
            raise HTTPException(503, "Histórico indisponível.") from None
        return {"deleted": deleted}

    return router
