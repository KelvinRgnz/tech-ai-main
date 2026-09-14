from __future__ import annotations

from pathlib import Path

from tech_ai.config.settings import ChromaSettings, GenerationSettings, Settings
from tech_ai.models.assistant import ACADEMIC_DISCLAIMER
from tech_ai.services.model_artifact_service import inspect_model_artifact


def test_default_manifest_loads_pt_br_lora_adapter() -> None:
    artifact = inspect_model_artifact(Path("configs/models/tech3-v3-pt-br.json"))

    assert artifact.artifact_type == "peft_adapter"
    assert artifact.artifact_uri == "hf://mikaelkanzaki/tech3-v3-pt-br"
    assert artifact.base_model_id == "unsloth/Qwen3-4B-Instruct-2507-unsloth-bnb-4bit"
    assert Settings.from_environment({}).model_manifest_path == Path(
        "configs/models/tech3-v3-pt-br.json"
    )


def test_chroma_cloud_contract_does_not_require_openai() -> None:
    environment_file = Path(".env.example").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    settings = ChromaSettings.from_environment(
        {
            "CHROMA_MODE": "cloud",
            "CHROMA_API_KEY": "ck-test",
            "CHROMA_TENANT": "tenant-1",
            "CHROMA_DATABASE": "fiap-tech-challenge-3",
        }
    )

    assert "OPENAI_API_KEY" not in environment_file
    assert "openai" not in pyproject.casefold()
    assert settings.mode == "cloud"
    assert settings.host == "api.trychroma.com"
    assert settings.database == "fiap-tech-challenge-3"
    assert settings.collection == "medquad_knowledge_minilm_v1"
    assert GenerationSettings.from_environment({}).max_new_tokens == 512


def test_academic_disclaimer_is_always_present() -> None:
    assert "não substitui avaliação médica" in ACADEMIC_DISCLAIMER.casefold()
