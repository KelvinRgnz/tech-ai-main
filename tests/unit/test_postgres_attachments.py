from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import psycopg
import pytest

from tech_ai.config.database import DatabaseSettings
from tech_ai.integrations.postgres_attachments import PostgresAttachmentRepository
from tech_ai.models.attachment import AttachmentAnalysis, StoredAttachment

URL = "postgresql://test:secret@localhost/test"


def setup_connection(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock]:
    connect = MagicMock()
    monkeypatch.setattr(psycopg, "connect", connect)
    return connect, connect.return_value.__enter__.return_value


def attachment() -> StoredAttachment:
    now = datetime.now(UTC)
    return StoredAttachment(
        uuid4(),
        uuid4(),
        "laudo.png",
        "ab/file.png",
        "a" * 64,
        "image",
        "image/png",
        123,
        now,
        AttachmentAnalysis(
            uuid4(),
            "pending",
            "simulator",
            "1",
            0,
            None,
            (),
            (),
            None,
            now,
            None,
            None,
        ),
    )


def test_create_is_scoped_parameterized_and_transactional(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connect, connection = setup_connection(monkeypatch)
    connection.execute.return_value.fetchone.return_value = (uuid4(),)
    item = attachment()
    patient_id = uuid4()
    assert PostgresAttachmentRepository(DatabaseSettings(URL)).create(
        "alice", patient_id, item
    )
    calls = connection.execute.call_args_list
    assert len(calls) == 2
    assert "owner_username = %s" in calls[0].args[0]
    assert calls[0].args[1][-2:] == (patient_id, "alice")
    assert item.storage_key not in calls[0].args[0]
    assert calls[1].args[1][1] == item.id
    connect.return_value.__exit__.assert_called_once_with(None, None, None)


def test_create_does_not_insert_analysis_for_foreign_patient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, connection = setup_connection(monkeypatch)
    connection.execute.return_value.fetchone.return_value = None
    assert not PostgresAttachmentRepository(DatabaseSettings(URL)).create(
        "bob", uuid4(), attachment()
    )
    assert connection.execute.call_count == 1


def test_list_get_and_complete_keep_owner_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    connect, connection = setup_connection(monkeypatch)
    cursor = connection.cursor.return_value.__enter__.return_value
    patient_id = uuid4()
    item = attachment()
    cursor.fetchall.return_value = []
    connection.execute.return_value.fetchone.return_value = (1,)
    repository = PostgresAttachmentRepository(DatabaseSettings(URL))
    assert repository.list_for_patient("alice", patient_id) == ()
    assert "owner_username = %s" in cursor.execute.call_args.args[0]
    assert "read_only=on" in connect.call_args.kwargs["options"]

    cursor.fetchone.return_value = None
    assert repository.get("alice", patient_id, item.id) is None
    assert cursor.execute.call_args.args[1] == (patient_id, "alice", item.id)

    connection.execute.return_value.fetchone.return_value = (item.analysis.id,)
    assert repository.complete_analysis(
        "alice", patient_id, item.id, item.analysis
    )
    sql, parameters = connection.execute.call_args.args
    assert "owner_username = %s" in sql
    assert parameters[-3:] == (item.id, patient_id, "alice")
