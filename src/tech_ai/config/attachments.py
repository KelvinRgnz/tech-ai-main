"""Configuração do armazenamento local de anexos fictícios."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from tech_ai.errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class AttachmentSettings:
    storage_dir: Path = Path(".data/attachments")

    def __post_init__(self) -> None:
        if not str(self.storage_dir).strip():
            raise ConfigurationError("TECH_AI_ATTACHMENT_DIR inválido.")

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> AttachmentSettings:
        values = os.environ if environment is None else environment
        raw_path = values.get("TECH_AI_ATTACHMENT_DIR", ".data/attachments").strip()
        if not raw_path:
            raise ConfigurationError("TECH_AI_ATTACHMENT_DIR inválido.")
        return cls(Path(raw_path))
