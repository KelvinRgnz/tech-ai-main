from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import psycopg
import pytest

from tech_ai.config.database import DatabaseSettings
from tech_ai.errors import DatabaseConnectionError
from tech_ai.integrations.postgres_patients import PostgresPatientRepository
from tech_ai.integrations.postgres_schema import migrate_database
from tech_ai.models.patient import PatientConversation
from tech_ai.runner import main

URL = "postgresql://test:secret@localhost/test"


def setup_connection(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock]:
    connect = MagicMock()
    monkeypatch.setattr(psycopg, "connect", connect)
    return connect, connect.return_value.__enter__.return_value


def test_create_is_one_transaction_with_parameters(monkeypatch: pytest.MonkeyPatch) -> None:
    connect, connection = setup_connection(monkeypatch)
    patient = PatientConversation(uuid4(), uuid4(), "D'Ávila", datetime.now(UTC))
    PostgresPatientRepository(DatabaseSettings(URL)).create("alice", patient)
    assert connect.call_count == 1
    calls = connection.execute.call_args_list
    assert len(calls) == 2
    assert patient.display_name not in calls[0].args[0]
    assert calls[0].args[1] == (patient.id, "alice", patient.display_name, True, patient.created_at)
    assert calls[1].args[1] == (patient.conversation_id, patient.id, patient.created_at)
    connect.return_value.__exit__.assert_called_once_with(None, None, None)


def test_second_insert_failure_exits_transaction_with_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connect, connection = setup_connection(monkeypatch)
    connection.execute.side_effect = [None, psycopg.IntegrityError("secret")]
    patient = PatientConversation(uuid4(), uuid4(), "A", datetime.now(UTC))
    with pytest.raises(DatabaseConnectionError) as captured:
        PostgresPatientRepository(DatabaseSettings(URL)).create("alice", patient)
    assert "secret" not in str(captured.value)
    assert connect.return_value.__exit__.call_args.args[0] is psycopg.IntegrityError


def test_reads_are_scoped_and_parameterized(monkeypatch: pytest.MonkeyPatch) -> None:
    connect, connection = setup_connection(monkeypatch)
    cursor = connection.cursor.return_value.__enter__.return_value
    patient = PatientConversation(uuid4(), uuid4(), "A", datetime.now(UTC))
    cursor.fetchall.return_value = [patient]
    cursor.fetchone.return_value = patient
    repo = PostgresPatientRepository(DatabaseSettings(URL))
    assert repo.list_for_owner("alice", limit=10, offset=20) == (patient,)
    assert "owner_username = %s" in cursor.execute.call_args.args[0]
    assert cursor.execute.call_args.args[1] == ("alice", 10, 20)
    assert "read_only=on" in connect.call_args.kwargs["options"]
    assert repo.get("bob", patient.id) == patient
    assert "owner_username = %s" in cursor.execute.call_args.args[0]
    assert cursor.execute.call_args.args[1] == ("bob", patient.id)
    cursor.fetchone.return_value = None
    assert repo.get("bob", uuid4()) is None


@pytest.mark.parametrize(
    "version,applied",
    [
        (None, (1, 2, 3, 4)),
        (1, (2, 3, 4)),
        (2, (3, 4)),
        (3, (4,)),
        (4, ()),
    ],
)
def test_migration_tracks_version_and_skips_existing(
    monkeypatch: pytest.MonkeyPatch, version: int | None, applied: tuple[int, ...]
) -> None:
    connect, connection = setup_connection(monkeypatch)
    connection.execute.return_value.fetchone.side_effect = [(True,), (version,)]
    assert migrate_database(DatabaseSettings(URL)) == applied
    sql = "\n".join(call.args[0] for call in connection.execute.call_args_list)
    assert "pg_try_advisory_xact_lock" in sql
    assert ("CREATE TABLE tech_ai.patients" in sql) is (1 in applied)
    assert ("CREATE TABLE tech_ai.messages" in sql) is (2 in applied)
    assert ("CREATE TABLE tech_ai.attachments" in sql) is (3 in applied)
    assert ("CREATE TABLE tech_ai.analyses" in sql) is (3 in applied)
    assert ("DROP CONSTRAINT attachments_modality_check" in sql) is (4 in applied)
    assert ("REVOKE ALL ON SCHEMA tech_ai FROM PUBLIC" in sql) is (1 in applied)
    if 1 in applied:
        assert "patient_id uuid NOT NULL UNIQUE REFERENCES" in sql
        assert "ENABLE ROW LEVEL SECURITY" in sql
    connect.return_value.__exit__.assert_called_once_with(None, None, None)


def test_newer_schema_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _, connection = setup_connection(monkeypatch)
    connection.execute.return_value.fetchone.side_effect = [(True,), (5,)]
    with pytest.raises(DatabaseConnectionError, match="mais recente"):
        migrate_database(DatabaseSettings(URL))


def test_migrate_command(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("TECH_AI_DATABASE_URL", URL)
    _, connection = setup_connection(monkeypatch)
    connection.execute.return_value.fetchone.side_effect = [(True,), (None,)]
    assert main(["migrate-db"]) == 0
    assert "Migrações aplicadas: 1, 2, 3, 4" in capsys.readouterr().out


def test_migration_fails_fast_when_another_migration_has_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, connection = setup_connection(monkeypatch)
    connection.execute.return_value.fetchone.return_value = (False,)
    with pytest.raises(DatabaseConnectionError, match="Outra migração"):
        migrate_database(DatabaseSettings(URL))
    assert connection.execute.call_count == 1
