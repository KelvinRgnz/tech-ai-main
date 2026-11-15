from __future__ import annotations

from typing import cast

import pytest
from fastapi.testclient import TestClient

from tech_ai.api.app import build_default_app, create_app
from tech_ai.config.settings import AuthSettings, Settings
from tech_ai.errors import (
    AssistantError,
    KnowledgeRetrievalError,
    KnowledgeStoreError,
    ModelRuntimeError,
)
from tech_ai.integrations.auth.password import hash_password
from tech_ai.models.assistant import ACADEMIC_DISCLAIMER, AssistantAnswer
from tech_ai.models.knowledge import KnowledgeCitation, KnowledgeSearchResult
from tech_ai.services.auth_service import AuthService
from tech_ai.services.knowledge_retrieval_service import KnowledgeRetrievalService
from tech_ai.services.medical_assistant_service import MedicalAssistantService

_TEST_USERNAME = "academic"
_TEST_PASSWORD = "academic123"
_TEST_SECRET = "test-secret-16chars"
_TEST_PASSWORD_HASH = hash_password(_TEST_PASSWORD)


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


def _auth_settings() -> AuthSettings:
    return AuthSettings(
        secret=_TEST_SECRET,
        users=((_TEST_USERNAME, _TEST_PASSWORD_HASH),),
        token_ttl_seconds=3600,
    )


def _auth_service() -> AuthService:
    return AuthService(
        {_TEST_USERNAME: _TEST_PASSWORD_HASH},
        secret=_TEST_SECRET,
        token_ttl_seconds=3600,
    )


def _login(client: TestClient) -> TestClient:
    response = client.post(
        "/api/login",
        json={"username": _TEST_USERNAME, "password": _TEST_PASSWORD},
    )
    assert response.status_code == 200
    return client


def _client(
    retrieval: FakeRetrievalService | None = None,
    assistant: FakeAssistantService | None = None,
    *,
    authenticate: bool = True,
) -> TestClient:
    app = create_app(
        settings=Settings(),
        auth_settings=_auth_settings(),
        auth_service=_auth_service(),
        retrieval_service=cast(KnowledgeRetrievalService, retrieval or FakeRetrievalService()),
        assistant_service=cast(MedicalAssistantService, assistant) if assistant else None,
    )
    client = TestClient(app)
    if authenticate:
        return _login(client)
    return client


def _lazy_client() -> TestClient:
    return _login(
        TestClient(
            create_app(
                settings=Settings(),
                auth_settings=_auth_settings(),
                auth_service=_auth_service(),
            )
        )
    )


def test_health_and_interface_are_available() -> None:
    client = _client(authenticate=False)

    health = client.get("/api/health")
    page = client.get("/")
    css = client.get("/static/styles.css")

    assert health.status_code == 200
    assert health.json()["disclaimer"] == ACADEMIC_DISCLAIMER
    assert page.status_code == 200
    assert "Assistente médico acadêmico" in page.text
    assert "Entrar no assistente" in page.text
    assert 'id="login-form"' in page.text
    assert "is-locked" in page.text
    assert "app.js?v=document1" in page.text
    assert 'id="patient-select"' in page.text
    assert 'id="patient-form"' in page.text
    assert 'id="attachment-button"' in page.text
    assert 'id="attachment-input"' in page.text
    assert page.headers.get("cache-control") == "no-store"
    assert "Quais são os sintomas da diabetes?" in page.text
    assert "Prefira perguntas em inglês" not in page.text
    assert css.status_code == 200
    assert "teal" in css.text or "--teal" in css.text


def test_capabilities_report_optional_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(authenticate=False)
    monkeypatch.setattr("tech_ai.api.app.importlib.util.find_spec", lambda module: object())
    assert client.get("/api/capabilities").json() == {"assistant_runtime": True}
    monkeypatch.setattr("tech_ai.api.app.importlib.util.find_spec", lambda module: None)
    assert client.get("/api/capabilities").json() == {"assistant_runtime": False}


