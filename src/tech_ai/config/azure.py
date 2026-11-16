"""Configuração segura e limites locais das integrações Azure."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from tech_ai.errors import ConfigurationError

_REGION_PATTERN = re.compile(r"^[a-z0-9]+$")


def _boolean(value: str, variable: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{variable} deve ser true ou false.")


def _positive_integer(value: str, variable: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise ConfigurationError(f"{variable} deve ser um número inteiro.") from error
    if parsed <= 0:
        raise ConfigurationError(f"{variable} deve ser maior que zero.")
    return parsed


def _valid_endpoint(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return bool(
        parsed.scheme == "https"
        and parsed.hostname
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
    )


@dataclass(frozen=True, slots=True)
class AzureSettings:
    """Credenciais privadas por serviço; tudo permanece desligado por padrão."""

    speech_enabled: bool = False
    speech_key: str = field(default="", repr=False)
    speech_region: str = "brazilsouth"
    language_enabled: bool = False
    language_key: str = field(default="", repr=False)
    language_endpoint: str = ""
    document_enabled: bool = False
    document_key: str = field(default="", repr=False)
    document_endpoint: str = ""
    max_audio_seconds: int = 120
    max_document_pages: int = 2
    max_text_records_per_analysis: int = 20
    max_concurrent_requests: int = 1

    def __post_init__(self) -> None:
        if not _REGION_PATTERN.fullmatch(self.speech_region):
            raise ConfigurationError("TECH_AI_AZURE_SPEECH_REGION inválida.")
        self._validate_service(
            self.speech_enabled,
            key=self.speech_key,
            key_variable="TECH_AI_AZURE_SPEECH_KEY",
        )
        self._validate_service(
            self.language_enabled,
            key=self.language_key,
            key_variable="TECH_AI_AZURE_LANGUAGE_KEY",
            endpoint=self.language_endpoint,
            endpoint_variable="TECH_AI_AZURE_LANGUAGE_ENDPOINT",
        )
        self._validate_service(
            self.document_enabled,
            key=self.document_key,
            key_variable="TECH_AI_AZURE_DOCUMENT_KEY",
            endpoint=self.document_endpoint,
            endpoint_variable="TECH_AI_AZURE_DOCUMENT_ENDPOINT",
        )
        limits = {
            "TECH_AI_AZURE_MAX_AUDIO_SECONDS": self.max_audio_seconds,
            "TECH_AI_AZURE_MAX_DOCUMENT_PAGES": self.max_document_pages,
            "TECH_AI_AZURE_MAX_TEXT_RECORDS": self.max_text_records_per_analysis,
            "TECH_AI_AZURE_MAX_CONCURRENT_REQUESTS": self.max_concurrent_requests,
        }
        for variable, value in limits.items():
            if value <= 0:
                raise ConfigurationError(f"{variable} deve ser maior que zero.")
        if self.max_audio_seconds > 120:
            raise ConfigurationError("TECH_AI_AZURE_MAX_AUDIO_SECONDS não pode exceder 120.")
        if self.max_concurrent_requests > 4:
            raise ConfigurationError(
                "TECH_AI_AZURE_MAX_CONCURRENT_REQUESTS não pode exceder 4 nesta POC."
            )

    @staticmethod
    def _validate_service(
        enabled: bool,
        *,
        key: str,
        key_variable: str,
        endpoint: str | None = None,
        endpoint_variable: str | None = None,
    ) -> None:
        if not enabled:
            return
        if not key.strip():
            raise ConfigurationError(f"{key_variable} obrigatória quando o serviço está ativo.")
        if endpoint is not None and endpoint_variable is not None and not _valid_endpoint(endpoint):
            raise ConfigurationError(f"{endpoint_variable} deve ser uma URL HTTPS válida.")

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> AzureSettings:
        values = os.environ if environment is None else environment
        return cls(
            speech_enabled=_boolean(
                values.get("TECH_AI_AZURE_SPEECH_ENABLED", "false"),
                "TECH_AI_AZURE_SPEECH_ENABLED",
            ),
            speech_key=values.get("TECH_AI_AZURE_SPEECH_KEY", "").strip(),
            speech_region=values.get(
                "TECH_AI_AZURE_SPEECH_REGION", "brazilsouth"
            ).strip().lower(),
            language_enabled=_boolean(
                values.get("TECH_AI_AZURE_LANGUAGE_ENABLED", "false"),
                "TECH_AI_AZURE_LANGUAGE_ENABLED",
            ),
            language_key=values.get("TECH_AI_AZURE_LANGUAGE_KEY", "").strip(),
            language_endpoint=values.get("TECH_AI_AZURE_LANGUAGE_ENDPOINT", "").strip(),
            document_enabled=_boolean(
                values.get("TECH_AI_AZURE_DOCUMENT_ENABLED", "false"),
                "TECH_AI_AZURE_DOCUMENT_ENABLED",
            ),
            document_key=values.get("TECH_AI_AZURE_DOCUMENT_KEY", "").strip(),
            document_endpoint=values.get("TECH_AI_AZURE_DOCUMENT_ENDPOINT", "").strip(),
            max_audio_seconds=_positive_integer(
                values.get("TECH_AI_AZURE_MAX_AUDIO_SECONDS", "120"),
                "TECH_AI_AZURE_MAX_AUDIO_SECONDS",
            ),
            max_document_pages=_positive_integer(
                values.get("TECH_AI_AZURE_MAX_DOCUMENT_PAGES", "2"),
                "TECH_AI_AZURE_MAX_DOCUMENT_PAGES",
            ),
            max_text_records_per_analysis=_positive_integer(
                values.get("TECH_AI_AZURE_MAX_TEXT_RECORDS", "20"),
                "TECH_AI_AZURE_MAX_TEXT_RECORDS",
            ),
            max_concurrent_requests=_positive_integer(
                values.get("TECH_AI_AZURE_MAX_CONCURRENT_REQUESTS", "1"),
                "TECH_AI_AZURE_MAX_CONCURRENT_REQUESTS",
            ),
        )
