from __future__ import annotations

from typing import cast

import pytest
from fastapi.testclient import TestClient

from tech_ai.api.app import build_default_app, create_app
from tech_ai.config.settings import Settings
from tech_ai.errors import (
    AssistantError,
    KnowledgeRetrievalError,
    KnowledgeStoreError,
    ModelRuntimeError,
)
from tech_ai.models.assistant import ACADEMIC_DISCLAIMER, AssistantAnswer
from tech_ai.models.knowledge import KnowledgeCitation, KnowledgeSearchResult
from tech_ai.services.knowledge_retrieval_service import KnowledgeRetrievalService
from tech_ai.services.medical_assistant_service import MedicalAssistantService


class FakeRetrievalService:
    def __init__(self, results: tuple[KnowledgeSearchResult, ...] | None = None) -> None:
        self.results = results or (
            KnowledgeSearchResult(
                record_id="rec-1",
                text="Tópico médico: Diabetes\nPergunta: Sintomas?\nResposta: Sede e cansaço.",
                metadata={"focus": "Diabetes", "source_url": "https://example.org/diabetes"},
                distance=0.21,
            ),
        )
        self.queries: list[tuple[str, int]] = []
        self.error: Exception | None = None

    def search(self, query: str, *, limit: int) -> tuple[KnowledgeSearchResult, ...]:
        self.queries.append((query, limit))
        if self.error is not None:
            raise self.error
        return self.results


class FakeAssistantService:
    def __init__(self) -> None:
        self.questions: list[str] = []
        self.error: Exception | None = None

    def answer(self, query: object, *, limit: int | None = None) -> AssistantAnswer:
        del limit
        question = getattr(query, "question", "")
        self.questions.append(question)
        if self.error is not None:
            raise self.error
        return AssistantAnswer(
            question=question,
            answer="Sedimento e sede excessiva podem ocorrer. [1]",
            model_id="tech3-v3",
            sources=(
                KnowledgeCitation(
                    number=1,
                    record_id="rec-1",
                    distance=0.21,
                    focus="Diabetes",
                    source_url="https://example.org/diabetes",
                ),
            ),
            grounded=True,
        )


def _client(
    retrieval: FakeRetrievalService | None = None,
    assistant: FakeAssistantService | None = None,
) -> TestClient:
    app = create_app(
        settings=Settings(),
        retrieval_service=cast(KnowledgeRetrievalService, retrieval or FakeRetrievalService()),
        assistant_service=cast(MedicalAssistantService, assistant) if assistant else None,
    )
    return TestClient(app)


def test_health_and_interface_are_available() -> None:
    client = _client()

    health = client.get("/api/health")
    page = client.get("/")
    css = client.get("/static/styles.css")

    assert health.status_code == 200
    assert health.json()["disclaimer"] == ACADEMIC_DISCLAIMER
    assert page.status_code == 200
    assert "Assistente médico acadêmico" in page.text
    assert "Quais são os sintomas da diabetes?" in page.text
    assert "Prefira perguntas em inglês" not in page.text
    assert css.status_code == 200
    assert "teal" in css.text or "--teal" in css.text


def test_consult_returns_sources_citations_and_disclaimer() -> None:
    retrieval = FakeRetrievalService()
    client = _client(retrieval)

    response = client.post("/api/consult", json={"question": "  diabetes  ", "limit": 3})

    assert response.status_code == 200
    payload = response.json()
    assert retrieval.queries == [("diabetes", 3)]
    assert payload["mode"] == "evidence"
    assert payload["answer"] == "Sede e cansaço."
    assert payload["grounded"] is True
    assert payload["disclaimer"] == ACADEMIC_DISCLAIMER
    assert payload["sources"][0]["record_id"] == "rec-1"
    assert payload["sources"][0]["chunk_id"] == "rec-1"
    assert payload["citations"][0]["citation"] == "[1]"
    assert payload["citations"][0]["focus"] == "Diabetes"
    assert payload["citations"][0]["source_url"] == "https://example.org/diabetes"
    assert payload["citations"][0]["distance"] == 0.21


def test_consult_rejects_blank_question_and_maps_service_errors() -> None:
    retrieval = FakeRetrievalService()
    client = _client(retrieval)

    blank = client.post("/api/consult", json={"question": "   "})
    retrieval.error = KnowledgeRetrievalError("consulta vazia")
    invalid = client.post("/api/consult", json={"question": "asma"})
    retrieval.error = KnowledgeStoreError("chroma offline")
    offline = client.post("/api/consult", json={"question": "asma"})

    assert blank.status_code == 422
    assert invalid.status_code == 400
    assert invalid.json()["detail"] == "consulta vazia"
    assert offline.status_code == 503


def test_ask_returns_grounded_answer() -> None:
    assistant = FakeAssistantService()
    client = _client(assistant=assistant)

    response = client.post("/api/ask", json={"question": "What is diabetes?"})

    assert response.status_code == 200
    payload = response.json()
    assert assistant.questions == ["What is diabetes?"]
    assert payload["mode"] == "assistant"
    assert payload["grounded"] is True
    assert payload["answer"].endswith("[1]")
    assert payload["disclaimer"] == ACADEMIC_DISCLAIMER


def test_consult_builds_retrieval_service_lazily(monkeypatch: pytest.MonkeyPatch) -> None:
    retrieval = FakeRetrievalService()
    monkeypatch.setattr(
        "tech_ai.api.app.build_knowledge_retrieval_service",
        lambda _settings: retrieval,
    )
    client = TestClient(create_app(settings=Settings()))

    response = client.post("/api/consult", json={"question": "diabetes"})

    assert response.status_code == 200
    assert retrieval.queries == [("diabetes", 4)]


def test_ask_builds_assistant_and_maps_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    assistant = FakeAssistantService()
    monkeypatch.setattr(
        "tech_ai.api.app.build_medical_assistant_service",
        lambda _settings: assistant,
    )
    built = TestClient(create_app(settings=Settings()))
    ok = built.post("/api/ask", json={"question": "What is diabetes?"})

    def fail(_settings: Settings) -> None:
        raise ImportError("torch")

    monkeypatch.setattr(
        "tech_ai.api.app.build_medical_assistant_service",
        fail,
    )
    missing = TestClient(create_app(settings=Settings()))
    unavailable = missing.post("/api/ask", json={"question": "What is diabetes?"})

    assert ok.status_code == 200
    assert unavailable.status_code == 503
    assert "runtime" in unavailable.json()["detail"]


def test_ask_maps_missing_runtime() -> None:
    assistant = FakeAssistantService()
    assistant.error = ModelRuntimeError("runtime ausente")
    client = _client(assistant=assistant)

    response = client.post("/api/ask", json={"question": "What is diabetes?"})

    assert response.status_code == 503
    assert response.json()["detail"] == "runtime ausente"


def test_ask_maps_invalid_question() -> None:
    assistant = FakeAssistantService()
    assistant.error = AssistantError("A pergunta não pode ser vazia.")
    client = _client(assistant=assistant)

    response = client.post("/api/ask", json={"question": "ok"})

    assert response.status_code == 400


def test_build_default_app_exposes_health() -> None:
    client = TestClient(build_default_app())

    assert client.get("/api/health").json()["status"] == "ok"
