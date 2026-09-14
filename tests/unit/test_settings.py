from __future__ import annotations

import os
from pathlib import Path

import pytest

from tech_ai.config.settings import (
    AuthSettings,
    ChromaSettings,
    GenerationSettings,
    LocalEmbeddingSettings,
    Settings,
    load_project_environment,
)
from tech_ai.errors import ConfigurationError


def test_settings_use_documented_default() -> None:
    settings = Settings.from_environment({})

    assert settings.model_manifest_path == Path("configs/models/tech3-v3-pt-br.json")
    assert settings.retrieval_limit == 4
    assert settings.max_retrieval_distance == 0.55
    assert settings.max_source_characters == 2_000
    assert settings.max_answer_characters == 4_000


def test_settings_read_environment_override() -> None:
    settings = Settings.from_environment(
        {
            "TECH_AI_MODEL_MANIFEST_PATH": "published/model-manifest.json",
            "TECH_AI_RETRIEVAL_LIMIT": "7",
            "TECH_AI_MAX_RETRIEVAL_DISTANCE": "0.42",
            "TECH_AI_MAX_SOURCE_CHARACTERS": "900",
            "TECH_AI_MAX_ANSWER_CHARACTERS": "1500",
        }
    )

    assert settings.model_manifest_path == Path("published/model-manifest.json")
    assert settings.retrieval_limit == 7
    assert settings.max_retrieval_distance == 0.42
    assert settings.max_source_characters == 900
    assert settings.max_answer_characters == 1500


def test_settings_reject_path_without_filename() -> None:
    with pytest.raises(ConfigurationError, match="não pode ser vazio"):
        Settings(model_manifest_path=Path("."))


@pytest.mark.parametrize(
    "environment",
    [
        {"TECH_AI_RETRIEVAL_LIMIT": "0"},
        {"TECH_AI_RETRIEVAL_LIMIT": "abc"},
        {"TECH_AI_MAX_RETRIEVAL_DISTANCE": "0"},
        {"TECH_AI_MAX_RETRIEVAL_DISTANCE": "invalid"},
        {"TECH_AI_MAX_SOURCE_CHARACTERS": "-1"},
        {"TECH_AI_MAX_ANSWER_CHARACTERS": "0"},
    ],
)
def test_settings_reject_invalid_positive_integers(environment: dict[str, str]) -> None:
    with pytest.raises(ConfigurationError, match="deve ser"):
        Settings.from_environment(environment)


def test_chroma_settings_use_shared_contract_and_overrides() -> None:
    defaults = ChromaSettings.from_environment({})
    configured = ChromaSettings.from_environment(
        {
            "CHROMA_HOST": "chroma",
            "CHROMA_PORT": "9000",
            "CHROMA_COLLECTION": "medical-v2",
            "CHROMA_SSL": "true",
        }
    )

    assert defaults.collection == "medquad_knowledge_minilm_v1"
    assert configured == ChromaSettings(
        host="chroma", port=9000, collection="medical-v2", ssl=True
    )


def test_chroma_settings_parse_cloud_contract() -> None:
    settings = ChromaSettings.from_environment(
        {
            "CHROMA_MODE": "cloud",
            "CHROMA_API_KEY": "ck-test",
            "CHROMA_TENANT": "tenant-1",
            "CHROMA_DATABASE": "fiap-tech-challenge-3",
        }
    )

    assert settings == ChromaSettings(
        mode="cloud",
        host="api.trychroma.com",
        port=443,
        collection="medquad_knowledge_minilm_v1",
        ssl=True,
        api_key="ck-test",
        tenant="tenant-1",
        database="fiap-tech-challenge-3",
    )


@pytest.mark.parametrize(
    "environment",
    [
        {"CHROMA_HOST": " "},
        {"CHROMA_COLLECTION": " "},
        {"CHROMA_SSL": "perhaps"},
        {"CHROMA_MODE": "remote"},
        {"CHROMA_MODE": "cloud"},
        {"CHROMA_MODE": "cloud", "CHROMA_API_KEY": "ck-test"},
        {
            "CHROMA_MODE": "cloud",
            "CHROMA_API_KEY": "ck-test",
            "CHROMA_TENANT": "tenant-1",
        },
    ],
)
def test_chroma_settings_reject_invalid_values(environment: dict[str, str]) -> None:
    with pytest.raises(ConfigurationError):
        ChromaSettings.from_environment(environment)


def test_load_project_environment_fills_missing_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CHROMA_MODE=cloud\n# comentario\n=ignored\nCHROMA_API_KEY='ck-file'\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("CHROMA_MODE", raising=False)
    monkeypatch.setenv("CHROMA_API_KEY", "ck-session")

    load_project_environment(env_file)
    load_project_environment(tmp_path / "missing.env")

    assert os.environ["CHROMA_MODE"] == "cloud"
    assert os.environ["CHROMA_API_KEY"] == "ck-session"


