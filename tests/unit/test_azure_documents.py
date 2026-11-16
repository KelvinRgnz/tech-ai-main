from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from tech_ai.errors import ConfigurationError, DocumentOcrError
from tech_ai.integrations.documents.azure import AzureDocumentReader, _azure_types


def test_missing_sdk_has_install_instruction(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(_name: str) -> None:
        raise ImportError("missing")

    monkeypatch.setattr(
        "tech_ai.integrations.documents.azure.importlib.import_module",
        missing,
    )
    with pytest.raises(ConfigurationError, match="uv sync --extra azure"):
        _azure_types()


def test_reader_enforces_f0_limits_and_supported_formats(tmp_path: Path) -> None:
    reader = AzureDocumentReader(
        key="secret",
        endpoint="https://document.example.azure.com/",
        max_bytes=5,
    )
    oversized = tmp_path / "large.pdf"
    oversized.write_bytes(b"123456")

    with pytest.raises(DocumentOcrError, match="4 MB"):
        reader.read(oversized, content_type="application/pdf")
    with pytest.raises(DocumentOcrError, match="Formato"):
        reader.read(oversized, content_type="text/plain")
    with pytest.raises(DocumentOcrError, match="indisponível"):
        reader.read(tmp_path / "missing.pdf", content_type="application/pdf")


def test_reader_normalizes_text_and_pages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    document = tmp_path / "prescricao.pdf"
    document.write_bytes(b"%PDF-test")
    result = SimpleNamespace(
        content="Paciente fictício\nDipirona 500 mg",
        pages=[
            SimpleNamespace(
                page_number=1,
                lines=[
                    SimpleNamespace(content="Paciente fictício"),
                    SimpleNamespace(content="Dipirona 500 mg"),
                ],
            )
        ],
    )
    calls: list[tuple[str, dict[str, object]]] = []

    class FakePoller:
        def result(self) -> object:
            return result

    class FakeClient:
        def __init__(self, **_configuration: object) -> None:
            pass

        def begin_analyze_document(
            self,
            model_id: str,
            **options: object,
        ) -> FakePoller:
            calls.append((model_id, options))
            return FakePoller()

    monkeypatch.setattr(
        "tech_ai.integrations.documents.azure._azure_types",
        lambda: (FakeClient, lambda key: key),
    )
    reader = AzureDocumentReader(
        key="secret",
        endpoint="https://document.example.azure.com/",
    )

    extracted = reader.read(document, content_type="application/pdf")

    assert extracted.text == "Paciente fictício\nDipirona 500 mg"
    assert extracted.pages[0].text == "Paciente fictício\nDipirona 500 mg"
    assert calls[0][0] == "prebuilt-read"
    assert calls[0][1]["pages"] == "1-2"
    assert calls[0][1]["locale"] == "pt-BR"


def test_reader_rejects_empty_ocr_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    document = tmp_path / "blank.png"
    document.write_bytes(b"png")

    class FakePoller:
        def result(self) -> object:
            return SimpleNamespace(content="", pages=[])

    class FakeClient:
        def __init__(self, **_configuration: object) -> None:
            pass

        def begin_analyze_document(self, *_args: object, **_options: object) -> FakePoller:
            return FakePoller()

    monkeypatch.setattr(
        "tech_ai.integrations.documents.azure._azure_types",
        lambda: (FakeClient, lambda key: key),
    )
    reader = AzureDocumentReader(
        key="secret",
        endpoint="https://document.example.azure.com/",
    )

    with pytest.raises(DocumentOcrError, match="Nenhum texto"):
        reader.read(document, content_type="image/png")
