from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import psycopg
import pytest

from tech_ai.config.database import DatabaseSettings
from tech_ai.integrations.postgres_conversations import PostgresConversationRepository
from tech_ai.models.conversation import ConversationMessage

URL = "postgresql://test:secret@localhost/test"


def connection(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock]:
    connect = MagicMock()
    monkeypatch.setattr(psycopg, "connect", connect)
    return connect, connect.return_value.__enter__.return_value


def test_append_uses_owner_patient_and_parameters(monkeypatch: pytest.MonkeyPatch) -> None:
    connect, database = connection(monkeypatch)
    database.execute.return_value.fetchone.return_value = (uuid4(),)
    patient_id = uuid4()
    message = ConversationMessage(uuid4(), UUID_ZERO, "user", "Question", None, datetime.now(UTC))
    repository = PostgresConversationRepository(DatabaseSettings(URL))
    assert repository.append("alice", patient_id, message) is True
    sql, parameters = database.execute.call_args.args
    assert "p.owner_username = %s" in sql
    assert parameters[-2:] == (patient_id, "alice")
    assert message.content not in sql
    assert "read_only=on" not in connect.call_args.kwargs["options"]


def test_append_returns_false_when_owner_does_not_match(monkeypatch: pytest.MonkeyPatch) -> None:
    _, database = connection(monkeypatch)
    database.execute.return_value.fetchone.return_value = None
    repository = PostgresConversationRepository(DatabaseSettings(URL))
    message = ConversationMessage(uuid4(), UUID_ZERO, "user", "Question", None, datetime.now(UTC))
    assert repository.append("bob", uuid4(), message) is False


def test_list_checks_ownership_before_reading_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    connect, database = connection(monkeypatch)
    patient_id = uuid4()
    conversation_id = uuid4()
    database.execute.return_value.fetchone.return_value = (conversation_id,)
    cursor = database.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [
        {
            "id": uuid4(),
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": "Answer",
            "payload": {"mode": "evidence"},
            "created_at": datetime.now(UTC),
        }
    ]
    repository = PostgresConversationRepository(DatabaseSettings(URL))
    messages = repository.list_messages("alice", patient_id, limit=20)
    assert messages is not None and messages[0].payload == {"mode": "evidence"}
    ownership_sql, ownership_parameters = database.execute.call_args.args
    assert "p.owner_username = %s" in ownership_sql
    assert ownership_parameters == (patient_id, "alice")
    assert cursor.execute.call_args.args[1] == (conversation_id, 20)
    assert "read_only=on" in connect.call_args.kwargs["options"]


def test_list_returns_none_without_ownership(monkeypatch: pytest.MonkeyPatch) -> None:
    _, database = connection(monkeypatch)
    database.execute.return_value.fetchone.return_value = None
    repository = PostgresConversationRepository(DatabaseSettings(URL))
    assert repository.list_messages("bob", uuid4(), limit=20) is None
    database.cursor.assert_not_called()


UUID_ZERO = uuid4()
