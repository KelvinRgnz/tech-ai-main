"""Configurações externas do runtime e da recuperação semântica."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from tech_ai.errors import ConfigurationError

_DEFAULT_MANIFEST_PATH = "configs/models/tech3-v3-pt-br.json"
_CLOUD_HOST = "api.trychroma.com"
_CLOUD_PORT = "443"
_LOCAL_HOST = "localhost"
_LOCAL_PORT = "8000"
_DEFAULT_COLLECTION = "medquad_knowledge_minilm_v1"


def load_project_environment(path: Path | None = None) -> None:
    """Carrega `.env` sem sobrescrever variáveis já definidas na sessão."""

    env_path = Path(".env") if path is None else path
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip("'\"")


def _positive_integer(value: str, variable: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise ConfigurationError(f"{variable} deve ser um número inteiro.") from error
    if parsed <= 0:
        raise ConfigurationError(f"{variable} deve ser maior que zero.")
    return parsed


def _positive_float(value: str, variable: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise ConfigurationError(f"{variable} deve ser um número.") from error
    if parsed <= 0:
        raise ConfigurationError(f"{variable} deve ser maior que zero.")
    return parsed


def _bounded_float(
    value: str,
    variable: str,
    *,
    minimum: float,
    maximum: float,
) -> float:
    parsed = _positive_float(value, variable)
    if parsed < minimum or parsed > maximum:
        raise ConfigurationError(
            f"{variable} deve estar entre {minimum} e {maximum}."
        )
    return parsed


def _boolean(value: str, variable: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{variable} deve ser true ou false.")


@dataclass(frozen=True, slots=True)
class Settings:
    """Parâmetros dos casos de uso, sem credenciais ou detalhes de SDK."""

    model_manifest_path: Path = Path(_DEFAULT_MANIFEST_PATH)
    retrieval_limit: int = 4
    max_retrieval_distance: float = 0.55
    max_source_characters: int = 2_000
    max_answer_characters: int = 4_000

    def __post_init__(self) -> None:
        if not self.model_manifest_path.name:
            raise ConfigurationError("TECH_AI_MODEL_MANIFEST_PATH não pode ser vazio.")
        if self.retrieval_limit <= 0:
            raise ConfigurationError("TECH_AI_RETRIEVAL_LIMIT deve ser maior que zero.")
        if self.max_retrieval_distance <= 0:
            raise ConfigurationError(
                "TECH_AI_MAX_RETRIEVAL_DISTANCE deve ser maior que zero."
            )
        if self.max_source_characters <= 0:
            raise ConfigurationError("TECH_AI_MAX_SOURCE_CHARACTERS deve ser maior que zero.")
        if self.max_answer_characters <= 0:
            raise ConfigurationError("TECH_AI_MAX_ANSWER_CHARACTERS deve ser maior que zero.")

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> Settings:
        values = environment if environment is not None else os.environ
        return cls(
            model_manifest_path=Path(
                values.get("TECH_AI_MODEL_MANIFEST_PATH", _DEFAULT_MANIFEST_PATH)
            ),
            retrieval_limit=_positive_integer(
                values.get("TECH_AI_RETRIEVAL_LIMIT", "4"),
                "TECH_AI_RETRIEVAL_LIMIT",
            ),
            max_retrieval_distance=_positive_float(
                values.get("TECH_AI_MAX_RETRIEVAL_DISTANCE", "0.55"),
                "TECH_AI_MAX_RETRIEVAL_DISTANCE",
            ),
            max_source_characters=_positive_integer(
                values.get("TECH_AI_MAX_SOURCE_CHARACTERS", "2000"),
                "TECH_AI_MAX_SOURCE_CHARACTERS",
            ),
            max_answer_characters=_positive_integer(
                values.get("TECH_AI_MAX_ANSWER_CHARACTERS", "4000"),
                "TECH_AI_MAX_ANSWER_CHARACTERS",
            ),
        )


@dataclass(frozen=True, slots=True)
class ChromaSettings:
    """Destino da coleção escrita pelo ``tech-ingestao``."""

    mode: str = "local"
    host: str = "localhost"
    port: int = 8000
    collection: str = "medquad_knowledge_minilm_v1"
    ssl: bool = False
    api_key: str = ""
    tenant: str = ""
    database: str = ""

    def __post_init__(self) -> None:
        if self.mode not in {"local", "cloud"}:
            raise ConfigurationError("CHROMA_MODE deve ser 'local' ou 'cloud'.")
        if self.mode != "cloud":
            return
        if not self.api_key:
            raise ConfigurationError("CHROMA_API_KEY é obrigatória no modo cloud.")
        if not self.tenant:
            raise ConfigurationError("CHROMA_TENANT é obrigatório no modo cloud.")
        if not self.database:
            raise ConfigurationError("CHROMA_DATABASE é obrigatório no modo cloud.")

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> ChromaSettings:
        values = os.environ if environment is None else environment
        mode = values.get("CHROMA_MODE", "local").strip().lower()
        collection = values.get("CHROMA_COLLECTION", _DEFAULT_COLLECTION).strip()
        if mode == "cloud":
            host = values.get("CHROMA_HOST", _CLOUD_HOST).strip()
            port = _positive_integer(values.get("CHROMA_PORT", _CLOUD_PORT), "CHROMA_PORT")
            ssl = _boolean(values.get("CHROMA_SSL", "true"), "CHROMA_SSL")
        else:
            host = values.get("CHROMA_HOST", _LOCAL_HOST).strip()
            port = _positive_integer(values.get("CHROMA_PORT", _LOCAL_PORT), "CHROMA_PORT")
            ssl = _boolean(values.get("CHROMA_SSL", "false"), "CHROMA_SSL")
        if not host:
            raise ConfigurationError("CHROMA_HOST não pode ser vazio.")
        if not collection:
            raise ConfigurationError("CHROMA_COLLECTION não pode ser vazia.")
        return cls(
            mode=mode,
            host=host,
            port=port,
            collection=collection,
            ssl=ssl,
            api_key=values.get("CHROMA_API_KEY", "").strip(),
            tenant=values.get("CHROMA_TENANT", "").strip(),
            database=values.get("CHROMA_DATABASE", "").strip(),
        )


@dataclass(frozen=True, slots=True)
class LocalEmbeddingSettings:
    """Contrato do modelo ONNX compartilhado com o ``tech-ingestao``."""

    model: str = "all-MiniLM-L6-v2"
    dimensions: int = 384

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> LocalEmbeddingSettings:
        values = os.environ if environment is None else environment
        model = values.get("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2").strip()
        dimensions = _positive_integer(
            values.get("LOCAL_EMBEDDING_DIMENSIONS", "384"),
            "LOCAL_EMBEDDING_DIMENSIONS",
        )
        if model != "all-MiniLM-L6-v2":
            raise ConfigurationError(
                "LOCAL_EMBEDDING_MODEL deve ser 'all-MiniLM-L6-v2' nesta versão."
            )
        if dimensions != 384:
            raise ConfigurationError(
                "LOCAL_EMBEDDING_DIMENSIONS deve ser 384 para all-MiniLM-L6-v2."
            )
        return cls(model=model, dimensions=dimensions)


@dataclass(frozen=True, slots=True)
class GenerationSettings:
    """Parâmetros conservadores para inferência sem loops e com amostragem leve."""

    max_new_tokens: int = 512
    repetition_penalty: float = 1.1
    no_repeat_ngram_size: int = 4
    temperature: float = 0.3

    def __post_init__(self) -> None:
        if self.max_new_tokens <= 0:
            raise ConfigurationError("TECH_AI_MAX_NEW_TOKENS deve ser maior que zero.")
        if self.repetition_penalty <= 0:
            raise ConfigurationError("TECH_AI_REPETITION_PENALTY deve ser maior que zero.")
        if self.no_repeat_ngram_size <= 0:
            raise ConfigurationError(
                "TECH_AI_NO_REPEAT_NGRAM_SIZE deve ser maior que zero."
            )
        if self.temperature < 0.2 or self.temperature > 0.7:
            raise ConfigurationError("TECH_AI_TEMPERATURE deve estar entre 0.2 e 0.7.")

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> GenerationSettings:
        values = os.environ if environment is None else environment
        return cls(
            max_new_tokens=_positive_integer(
                values.get("TECH_AI_MAX_NEW_TOKENS", "512"),
                "TECH_AI_MAX_NEW_TOKENS",
            ),
            repetition_penalty=_positive_float(
                values.get("TECH_AI_REPETITION_PENALTY", "1.1"),
                "TECH_AI_REPETITION_PENALTY",
            ),
            no_repeat_ngram_size=_positive_integer(
                values.get("TECH_AI_NO_REPEAT_NGRAM_SIZE", "4"),
                "TECH_AI_NO_REPEAT_NGRAM_SIZE",
            ),
            temperature=_bounded_float(
                values.get("TECH_AI_TEMPERATURE", "0.3"),
                "TECH_AI_TEMPERATURE",
                minimum=0.2,
                maximum=0.7,
            ),
        )
