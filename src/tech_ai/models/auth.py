"""Usuário autenticado e sessão emitida pelo runtime HTTP."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuthUser:
    """Identidade mínima exposta depois do login."""

    username: str


@dataclass(frozen=True, slots=True)
class SessionToken:
    """Token assinado entregue ao cliente HTTP."""

    value: str
    username: str
    expires_at: int
