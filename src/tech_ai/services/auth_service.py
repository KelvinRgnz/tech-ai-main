"""Login, emissão e validação de sessão do assistente."""

from __future__ import annotations

from collections.abc import Mapping

from tech_ai.errors import AuthenticationError, ConfigurationError
from tech_ai.integrations.auth.password import verify_password
from tech_ai.integrations.auth.session_token import issue_session_token, read_session_token
from tech_ai.models.auth import AuthUser, SessionToken


class AuthService:
    """Mantém usuários em memória e sessões assinadas."""

    def __init__(
        self,
        users: Mapping[str, str],
        *,
        secret: str,
        token_ttl_seconds: int,
    ) -> None:
        if not users:
            raise ConfigurationError("Nenhum usuário foi configurado para autenticação.")
        if len(secret) < 16:
            raise ConfigurationError("TECH_AI_AUTH_SECRET deve ter ao menos 16 caracteres.")
        if token_ttl_seconds <= 0:
            raise ConfigurationError("TECH_AI_AUTH_TOKEN_TTL_SECONDS deve ser maior que zero.")
        self._users = {username.casefold(): encoded for username, encoded in users.items()}
        self._secret = secret
        self._token_ttl_seconds = token_ttl_seconds
        self._revoked: set[str] = set()

    def login(self, username: str, password: str) -> SessionToken:
        normalized = username.strip()
        if not normalized or not password:
            raise AuthenticationError("Informe usuário e senha.")
        encoded = self._users.get(normalized.casefold())
        if encoded is None or not verify_password(password, encoded):
            raise AuthenticationError("Credenciais inválidas.")
        value, expires_at = issue_session_token(
            normalized.casefold(),
            secret=self._secret,
            ttl_seconds=self._token_ttl_seconds,
        )
        return SessionToken(value=value, username=normalized.casefold(), expires_at=expires_at)

    def read_session(self, token: str | None) -> AuthUser:
        if token is None or not token.strip():
            raise AuthenticationError("Autenticação obrigatória.")
        stripped = token.strip()
        if stripped in self._revoked:
            raise AuthenticationError("Sessão encerrada.")
        username = read_session_token(stripped, secret=self._secret)
        if username.casefold() not in self._users:
            raise AuthenticationError("Sessão inválida.")
        return AuthUser(username=username)

    def logout(self, token: str | None) -> None:
        if token is None or not token.strip():
            return
        self._revoked.add(token.strip())
