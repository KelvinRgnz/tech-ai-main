"""Persistência PostgreSQL dos anexos no escopo do paciente autenticado."""

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from tech_ai.config.database import DatabaseSettings
from tech_ai.integrations.postgres import database_connection
from tech_ai.models.attachment import (
    AnalysisStatus,
    AttachmentAnalysis,
    AttachmentModality,
    StoredAttachment,
)

_SELECT = """
SELECT
    a.id, a.conversation_id, a.original_name, a.storage_key, a.sha256,
    a.modality, a.content_type, a.size_bytes, a.created_at,
    n.id AS analysis_id, n.status, n.processor_name, n.processor_version,
    n.attempt, n.summary, n.observations, n.limitations, n.error_code,
    n.created_at AS analysis_created_at, n.started_at, n.finished_at
FROM tech_ai.attachments a
JOIN tech_ai.analyses n ON n.attachment_id = a.id
JOIN tech_ai.conversations c ON c.id = a.conversation_id
JOIN tech_ai.patients p ON p.id = c.patient_id
"""


class PostgresAttachmentRepository:
    def __init__(self, settings: DatabaseSettings) -> None:
        self._settings = settings

    def create(self, owner: str, patient_id: UUID, attachment: StoredAttachment) -> bool:
        with database_connection(self._settings) as connection:
            result = connection.execute(
                """
                INSERT INTO tech_ai.attachments
                    (id, conversation_id, original_name, storage_key, sha256,
                     modality, content_type, size_bytes, created_at)
                SELECT %s, c.id, %s, %s, %s, %s, %s, %s, %s
                FROM tech_ai.conversations c
                JOIN tech_ai.patients p ON p.id = c.patient_id
                WHERE p.id = %s AND p.owner_username = %s
                RETURNING conversation_id
                """,
                (
                    attachment.id,
                    attachment.original_name,
                    attachment.storage_key,
                    attachment.sha256,
                    attachment.modality,
                    attachment.content_type,
                    attachment.size_bytes,
                    attachment.created_at,
                    patient_id,
                    owner,
                ),
            )
            row = result.fetchone()
            if row is None:
                return False
            connection.execute(
                """
                INSERT INTO tech_ai.analyses
                    (id, attachment_id, status, processor_name, processor_version,
                     attempt, summary, observations, limitations, error_code,
                     created_at, started_at, finished_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    attachment.analysis.id,
                    attachment.id,
                    attachment.analysis.status,
                    attachment.analysis.processor_name,
                    attachment.analysis.processor_version,
                    attachment.analysis.attempt,
                    attachment.analysis.summary,
                    Jsonb(attachment.analysis.observations),
                    Jsonb(attachment.analysis.limitations),
                    attachment.analysis.error_code,
                    attachment.analysis.created_at,
                    attachment.analysis.started_at,
                    attachment.analysis.finished_at,
                ),
            )
            return True

    def list_for_patient(
        self, owner: str, patient_id: UUID
    ) -> tuple[StoredAttachment, ...] | None:
        with database_connection(self._settings, read_only=True) as connection:
            ownership = connection.execute(
                "SELECT 1 FROM tech_ai.patients WHERE id = %s AND owner_username = %s",
                (patient_id, owner),
            ).fetchone()
            if ownership is None:
                return None
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    _SELECT
                    + " WHERE p.id = %s AND p.owner_username = %s"
                    + " ORDER BY a.created_at ASC, a.id ASC",
                    (patient_id, owner),
                )
                return tuple(self._to_attachment(row) for row in cursor.fetchall())

    def get(
        self, owner: str, patient_id: UUID, attachment_id: UUID
    ) -> StoredAttachment | None:
        with (
            database_connection(self._settings, read_only=True) as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            cursor.execute(
                _SELECT + " WHERE p.id = %s AND p.owner_username = %s AND a.id = %s",
                (patient_id, owner, attachment_id),
            )
            row = cursor.fetchone()
            return self._to_attachment(row) if row is not None else None

    def complete_analysis(
        self,
        owner: str,
        patient_id: UUID,
        attachment_id: UUID,
        analysis: AttachmentAnalysis,
    ) -> bool:
        with database_connection(self._settings) as connection:
            result = connection.execute(
                """
                UPDATE tech_ai.analyses n
                SET status = %s, processor_name = %s, processor_version = %s,
                    attempt = %s, summary = %s, observations = %s, limitations = %s,
                    error_code = %s, started_at = %s, finished_at = %s
                FROM tech_ai.attachments a
                JOIN tech_ai.conversations c ON c.id = a.conversation_id
                JOIN tech_ai.patients p ON p.id = c.patient_id
                WHERE n.attachment_id = a.id AND a.id = %s
                  AND p.id = %s AND p.owner_username = %s
                RETURNING n.id
                """,
                (
                    analysis.status,
                    analysis.processor_name,
                    analysis.processor_version,
                    analysis.attempt,
                    analysis.summary,
                    Jsonb(analysis.observations),
                    Jsonb(analysis.limitations),
                    analysis.error_code,
                    analysis.started_at,
                    analysis.finished_at,
                    attachment_id,
                    patient_id,
                    owner,
                ),
            )
            return result.fetchone() is not None

    @staticmethod
    def _to_attachment(row: dict[str, Any]) -> StoredAttachment:
        analysis = AttachmentAnalysis(
            id=cast(UUID, row["analysis_id"]),
            status=cast(AnalysisStatus, row["status"]),
            processor_name=cast(str, row["processor_name"]),
            processor_version=cast(str, row["processor_version"]),
            attempt=cast(int, row["attempt"]),
            summary=cast(str | None, row["summary"]),
            observations=tuple(cast(list[str], row["observations"])),
            limitations=tuple(cast(list[str], row["limitations"])),
            error_code=cast(str | None, row["error_code"]),
            created_at=cast(datetime, row["analysis_created_at"]),
            started_at=cast(datetime | None, row["started_at"]),
            finished_at=cast(datetime | None, row["finished_at"]),
        )
        return StoredAttachment(
            id=cast(UUID, row["id"]),
            conversation_id=cast(UUID, row["conversation_id"]),
            original_name=cast(str, row["original_name"]),
            storage_key=cast(str, row["storage_key"]),
            sha256=cast(str, row["sha256"]),
            modality=cast(AttachmentModality, row["modality"]),
            content_type=cast(str, row["content_type"]),
            size_bytes=cast(int, row["size_bytes"]),
            created_at=cast(datetime, row["created_at"]),
            analysis=analysis,
        )
