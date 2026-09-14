"""Aplicação HTTP que expõe consulta, resposta e a interface do assistente."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from tech_ai.config.dependencies import (
    build_auth_service,
    build_knowledge_retrieval_service,
    build_medical_assistant_service,
)
from tech_ai.config.settings import AuthSettings, Settings
from tech_ai.errors import (
    AssistantError,
    AuthenticationError,
    ConfigurationError,
    EmbeddingError,
    KnowledgeRetrievalError,
    KnowledgeStoreError,
    ModelArtifactReadError,
    ModelArtifactValidationError,
    ModelRuntimeError,
    TranslationError,
)
from tech_ai.integrations.translation.documents import excerpt_from_knowledge_text
from tech_ai.models.assistant import ACADEMIC_DISCLAIMER, AssistantQuery
from tech_ai.models.auth import AuthUser
from tech_ai.models.knowledge import KnowledgeCitation
from tech_ai.services.auth_service import AuthService
from tech_ai.services.knowledge_retrieval_service import KnowledgeRetrievalService
from tech_ai.services.medical_assistant_service import MedicalAssistantService

_WEB_DIR = Path(__file__).resolve().parent / "web"
_NO_EVIDENCE_ANSWER = (
    "Não encontrei evidências suficientemente relacionadas na base de conhecimento "
    "para responder com segurança."
)
_RUNTIME_UNAVAILABLE = (
    "O runtime do modelo não está instalado. Use a consulta de evidências ou "
    "instale com: uv sync --dev --extra runtime"
)


class ConsultRequest(BaseModel):
    """Pergunta enviada pela interface do assistente."""

    question: str
    limit: int | None = Field(default=None, gt=0, le=20)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("A pergunta não pode ser vazia.")
        return stripped


class LoginRequest(BaseModel):
    """Credenciais enviadas pela tela de acesso."""

    username: str
    password: str

    @field_validator("username", "password")
    @classmethod
    def credentials_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Informe usuário e senha.")
        return stripped


def _bearer_token(header: str | None) -> str | None:
    if header is None:
        return None
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def _session_cookie(response: Response, *, token: str, settings: AuthSettings) -> None:
    response.set_cookie(
        settings.cookie_name,
        token,
        httponly=True,
        samesite="lax",
        max_age=settings.token_ttl_seconds,
        path="/",
    )


def create_app(
    *,
    settings: Settings | None = None,
    auth_settings: AuthSettings | None = None,
    retrieval_service: KnowledgeRetrievalService | None = None,
    assistant_service: MedicalAssistantService | None = None,
    auth_service: AuthService | None = None,
) -> FastAPI:
    """Monta a API e a interface estática sem conectar no import."""

    runtime_settings = settings or Settings.from_environment()
    runtime_auth_settings = auth_settings or AuthSettings.from_environment()
    retrieval_holder: dict[str, KnowledgeRetrievalService] = {}
    assistant_holder: dict[str, MedicalAssistantService] = {}
    auth = auth_service or build_auth_service(runtime_auth_settings)
    if retrieval_service is not None:
        retrieval_holder["service"] = retrieval_service
    if assistant_service is not None:
        assistant_holder["service"] = assistant_service

    def get_retrieval() -> KnowledgeRetrievalService:
        cached = retrieval_holder.get("service")
        if cached is not None:
            return cached
        built = build_knowledge_retrieval_service(runtime_settings)
        retrieval_holder["service"] = built
        return built

    def get_assistant() -> MedicalAssistantService:
        cached = assistant_holder.get("service")
        if cached is not None:
            return cached
        try:
            built = build_medical_assistant_service(runtime_settings)
        except ImportError as error:
            raise ModelRuntimeError(_RUNTIME_UNAVAILABLE) from error
        assistant_holder["service"] = built
        return built

    def current_user(request: Request) -> AuthUser:
        token = request.cookies.get(runtime_auth_settings.cookie_name) or _bearer_token(
            request.headers.get("authorization")
        )
        try:
            return auth.read_session(token)
        except AuthenticationError as error:
            raise HTTPException(status_code=401, detail=str(error)) from error

    app = FastAPI(
        title="Tech AI",
        summary="Assistente médico acadêmico do Tech Challenge.",
    )

    @app.middleware("http")
    async def disable_ui_cache(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "disclaimer": ACADEMIC_DISCLAIMER}

    @app.post("/api/login")
    def login(body: LoginRequest, response: Response) -> dict[str, str | int]:
        try:
            session = auth.login(body.username, body.password)
        except AuthenticationError as error:
            raise HTTPException(status_code=401, detail=str(error)) from error
        _session_cookie(response, token=session.value, settings=runtime_auth_settings)
        return {
            "username": session.username,
            "expires_at": session.expires_at,
        }

    @app.post("/api/logout")
    def logout(request: Request, response: Response) -> dict[str, str]:
        token = request.cookies.get(runtime_auth_settings.cookie_name) or _bearer_token(
            request.headers.get("authorization")
        )
        auth.logout(token)
        response.delete_cookie(runtime_auth_settings.cookie_name, path="/")
        return {"status": "ok"}

    @app.get("/api/me")
    def me(user: AuthUser = Depends(current_user)) -> dict[str, str]:
        return {"username": user.username}

    @app.post("/api/consult")
    def consult(
        body: ConsultRequest,
        user: AuthUser = Depends(current_user),
    ) -> dict[str, object]:
        del user
        try:
            results = get_retrieval().search(
                body.question,
                limit=body.limit or runtime_settings.retrieval_limit,
            )
        except KnowledgeRetrievalError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except (
            ConfigurationError,
            EmbeddingError,
            KnowledgeStoreError,
            TranslationError,
        ) as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

        citations = [
            KnowledgeCitation.from_result(result, number=number).as_dict()
            for number, result in enumerate(results, start=1)
        ]
        excerpt = excerpt_from_knowledge_text(results[0].text) if results else None
        return {
            "question": body.question,
            "mode": "evidence",
            "answer": excerpt or _NO_EVIDENCE_ANSWER,
            "grounded": bool(results),
            "sources": [result.as_dict() for result in results],
            "citations": citations,
            "disclaimer": ACADEMIC_DISCLAIMER,
        }

    @app.post("/api/ask")
    def ask(
        body: ConsultRequest,
        user: AuthUser = Depends(current_user),
    ) -> dict[str, object]:
        del user
        try:
            answer = get_assistant().answer(
                AssistantQuery(question=body.question),
                limit=body.limit or runtime_settings.retrieval_limit,
            )
        except (
            AssistantError,
            KnowledgeRetrievalError,
        ) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except (
            ConfigurationError,
            EmbeddingError,
            KnowledgeStoreError,
            ModelArtifactReadError,
            ModelArtifactValidationError,
            ModelRuntimeError,
            TranslationError,
        ) as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        payload = answer.as_dict()
        payload["mode"] = "assistant"
        return payload

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(_WEB_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=_WEB_DIR), name="static")
    return app


def build_default_app() -> FastAPI:
    """Entrada usada pelo Uvicorn quando o módulo é carregado direto."""

    from tech_ai.config.settings import load_project_environment

    load_project_environment()
    return create_app()
