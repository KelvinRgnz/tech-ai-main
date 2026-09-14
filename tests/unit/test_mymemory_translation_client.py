from __future__ import annotations

import json
from typing import Any

import pytest

from tech_ai.errors import TranslationError
from tech_ai.integrations.translation.mymemory import MyMemoryTranslationClient


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def test_mymemory_translates_and_caches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_urlopen(request: object, timeout: float = 0) -> FakeResponse:
        del request, timeout
        nonlocal calls
        calls += 1
        return FakeResponse({"responseData": {"translatedText": "A diabetes é grave."}})

    monkeypatch.setattr(
        "tech_ai.integrations.translation.mymemory.urlopen",
        fake_urlopen,
    )
    client = MyMemoryTranslationClient()

    first = client.translate("Diabetes is serious.", source="en", target="pt")
    second = client.translate("Diabetes is serious.", source="en", target="pt")

    assert first == "A diabetes é grave."
    assert second == first
    assert calls == 1


def test_mymemory_rejects_invalid_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "tech_ai.integrations.translation.mymemory.urlopen",
        lambda *_args, **_kwargs: FakeResponse({"responseData": {}}),
    )
    client = MyMemoryTranslationClient()

    with pytest.raises(TranslationError, match="inválida"):
        client.translate("Hello world.", source="en", target="pt")


def test_mymemory_wraps_http_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args: Any, **_kwargs: Any) -> None:
        raise TimeoutError("offline")

    monkeypatch.setattr("tech_ai.integrations.translation.mymemory.urlopen", fail)
    client = MyMemoryTranslationClient()

    with pytest.raises(TranslationError, match="Não foi possível traduzir"):
        client.translate("Hello world.", source="en", target="pt")


def test_mymemory_skips_blank_and_same_language() -> None:
    client = MyMemoryTranslationClient()

    assert client.translate("   ", source="en", target="pt") == ""
    assert client.translate("já em português", source="pt", target="pt") == "já em português"


def test_mymemory_splits_long_text(monkeypatch: pytest.MonkeyPatch) -> None:
    queries: list[str] = []

    def fake_urlopen(request: object, timeout: float = 0) -> FakeResponse:
        del timeout
        url = str(getattr(request, "full_url", request))
        queries.append(url)
        return FakeResponse({"responseData": {"translatedText": "ok"}})

    monkeypatch.setattr(
        "tech_ai.integrations.translation.mymemory.urlopen",
        fake_urlopen,
    )
    client = MyMemoryTranslationClient()
    long_text = "Stress is serious. " * 40

    translated = client.translate(long_text.strip(), source="en", target="pt")

    assert translated
    assert len(queries) >= 2
