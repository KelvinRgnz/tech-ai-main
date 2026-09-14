"""Tradução EN↔PT via MyMemory, sem chave OpenAI nem runtime de LLM."""

from __future__ import annotations

import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from tech_ai.errors import TranslationError

_API_URL = "https://api.mymemory.translated.net/get"
_MAX_CHUNK_CHARACTERS = 450
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


class MyMemoryTranslationClient:
    """Cliente HTTP estável, com cache em memória e recorte por sentença."""

    def __init__(self, *, timeout_seconds: float = 20.0) -> None:
        self._timeout_seconds = timeout_seconds
        self._cache: dict[tuple[str, str, str], str] = {}

    def translate(self, text: str, *, source: str, target: str) -> str:
        stripped = text.strip()
        if not stripped or source == target:
            return stripped
        cache_key = (stripped, source, target)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        translated = " ".join(
            self._translate_chunk(chunk, source=source, target=target)
            for chunk in _chunks(stripped)
        ).strip()
        if not translated:
            raise TranslationError("O serviço de tradução retornou texto vazio.")
        self._cache[cache_key] = translated
        return translated

    def _translate_chunk(self, chunk: str, *, source: str, target: str) -> str:
        query = urlencode({"q": chunk, "langpair": f"{source}|{target}"})
        url = f"{_API_URL}?{query}"
        if not url.startswith("https://"):
            raise TranslationError("A URL de tradução deve usar HTTPS.")
        request = Request(  # noqa: S310
            url,
            headers={"User-Agent": "tech-ai/0.1"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:  # noqa: S310
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as error:
            raise TranslationError("Não foi possível traduzir o texto recuperado.") from error
        translated = _read_translated_text(payload)
        if translated is None:
            raise TranslationError("O serviço de tradução retornou uma resposta inválida.")
        return translated


def _chunks(text: str) -> list[str]:
    if len(text) <= _MAX_CHUNK_CHARACTERS:
        return [text]
    pieces: list[str] = []
    current = ""
    for sentence in _SENTENCE_SPLIT.split(text):
        candidate = sentence if not current else f"{current} {sentence}"
        if len(candidate) <= _MAX_CHUNK_CHARACTERS:
            current = candidate
            continue
        if current:
            pieces.append(current)
        if len(sentence) <= _MAX_CHUNK_CHARACTERS:
            current = sentence
        else:
            pieces.extend(
                sentence[index : index + _MAX_CHUNK_CHARACTERS]
                for index in range(0, len(sentence), _MAX_CHUNK_CHARACTERS)
            )
            current = ""
    if current:
        pieces.append(current)
    return pieces or [text]


def _read_translated_text(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get("responseData")
    if not isinstance(data, dict):
        return None
    translated = data.get("translatedText")
    if not isinstance(translated, str):
        return None
    cleaned = translated.strip()
    return cleaned or None
