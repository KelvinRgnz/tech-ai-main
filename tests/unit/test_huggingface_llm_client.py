from __future__ import annotations

import contextlib
import sys
from collections.abc import Mapping, Sequence
from types import SimpleNamespace
from typing import Any, cast

import pytest

from tech_ai.config.settings import GenerationSettings
from tech_ai.errors import ModelRuntimeError
from tech_ai.integrations.llm.huggingface import HuggingFaceLlmClient, resolve_artifact_source
from tech_ai.models.model_artifact import ModelArtifact


def pt_br_artifact() -> ModelArtifact:
    return ModelArtifact(
        schema_version="1.0",
        artifact_id="qwen3-4b-medquad-candidate-v3-pt-br",
        artifact_type="peft_adapter",
        artifact_uri="hf://mikaelkanzaki/tech3-v3-pt-br",
        artifact_revision="87564cac62fe90c11b23cd3d2f2124e3d8f10118",
        base_model_id="unsloth/Qwen3-4B-Instruct-2507-unsloth-bnb-4bit",
        base_model_revision="7744afa8566e264af1a92a806d8d9aae00cc7c78",
        tokenizer_id="unsloth/Qwen3-4B-Instruct-2507-unsloth-bnb-4bit",
        tokenizer_revision="7744afa8566e264af1a92a806d8d9aae00cc7c78",
        producer_commit="a" * 40,
        dataset_manifest_sha256="b" * 64,
    )


class FakeTokenizer:
    pad_token_id: int | None = None
    eos_token_id = 1
    loaded: tuple[str, str | None] | None = None

    @classmethod
    def from_pretrained(cls, name: str, revision: str | None = None) -> FakeTokenizer:
        cls.loaded = (name, revision)
        return cls()

    def apply_chat_template(self, messages: object, **_kwargs: object) -> str:
        del messages
        return "PROMPT"

    def __call__(self, prompt: str, return_tensors: str = "pt") -> dict[str, Any]:
        del prompt, return_tensors

        class _Ids:
            shape = (1, 4)

            def to(self, _device: object) -> _Ids:
                return self

        return {"input_ids": _Ids()}

    def decode(self, tokens: object, skip_special_tokens: bool = True) -> str:
        del tokens, skip_special_tokens
        return "O estresse é uma resposta do organismo. [1]"


class FakeBaseModel:
    def __init__(self) -> None:
        self.eval_called = False
        self.generate_kwargs: dict[str, object] = {}

    def eval(self) -> FakeBaseModel:
        self.eval_called = True
        return self

    def parameters(self) -> Any:
        yield SimpleNamespace(device="cpu")

    def generate(self, **kwargs: object) -> list[list[int]]:
        self.generate_kwargs = dict(kwargs)
        return [[0, 1, 2, 3, 10, 11]]


def _install_runtime_fakes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    base_model: FakeBaseModel,
    loaded: dict[str, object],
) -> None:
    class FakeAutoModel:
        @staticmethod
        def from_pretrained(
            name: str,
            revision: str | None = None,
            **kwargs: object,
        ) -> FakeBaseModel:
            loaded["base"] = {"name": name, "revision": revision, "kwargs": kwargs}
            return base_model

    class FakePeftModel:
        @staticmethod
        def from_pretrained(
            model: FakeBaseModel,
            source: str,
            revision: str | None = None,
        ) -> FakeBaseModel:
            loaded["adapter"] = {"source": source, "revision": revision, "base": model}
            return model

    class FakeBitsAndBytesConfig:
        def __init__(self, **kwargs: object) -> None:
            loaded["bnb"] = kwargs

    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(
            cuda=SimpleNamespace(is_available=lambda: True),
            bfloat16="bf16",
            float32="fp32",
            inference_mode=contextlib.nullcontext,
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "transformers",
        SimpleNamespace(
            AutoModelForCausalLM=FakeAutoModel,
            AutoTokenizer=FakeTokenizer,
            BitsAndBytesConfig=FakeBitsAndBytesConfig,
        ),
    )
    monkeypatch.setitem(sys.modules, "peft", SimpleNamespace(PeftModel=FakePeftModel))


def test_resolve_artifact_source_strips_hf_prefix() -> None:
    assert resolve_artifact_source("hf://mikaelkanzaki/tech3-v3-pt-br") == (
        "mikaelkanzaki/tech3-v3-pt-br"
    )


def test_from_artifact_loads_lora_adapter_on_unsloth_4bit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded: dict[str, object] = {}
    base_model = FakeBaseModel()
    _install_runtime_fakes(monkeypatch, base_model=base_model, loaded=loaded)

    client = HuggingFaceLlmClient.from_artifact(pt_br_artifact(), GenerationSettings())

    assert isinstance(client, HuggingFaceLlmClient)
    base = cast(dict[str, object], loaded["base"])
    assert base["name"] == "unsloth/Qwen3-4B-Instruct-2507-unsloth-bnb-4bit"
    assert base["revision"] == "7744afa8566e264af1a92a806d8d9aae00cc7c78"
    base_kwargs = cast(dict[str, object], base["kwargs"])
    assert base_kwargs["device_map"] == "auto"
    assert "quantization_config" in base_kwargs
    assert loaded["bnb"] == {
        "load_in_4bit": True,
        "bnb_4bit_quant_type": "nf4",
        "bnb_4bit_use_double_quant": True,
        "bnb_4bit_compute_dtype": "bf16",
    }
    assert loaded["adapter"] == {
        "source": "mikaelkanzaki/tech3-v3-pt-br",
        "revision": "87564cac62fe90c11b23cd3d2f2124e3d8f10118",
        "base": base_model,
    }
    assert FakeTokenizer.loaded == (
        "unsloth/Qwen3-4B-Instruct-2507-unsloth-bnb-4bit",
        "7744afa8566e264af1a92a806d8d9aae00cc7c78",
    )
    assert base_model.eval_called is True


def test_generate_uses_temperature_and_repetition_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = FakeBaseModel()
    tokenizer = FakeTokenizer()
    tokenizer.pad_token_id = 0
    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(inference_mode=contextlib.nullcontext),
    )

    client = HuggingFaceLlmClient(
        model=model,
        tokenizer=tokenizer,
        settings=GenerationSettings(max_new_tokens=512, temperature=0.3),
    )
    answer = client.generate(
        system_prompt="Responda exclusivamente em português.",
        user_prompt="O que é estresse?",
    )

    assert "estresse" in answer.casefold()
    assert model.generate_kwargs["max_new_tokens"] == 512
    assert model.generate_kwargs["do_sample"] is True
    assert model.generate_kwargs["temperature"] == 0.3
    assert model.generate_kwargs["repetition_penalty"] == 1.1
    assert model.generate_kwargs["no_repeat_ngram_size"] == 4


def test_from_artifact_requires_runtime_extras(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    original_import = builtins.__import__

    def fake_import(
        name: str,
        globals: Mapping[str, object] | None = None,
        locals: Mapping[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> Any:
        if name in {"torch", "transformers"}:
            raise ImportError(name)
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ModelRuntimeError, match="Extras de runtime ausentes"):
        HuggingFaceLlmClient.from_artifact(pt_br_artifact(), GenerationSettings())
