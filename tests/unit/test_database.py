from unittest.mock import MagicMock

import psycopg
import pytest

from tech_ai.config.database import DatabaseSettings
from tech_ai.errors import ConfigurationError, DatabaseConnectionError
from tech_ai.integrations.postgres import check_connection
from tech_ai.runner import main

URL = "postgresql://test:private-password@localhost:5432/test"


@pytest.mark.parametrize("url", ["", "https://localhost/db", "postgresql://a@host/db"])
def test_invalid_url_does_not_disclose_value(url: str) -> None:
    with pytest.raises(ConfigurationError, match="TECH_AI_DATABASE_URL"):
        DatabaseSettings.from_environment({"TECH_AI_DATABASE_URL": url})


def test_settings_hide_password() -> None:
    assert "private-password" not in repr(DatabaseSettings(URL))


def test_check_uses_tls_read_only_and_closes_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    connect = MagicMock()
    connection = connect.return_value.__enter__.return_value
    connection.execute.return_value.fetchone.return_value = (1,)
    monkeypatch.setattr(psycopg, "connect", connect)
    check_connection(DatabaseSettings(URL))
    assert connect.call_args.kwargs["sslmode"] == "require"
    assert connect.call_args.kwargs["connect_timeout"] == 10
    assert "default_transaction_read_only=on" in connect.call_args.kwargs["options"]
    connection.execute.assert_called_once_with("SELECT 1")
    connect.return_value.__exit__.assert_called_once()


def test_driver_error_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(psycopg, "connect", MagicMock(side_effect=psycopg.OperationalError(URL)))
    with pytest.raises(DatabaseConnectionError) as captured:
        check_connection(DatabaseSettings(URL))
    assert "private-password" not in str(captured.value)
    assert captured.value.__suppress_context__


def test_check_db_cli(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("TECH_AI_DATABASE_URL", URL)
    connect = MagicMock()
    connect.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = (1,)
    monkeypatch.setattr(psycopg, "connect", connect)
    assert main(["check-db"]) == 0
    assert "private-password" not in capsys.readouterr().out