def test_local_embedding_settings_preserve_index_contract() -> None:
    assert LocalEmbeddingSettings.from_environment({}) == LocalEmbeddingSettings(
        model="all-MiniLM-L6-v2",
        dimensions=384,
    )


@pytest.mark.parametrize(
    "environment",
    [
        {"LOCAL_EMBEDDING_MODEL": "other-model"},
        {"LOCAL_EMBEDDING_DIMENSIONS": "768"},
        {"LOCAL_EMBEDDING_DIMENSIONS": "invalid"},
    ],
)
def test_local_embedding_settings_reject_incompatible_contract(
    environment: dict[str, str],
) -> None:
    with pytest.raises(ConfigurationError):
        LocalEmbeddingSettings.from_environment(environment)


def test_generation_settings_read_loop_controls() -> None:
    settings = GenerationSettings.from_environment(
        {
            "TECH_AI_MAX_NEW_TOKENS": "768",
            "TECH_AI_REPETITION_PENALTY": "1.2",
            "TECH_AI_NO_REPEAT_NGRAM_SIZE": "5",
            "TECH_AI_TEMPERATURE": "0.4",
        }
    )

    assert settings == GenerationSettings(
        max_new_tokens=768,
        repetition_penalty=1.2,
        no_repeat_ngram_size=5,
        temperature=0.4,
    )


def test_generation_settings_use_conservative_defaults() -> None:
    assert GenerationSettings.from_environment({}) == GenerationSettings(
        max_new_tokens=512,
        repetition_penalty=1.1,
        no_repeat_ngram_size=4,
        temperature=0.3,
    )


def test_generation_settings_reject_invalid_penalty() -> None:
    with pytest.raises(ConfigurationError, match="número"):
        GenerationSettings.from_environment({"TECH_AI_REPETITION_PENALTY": "abc"})


def test_generation_settings_reject_temperature_outside_range() -> None:
    with pytest.raises(ConfigurationError, match=r"entre 0\.2 e 0\.7"):
        GenerationSettings.from_environment({"TECH_AI_TEMPERATURE": "0.9"})


def test_auth_settings_parse_users_cookie_and_ttl() -> None:
    settings = AuthSettings.from_environment(
        {
            "TECH_AI_AUTH_SECRET": "test-secret-16chars",
            "TECH_AI_AUTH_USERS": "Academic:academic123; ana:pbkdf2$1$00$00",
            "TECH_AI_AUTH_TOKEN_TTL_SECONDS": "120",
            "TECH_AI_AUTH_COOKIE_NAME": "session_demo",
        }
    )
    mapping = settings.user_mapping()

    assert settings.secret == "test-secret-16chars"
    assert settings.token_ttl_seconds == 120
    assert settings.cookie_name == "session_demo"
    assert set(mapping) == {"academic", "ana"}
    assert mapping["academic"].startswith("pbkdf2$")
    assert mapping["ana"] == "pbkdf2$1$00$00"


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        (
            {"TECH_AI_AUTH_USERS": "academic:academic123"},
            "TECH_AI_AUTH_SECRET",
        ),
        (
            {
                "TECH_AI_AUTH_SECRET": "test-secret-16chars",
                "TECH_AI_AUTH_USERS": "",
            },
            "ao menos um usuário",
        ),
        (
            {
                "TECH_AI_AUTH_SECRET": "test-secret-16chars",
                "TECH_AI_AUTH_USERS": "academic:curta",
            },
            "8 caracteres",
        ),
        (
            {
                "TECH_AI_AUTH_SECRET": "test-secret-16chars",
                "TECH_AI_AUTH_USERS": "academic:academic123,Academic:outra-senha",
            },
            "duplicado",
        ),
        (
            {
                "TECH_AI_AUTH_SECRET": "test-secret-16chars",
                "TECH_AI_AUTH_USERS": "academic:",
            },
            "usuario:senha",
        ),
    ],
)
def test_auth_settings_reject_invalid_environment(
    environment: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(ConfigurationError, match=message):
        AuthSettings.from_environment(environment)


def test_auth_settings_reject_invalid_constructed_values() -> None:
    hashed = "pbkdf2$1$00$00"
    with pytest.raises(ConfigurationError, match="ao menos um usuário"):
        AuthSettings(secret="test-secret-16chars", users=())
    with pytest.raises(ConfigurationError, match="maior que zero"):
        AuthSettings(
            secret="test-secret-16chars",
            users=(("academic", hashed),),
            token_ttl_seconds=0,
        )
    with pytest.raises(ConfigurationError, match="COOKIE_NAME"):
        AuthSettings(
            secret="test-secret-16chars",
            users=(("academic", hashed),),
            cookie_name="  ",
        )
