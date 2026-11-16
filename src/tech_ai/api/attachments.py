"""Upload autenticado e processamento multimodal de anexos da conversa."""

from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse

from tech_ai.errors import (
    AttachmentNotFoundError,
    AttachmentStorageError,
    AttachmentValidationError,
    ConfigurationError,
    DatabaseConnectionError,
    PatientNotFoundError,
)
from tech_ai.models.attachment import AttachmentView
from tech_ai.models.auth import AuthUser
from tech_ai.services.attachment_service import AttachmentService


def attachment_router(
    current_user: Callable[[Request], AuthUser],
    service_factory: Callable[[], AttachmentService],
) -> APIRouter:
    router = APIRouter(prefix="/api/patients", tags=["attachments"])

    def map_error(error: Exception) -> HTTPException:
        if isinstance(error, (PatientNotFoundError, AttachmentNotFoundError)):
            return HTTPException(404, str(error))
        if isinstance(error, AttachmentValidationError):
            return HTTPException(422, str(error))
        if isinstance(error, (ConfigurationError, DatabaseConnectionError, AttachmentStorageError)):
            return HTTPException(503, "Serviço de anexos indisponível.")
        return HTTPException(500, "Falha inesperada no serviço de anexos.")

    @router.post("/{patient_id}/attachments", status_code=201)
    async def upload(
        patient_id: UUID,
        request: Request,
        filename: str = Query(min_length=1, max_length=255),
        user: AuthUser = Depends(current_user),
    ) -> AttachmentView:
        try:
            return await service_factory().upload(
                user.username,
                patient_id,
                original_name=filename,
                declared_content_type=request.headers.get("content-type", ""),
                chunks=request.stream(),
            )
        except Exception as error:
            raise map_error(error) from None

    @router.get("/{patient_id}/attachments")
    def list_attachments(
        patient_id: UUID, user: AuthUser = Depends(current_user)
    ) -> tuple[AttachmentView, ...]:
        try:
            return service_factory().list_for_patient(user.username, patient_id)
        except Exception as error:
            raise map_error(error) from None

    @router.post("/{patient_id}/attachments/{attachment_id}/process")
    def process(
        patient_id: UUID,
        attachment_id: UUID,
        user: AuthUser = Depends(current_user),
    ) -> AttachmentView:
        try:
            return service_factory().process(user.username, patient_id, attachment_id)
        except Exception as error:
            raise map_error(error) from None

    @router.get("/{patient_id}/attachments/{attachment_id}/content")
    def content(
        patient_id: UUID,
        attachment_id: UUID,
        user: AuthUser = Depends(current_user),
    ) -> FileResponse:
        try:
            path, content_type, original_name = service_factory().content(
                user.username, patient_id, attachment_id
            )
            return FileResponse(
                Path(path),
                media_type=content_type,
                filename=original_name,
                content_disposition_type="inline",
            )
        except Exception as error:
            raise map_error(error) from None

    return router
