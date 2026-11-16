from __future__ import annotations

from types import SimpleNamespace

import pytest

from tech_ai.errors import ConfigurationError, LanguageAnalysisError
from tech_ai.integrations.language.azure import AzureLanguageAnalyzer, _azure_types


def test_missing_sdk_has_install_instruction(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(_name: str) -> None:
        raise ImportError("missing")

    monkeypatch.setattr(
        "tech_ai.integrations.language.azure.importlib.import_module",
        missing,
    )
    with pytest.raises(ConfigurationError, match="uv sync --extra azure"):
        _azure_types()


@pytest.mark.parametrize("text", ["", "   ", "texto muito longo"])
def test_analyzer_rejects_empty_or_oversized_text(text: str) -> None:
    analyzer = AzureLanguageAnalyzer(
        key="secret",
        endpoint="https://language.example.azure.com/",
        max_characters=5,
    )
    with pytest.raises(LanguageAnalysisError):
        analyzer.analyze(text)


def test_analyzer_normalizes_azure_results(monkeypatch: pytest.MonkeyPatch) -> None:
    sentiment = SimpleNamespace(
        is_error=False,
        sentiment="mixed",
        confidence_scores=SimpleNamespace(positive=0.45, neutral=0.1, negative=0.45),
    )
    phrases = SimpleNamespace(
        is_error=False,
        key_phrases=[" cansaço ", "exercício", ""],
    )

    class FakeClient:
        def __init__(self, **_configuration: object) -> None:
            pass

        def analyze_sentiment(self, *_args: object, **_kwargs: object) -> list[object]:
            return [sentiment]

        def extract_key_phrases(self, *_args: object, **_kwargs: object) -> list[object]:
            return [phrases]

    monkeypatch.setattr(
        "tech_ai.integrations.language.azure._azure_types",
        lambda: (FakeClient, lambda key: key),
    )
    analyzer = AzureLanguageAnalyzer(
        key="secret",
        endpoint="https://language.example.azure.com/",
    )

    result = analyzer.analyze("  relato   fictício ")

    assert result.sentiment == "mixed"
    assert result.confidence.positive == 0.45
    assert result.key_phrases == ("cansaço", "exercício")
