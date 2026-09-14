"""Runtime Transformers para o modelo e o adaptador publicados no Hugging Face."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from tech_ai.config.settings import GenerationSettings
from tech_ai.errors import ModelRuntimeError
from tech_ai.models.model_artifact import ModelArtifact


def resolve_artifact_source(artifact_uri: str) -> str:
    """Converte ``hf://owner/repo`` em uma referência aceita pelo Hub."""

    prefix = "hf://"
    if artifact_uri.startswith(prefix):
        return artifact_uri[len(prefix) :]
    return str(Path(artifact_uri).expanduser())


def _is_bitsandbytes_model(model_id: str) -> bool:
    lowered = model_id.casefold()
    return "bnb-4bit" in lowered or "4bit" in lowered or "bitsandbytes" in lowered


def _model_load_kwargs(base_model_id: str, torch_module: Any) -> dict[str, Any]:
    has_cuda = bool(torch_module.cuda.is_available())
    kwargs: dict[str, Any] = {}
    if has_cuda:
        kwargs["device_map"] = "auto"
    if _is_bitsandbytes_model(base_model_id):
        from transformers import BitsAndBytesConfig

        compute_dtype = torch_module.bfloat16 if has_cuda else torch_module.float32
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=compute_dtype,
        )
        kwargs.setdefault("device_map", "auto")
    else:
        kwargs["dtype"] = torch_module.bfloat16 if has_cuda else torch_module.float32
    return kwargs


def _apply_chat_template(tokenizer: Any, messages: list[dict[str, str]]) -> str:
    try:
        return cast(
            str,
            tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            ),
        )
    except TypeError:
        return cast(
            str,
            tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            ),
        )


class HuggingFaceLlmClient:
    """Mantém o modelo carregado e oferece uma fronteira pequena de geração."""

    def __init__(
        self,
        *,
        model: Any,
        tokenizer: Any,
        settings: GenerationSettings,
    ) -> None:
        self._model = model
        self._tokenizer = tokenizer
        self._settings = settings

    @classmethod
    def from_artifact(
        cls,
        artifact: ModelArtifact,
        settings: GenerationSettings,
    ) -> HuggingFaceLlmClient:
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as error:
            raise ModelRuntimeError(
                "Extras de runtime ausentes. Instale com 'uv sync --extra runtime'."
            ) from error

        source = resolve_artifact_source(artifact.artifact_uri)
        load_kwargs = _model_load_kwargs(artifact.base_model_id, torch)

        try:
            tokenizer = AutoTokenizer.from_pretrained(
                artifact.tokenizer_id,
                revision=artifact.tokenizer_revision,
            )
            if tokenizer.pad_token_id is None:
                tokenizer.pad_token_id = tokenizer.eos_token_id

            if artifact.artifact_type == "merged_transformers":
                model = AutoModelForCausalLM.from_pretrained(
                    source,
                    revision=artifact.artifact_revision,
                    **load_kwargs,
                )
            else:
                from peft import PeftModel

                base_model = AutoModelForCausalLM.from_pretrained(
                    artifact.base_model_id,
                    revision=artifact.base_model_revision,
                    **load_kwargs,
                )
                model = PeftModel.from_pretrained(
                    base_model,
                    source,
                    revision=artifact.artifact_revision,
                )
            model.eval()
        except Exception as error:
            raise ModelRuntimeError(
                f"Não foi possível carregar o artefato {artifact.artifact_id!r}: {error}"
            ) from error
        return cls(model=model, tokenizer=tokenizer, settings=settings)

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        try:
            import torch

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            prompt = _apply_chat_template(self._tokenizer, messages)
            inputs = self._tokenizer(prompt, return_tensors="pt")
            device = next(self._model.parameters()).device
            inputs = {name: value.to(device) for name, value in inputs.items()}
            input_length = inputs["input_ids"].shape[-1]
            generate_kwargs: dict[str, Any] = {
                "max_new_tokens": self._settings.max_new_tokens,
                "do_sample": True,
                "temperature": self._settings.temperature,
                "repetition_penalty": self._settings.repetition_penalty,
                "no_repeat_ngram_size": self._settings.no_repeat_ngram_size,
                "pad_token_id": self._tokenizer.pad_token_id,
                "eos_token_id": self._tokenizer.eos_token_id,
            }
            with torch.inference_mode():
                output = self._model.generate(**inputs, **generate_kwargs)
            generated_tokens = output[0][input_length:]
            answer = cast(
                str,
                self._tokenizer.decode(generated_tokens, skip_special_tokens=True),
            ).strip()
        except Exception as error:
            raise ModelRuntimeError("A inferência do modelo falhou.") from error
        if not answer:
            raise ModelRuntimeError("O modelo retornou uma resposta vazia.")
        return answer
