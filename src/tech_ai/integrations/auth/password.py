"""Hash PBKDF2-SHA256 para senhas de acesso ao assistente."""

from __future__ import annotations

import hashlib
import hmac
import secrets

_PREFIX = "pbkdf2"
_ITERATIONS = 120_000


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """Gera um hash reproduzível sem persistir a senha em texto."""

    salt_bytes = salt if salt is not None else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, _ITERATIONS)
    return f"{_PREFIX}${_ITERATIONS}${salt_bytes.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """Compara a senha com o hash em tempo constante."""

    try:
        prefix, iteration_text, salt_hex, digest_hex = encoded.split("$", 3)
        iterations = int(iteration_text)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except ValueError:
        return False
    if prefix != _PREFIX or iterations <= 0:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)
