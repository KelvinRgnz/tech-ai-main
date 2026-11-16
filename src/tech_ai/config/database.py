"""Configuração privada da conexão PostgreSQL."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from tech_ai.errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    url: str = field(repr=False)

    def __post_init__(self) -> None:
        try:
            parsed = urlsplit(self.url)
            valid = (
                parsed.scheme in {"postgres", "postgresql"}
                and bool(parsed.hostname)
                and bool(parsed.username)
                and bool(parsed.password)
                and parsed.password != "[YOUR-PASSWORD]"  # noqa: S105 -- placeholder only
                and bool(parsed.path.strip("/"))
                and (parsed.port is None or parsed.port > 0)
            )
        except ValueError:
            valid = False
        if not valid:
            raise ConfigurationError("TECH_AI_DATABASE_URL ausente ou inválida.") from None

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> DatabaseSettings:
        values = os.environ if environment is None else environment
        return cls(url=values.get("TECH_AI_DATABASE_URL", "").strip())
