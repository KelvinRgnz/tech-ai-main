"""Histórico de conversa no PostgreSQL com escopo por proprietário."""

from typing import Any, cast
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from tech_ai.config.database import DatabaseSettings
from tech_ai.integrations.postgres import database_connection
from tech_ai.models.conversation import ConversationMessage, MessageRole


class PostgresConversationRepository:
    def __init__(self, settings: DatabaseSettings) -> None:
        self._settings = settings

    def append(self, owner: str, patient_id: UUID, message: ConversationMessage) -> bool:
        with database_connection(self._settings) as connection:
            result = connection.execute(
                """
                INSERT INTO tech_ai.messages
                    (id, conversation_id, role, content, payload, created_at)
                SELECT %s, c.id, %s, %s, %s, %s
                FROM tech_ai.conversations c
                JOIN tech_ai.patients p ON p.id = c.patient_id
                WHERE p.id = %s AND p.owner_username = %s
                RETURNING conversation_id
                """,
                (
                    message.id,
                    message.role,
                    message.content,
                    Jsonb(message.payload) if message.payload is not None else None,
                    message.created_at,
                    patient_id,
                    owner,
                ),
            )
            row = result.fetchone()
            return row is not None

    def list_messages(
        self, owner: str, patient_id: UUID, *, limit: int
    ) -> tuple[ConversationMessage, ...] | None:
        with database_connection(self._settings, read_only=True) as connection:
            ownership = connection.execute(
                "SELECT c.id FROM tech_ai.conversations c "
                "JOIN tech_ai.patients p ON p.id = c.patient_id "
                "WHERE p.id = %s AND p.owner_username = %s",
                (patient_id, owner),
            ).fetchone()
            if ownership is None:
                return None
            conversation_id = cast(UUID, ownership[0])
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    "SELECT id, conversation_id, role, content, payload, created_at "
                    "FROM tech_ai.messages WHERE conversation_id = %s "
                    "ORDER BY created_at ASC, id ASC LIMIT %s",
                    (conversation_id, limit),
                )
                return tuple(self._to_message(row) for row in cursor.fetchall())

    @staticmethod
    def _to_message(row: dict[str, Any]) -> ConversationMessage:
        role = cast(MessageRole, row["role"])
        payload = cast(dict[str, Any] | None, row["payload"])
        return ConversationMessage(
            id=cast(UUID, row["id"]),
            conversation_id=cast(UUID, row["conversation_id"]),
            role=role,
            content=cast(str, row["content"]),
            payload=payload,
            created_at=row["created_at"],
        )
