from __future__ import annotations

import time

import pytest

from tech_ai.errors import AuthenticationError, ConfigurationError
from tech_ai.integrations.auth.password import hash_password, verify_password
from tech_ai.integrations.auth.session_token import issue_session_token, read_session_token
from tech_ai.services.auth_service import AuthService


def test_password_hash_verifies_and_rejects_wrong_secret() -> None:
    encoded = hash_password("academic123")

    assert encoded.startswith("pbkdf2$")
    assert verify_password("academic123", encoded) is True
    assert verify_password("outra-senha", encoded) is False
    assert verify_password("academic123", "formato-invalido") is False
    assert verify_password("academic123", "other$1$00$00") is False
    assert verify_password("academic123", "pbkdf2$0$00$00") is False


def test_session_token_roundtrip_and_expiry() -> None:
    token, expires_at = issue_session_token(
        "academic",
        secret="test-secret-16chars",
        ttl_seconds=60,
        now=1_000,
    )

    assert read_session_token(token, secret="test-secret-16chars", now=1_010) == "academic"
    assert expires_at == 1_060
    with pytest.raises(AuthenticationError, match="expirada"):
        read_session_token(token, secret="test-secret-16chars", now=1_061)
    with pytest.raises(AuthenticationError, match="inválida"):
        read_session_token(token, secret="another-secret-16", now=1_010)
    with pytest.raises(AuthenticationError, match="inválida"):
        read_session_token("token-quebrado", secret="test-secret-16chars", now=1_010)


def test_auth_service_login_logout_and_session() -> None:
    service = AuthService(
        {"academic": hash_password("academic123")},
        secret="test-secret-16chars",
        token_ttl_seconds=60,
    )

    session = service.login("Academic", "academic123")
    user = service.read_session(session.value)

    assert session.username == "academic"
    assert user.username == "academic"
    service.logout(session.value)
    with pytest.raises(AuthenticationError, match="encerrada"):
        service.read_session(session.value)


@pytest.mark.parametrize(
    ("username", "password", "message"),
    [
        ("", "academic123", "Informe usuário e senha"),
        ("academic", "", "Informe usuário e senha"),
        ("academic", "errada123", "Credenciais inválidas"),
        ("ghost", "academic123", "Credenciais inválidas"),
    ],
)
def test_auth_service_rejects_invalid_credentials(
    username: str,
    password: str,
    message: str,
) -> None:
    service = AuthService(
        {"academic": hash_password("academic123")},
        secret="test-secret-16chars",
        token_ttl_seconds=60,
    )

    with pytest.raises(AuthenticationError, match=message):
        service.login(username, password)


def test_auth_service_rejects_missing_token_and_unknown_user() -> None:
    service = AuthService(
        {"academic": hash_password("academic123")},
        secret="test-secret-16chars",
        token_ttl_seconds=60,
    )

    with pytest.raises(AuthenticationError, match="obrigatória"):
        service.read_session(None)
    token, _expires = issue_session_token(
        "ghost",
        secret="test-secret-16chars",
        ttl_seconds=60,
    )
    with pytest.raises(AuthenticationError, match="inválida"):
        service.read_session(token)


def test_auth_service_rejects_empty_directory() -> None:
    with pytest.raises(ConfigurationError, match="Nenhum usuário"):
        AuthService({}, secret="test-secret-16chars", token_ttl_seconds=60)


def test_auth_service_rejects_invalid_secret_and_ttl() -> None:
    users = {"academic": hash_password("academic123")}
    with pytest.raises(ConfigurationError, match="16 caracteres"):
        AuthService(users, secret="curta", token_ttl_seconds=60)
    with pytest.raises(ConfigurationError, match="maior que zero"):
        AuthService(users, secret="test-secret-16chars", token_ttl_seconds=0)


def test_auth_service_logout_ignores_blank_token() -> None:
    service = AuthService(
        {"academic": hash_password("academic123")},
        secret="test-secret-16chars",
        token_ttl_seconds=60,
    )

    service.logout(None)
    service.logout("   ")


def test_session_token_issue_uses_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "time", lambda: 2_000.0)
    token, expires_at = issue_session_token(
        "academic",
        secret="test-secret-16chars",
        ttl_seconds=10,
    )

    assert expires_at == 2_010
    assert read_session_token(token, secret="test-secret-16chars", now=2_005) == "academic"
