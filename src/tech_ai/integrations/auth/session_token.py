"""Tokens de sessão HMAC, sem JWT externo."""

from __future__ import annotations

import hashlib
import hmac
import time

from tech_ai.errors import AuthenticationError


def issue_session_token(
    username: str,
    *,
    secret: str,
    ttl_seconds: int,
    now: int | None = None,
) -> tuple[str, int]:
    """Assina um token com expiração absoluta em epoch."""

    expires_at = (int(time.time()) if now is None else now) + ttl_seconds
    payload = f"v1|{username}|{expires_at}"
    signature = _sign(payload, secret)
    return f"{payload}|{signature}", expires_at


def read_session_token(token: str, *, secret: str, now: int | None = None) -> str:
    """Devolve o usuário se a assinatura e o prazo forem válidos."""

    try:
        version, username, expires_text, signature = token.split("|", 3)
        expires_at = int(expires_text)
    except ValueError as error:
        raise AuthenticationError("Sessão inválida.") from error
    payload = f"{version}|{username}|{expires_at}"
    expected = _sign(payload, secret)
    if version != "v1" or not username or not hmac.compare_digest(signature, expected):
        raise AuthenticationError("Sessão inválida.")
    current = int(time.time()) if now is None else now
    if expires_at <= current:
        raise AuthenticationError("Sessão expirada.")
    return username


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
