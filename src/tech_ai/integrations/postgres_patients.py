"""Persistência transacional de pacientes no PostgreSQL."""

from uuid import UUID

from psycopg.rows import class_row

from tech_ai.config.database import DatabaseSettings
from tech_ai.integrations.postgres import database_connection
from tech_ai.models.patient import PatientConversation

_SELECT = """
SELECT p.id, c.id AS conversation_id, p.display_name, p.created_at, p.fictional
FROM tech_ai.patients p JOIN tech_ai.conversations c ON c.patient_id = p.id
WHERE p.owner_username = %s
"""


class PostgresPatientRepository:
    def __init__(self, settings: DatabaseSettings) -> None:
        self._settings = settings

    def create(self, owner: str, patient: PatientConversation) -> None:
        with database_connection(self._settings) as connection:
            connection.execute(
                "INSERT INTO tech_ai.patients "
                "(id, owner_username, display_name, fictional, created_at) "
                "VALUES (%s, %s, %s, %s, %s)",
                (patient.id, owner, patient.display_name, True, patient.created_at),
            )
            connection.execute(
                "INSERT INTO tech_ai.conversations (id, patient_id, created_at) "
                "VALUES (%s, %s, %s)",
                (patient.conversation_id, patient.id, patient.created_at),
            )

    def list_for_owner(
        self, owner: str, *, limit: int, offset: int
    ) -> tuple[PatientConversation, ...]:
        with (
            database_connection(self._settings, read_only=True) as connection,
            connection.cursor(row_factory=class_row(PatientConversation)) as cursor,
        ):
            cursor.execute(
                _SELECT + " ORDER BY p.created_at DESC, p.id LIMIT %s OFFSET %s",
                (owner, limit, offset),
            )
            return tuple(cursor.fetchall())

    def get(self, owner: str, patient_id: UUID) -> PatientConversation | None:
        with (
            database_connection(self._settings, read_only=True) as connection,
            connection.cursor(row_factory=class_row(PatientConversation)) as cursor,
        ):
            cursor.execute(_SELECT + " AND p.id = %s", (owner, patient_id))
            return cursor.fetchone()
