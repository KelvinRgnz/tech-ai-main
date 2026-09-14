"""Composição explícita das dependências, equivalente ao ``@Configuration``."""

from __future__ import annotations

from tech_ai.config.settings import (
    AuthSettings,
    ChromaSettings,
    GenerationSettings,
    LocalEmbeddingSettings,
    Settings,
)
from tech_ai.integrations.chroma.knowledge_repository import ChromaKnowledgeRepository
from tech_ai.integrations.embeddings.local_onnx import LocalOnnxEmbeddingClient
from tech_ai.integrations.llm.huggingface import HuggingFaceLlmClient
from tech_ai.integrations.translation.mymemory import MyMemoryTranslationClient
from tech_ai.services.auth_service import AuthService
from tech_ai.services.knowledge_retrieval_service import KnowledgeRetrievalService
from tech_ai.services.medical_assistant_service import MedicalAssistantService
from tech_ai.services.model_artifact_service import inspect_model_artifact


def build_knowledge_retrieval_service(
    settings: Settings | None = None,
) -> KnowledgeRetrievalService:
    """Monta embeddings ONNX locais e o ChromaDB somente-leitura."""

    runtime_settings = settings or Settings.from_environment()
    embedding_client = LocalOnnxEmbeddingClient(LocalEmbeddingSettings.from_environment())
    repository = ChromaKnowledgeRepository(ChromaSettings.from_environment())
    return KnowledgeRetrievalService(
        embedding_client,
        repository,
        max_distance=runtime_settings.max_retrieval_distance,
        translator=MyMemoryTranslationClient(),
    )


def build_medical_assistant_service(settings: Settings) -> MedicalAssistantService:
    """Monta o caso de uso completo: ChromaDB, modelo publicado e RAG."""

    retrieval_service = build_knowledge_retrieval_service(settings)
    artifact = inspect_model_artifact(settings.model_manifest_path)
    llm_client = HuggingFaceLlmClient.from_artifact(
        artifact,
        GenerationSettings.from_environment(),
    )
    model_id = artifact.artifact_uri.removeprefix("hf://")
    return MedicalAssistantService(
        retrieval_service=retrieval_service,
        llm_client=llm_client,
        model_id=model_id,
        retrieval_limit=settings.retrieval_limit,
        max_source_characters=settings.max_source_characters,
        max_answer_characters=settings.max_answer_characters,
    )


def build_auth_service(settings: AuthSettings | None = None) -> AuthService:
    """Monta o serviço de login com usuários definidos no ambiente."""

    auth_settings = settings or AuthSettings.from_environment()
    return AuthService(
        auth_settings.user_mapping(),
        secret=auth_settings.secret,
        token_ttl_seconds=auth_settings.token_ttl_seconds,
    )