def test_vague_question_starts_interview_without_retrieval() -> None:
    retrieval = FakeRetrievalService()
    client = _client(retrieval)
    response = client.post(
        "/api/consult", json={"question": "Estou tendo um problema, consegue me ajudar?"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "interview"
    assert payload["grounded"] is False
    assert "principal sintoma" in payload["answer"]
    assert retrieval.queries == []


def test_vague_question_does_not_load_assistant_model() -> None:
    assistant = FakeAssistantService()
    client = _client(assistant=assistant)
    response = client.post("/api/ask", json={"question": "Pode me ajudar?"})
    assert response.status_code == 200
    assert response.json()["mode"] == "interview"
    assert assistant.questions == []


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
    client = _lazy_client()

    response = client.post("/api/consult", json={"question": "diabetes"})

    assert response.status_code == 200
    assert retrieval.queries == [("diabetes", 4)]


def test_ask_builds_assistant_and_maps_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    assistant = FakeAssistantService()
    monkeypatch.setattr(
        "tech_ai.api.app.build_medical_assistant_service",
        lambda _settings: assistant,
    )
    built = _lazy_client()
    ok = built.post("/api/ask", json={"question": "What is diabetes?"})

    def fail(_settings: Settings) -> None:
        raise ImportError("torch")

    monkeypatch.setattr(
        "tech_ai.api.app.build_medical_assistant_service",
        fail,
    )
    missing = _lazy_client()
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


def test_build_default_app_exposes_health(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TECH_AI_AUTH_SECRET", _TEST_SECRET)
    monkeypatch.setenv("TECH_AI_AUTH_USERS", f"{_TEST_USERNAME}:{_TEST_PASSWORD}")
    client = TestClient(build_default_app())

    assert client.get("/api/health").json()["status"] == "ok"


def test_consult_and_me_require_authentication() -> None:
    client = _client(authenticate=False)

    consult = client.post("/api/consult", json={"question": "diabetes"})
    me = client.get("/api/me")

    assert consult.status_code == 401
    assert me.status_code == 401
    assert consult.json()["detail"] == "Autenticação obrigatória."


def test_login_sets_httponly_cookie_and_exposes_current_user() -> None:
    client = _client(authenticate=False)

    response = client.post(
        "/api/login",
        json={"username": "Academic", "password": _TEST_PASSWORD},
    )

    assert response.status_code == 200
    assert response.json()["username"] == _TEST_USERNAME
    assert "httponly" in response.headers["set-cookie"].lower()
    assert client.get("/api/me").json() == {"username": _TEST_USERNAME}


def test_login_rejects_invalid_credentials() -> None:
    client = _client(authenticate=False)

    response = client.post(
        "/api/login",
        json={"username": _TEST_USERNAME, "password": "senha-errada"},
    )
    blank = client.post(
        "/api/login",
        json={"username": "  ", "password": _TEST_PASSWORD},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Credenciais inválidas."
    assert blank.status_code == 422


def test_logout_revokes_session() -> None:
    retrieval = FakeRetrievalService()
    app = create_app(
        settings=Settings(),
        auth_settings=_auth_settings(),
        auth_service=_auth_service(),
        retrieval_service=cast(KnowledgeRetrievalService, retrieval),
    )
    client = _login(TestClient(app))
    token = client.cookies.get("tech_ai_session")
    assert token is not None

    logout = client.post("/api/logout")
    with_cookie = client.post("/api/consult", json={"question": "diabetes"})
    with_revoked_bearer = TestClient(app).post(
        "/api/consult",
        json={"question": "diabetes"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert logout.status_code == 200
    assert with_cookie.status_code == 401
    assert with_revoked_bearer.status_code == 401
    assert with_revoked_bearer.json()["detail"] == "Sessão encerrada."


def test_consult_accepts_bearer_token() -> None:
    retrieval = FakeRetrievalService()
    app = create_app(
        settings=Settings(),
        auth_settings=_auth_settings(),
        auth_service=_auth_service(),
        retrieval_service=cast(KnowledgeRetrievalService, retrieval),
    )
    login_client = _login(TestClient(app))
    token = login_client.cookies.get("tech_ai_session")
    assert token is not None

    response = TestClient(app).post(
        "/api/consult",
        json={"question": "diabetes"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert retrieval.queries == [("diabetes", 4)]
