"""Interface de linha de comando do runtime de IA."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from tech_ai.config.settings import Settings, load_project_environment
from tech_ai.errors import (
    AssistantError,
    ConfigurationError,
    DatabaseConnectionError,
    EmbeddingError,
    KnowledgeRetrievalError,
    KnowledgeStoreError,
    ModelArtifactReadError,
    ModelArtifactValidationError,
    ModelRuntimeError,
    TranslationError,
)
from tech_ai.models.assistant import AssistantQuery
from tech_ai.services.model_artifact_service import inspect_model_artifact


def _build_parser(settings: Settings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tech-ai",
        description="Consome o modelo médico pronto do Tech Challenge.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("check-db", help="Verifica PostgreSQL sem alterar dados.")
    subcommands.add_parser("migrate-db", help="Aplica migrações da persistência PostgreSQL.")
    inspect_parser = subcommands.add_parser(
        "inspect-model",
        help="Valida e exibe o manifesto de um modelo publicado.",
    )
    inspect_parser.add_argument(
        "--manifest",
        type=Path,
        default=settings.model_manifest_path,
        help="Manifesto publicado pelo tech-fine-tuning.",
    )

    search_parser = subcommands.add_parser(
        "search",
        help="Consulta semanticamente a coleção MedQuAD no ChromaDB.",
    )
    search_parser.add_argument("--question", required=True, help="Pergunta a pesquisar.")
    search_parser.add_argument(
        "--limit",
        type=int,
        default=settings.retrieval_limit,
        help="Quantidade máxima de evidências.",
    )
    search_parser.add_argument(
        "--max-distance",
        type=float,
        default=settings.max_retrieval_distance,
        help="Distância máxima aceita para uma evidência.",
    )

    ask_parser = subcommands.add_parser(
        "ask",
        help="Responde usando o modelo publicado e evidências do ChromaDB.",
    )
    ask_parser.add_argument("--question", required=True, help="Pergunta médica.")
    ask_parser.add_argument(
        "--limit",
        type=int,
        default=settings.retrieval_limit,
        help="Quantidade máxima de evidências no prompt.",
    )
    ask_parser.add_argument(
        "--max-distance",
        type=float,
        default=settings.max_retrieval_distance,
        help="Distância máxima aceita para uma evidência.",
    )
    ask_parser.add_argument(
        "--manifest",
        type=Path,
        default=settings.model_manifest_path,
        help="Manifesto de implantação do modelo publicado.",
    )

    serve_parser = subcommands.add_parser(
        "serve",
        help="Sobe a interface do assistente médico acadêmico.",
    )
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8080)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    load_project_environment()
    try:
        settings = Settings.from_environment()
        parser = _build_parser(settings)
        arguments = parser.parse_args(argv)
        if arguments.command == "migrate-db":
            from tech_ai.services.database_service import initialize_database

            applied = initialize_database()
            if applied:
                versions = ", ".join(str(version) for version in applied)
                print(f"Migrações aplicadas: {versions}.")
            else:
                print("Banco já atualizado.")
            return 0
        if arguments.command == "check-db":
            from tech_ai.services.database_service import check_database

            check_database()
            print("PostgreSQL: conexão TLS e consulta somente-leitura verificadas.")
            return 0
        if arguments.command == "inspect-model":
            artifact = inspect_model_artifact(arguments.manifest)
            print(artifact.to_json())
            return 0
        if arguments.command == "search":
            from tech_ai.config.dependencies import build_knowledge_retrieval_service

            command_settings = Settings(
                model_manifest_path=settings.model_manifest_path,
                retrieval_limit=arguments.limit,
                max_retrieval_distance=arguments.max_distance,
                max_source_characters=settings.max_source_characters,
            )
            retrieval_service = build_knowledge_retrieval_service(command_settings)
            results = retrieval_service.search(arguments.question, limit=arguments.limit)
            print(
                json.dumps(
                    [result.as_dict() for result in results],
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if arguments.command == "ask":
            from tech_ai.config.dependencies import build_medical_assistant_service

            command_settings = Settings(
                model_manifest_path=arguments.manifest,
                retrieval_limit=arguments.limit,
                max_retrieval_distance=arguments.max_distance,
                max_source_characters=settings.max_source_characters,
            )
            assistant_service = build_medical_assistant_service(command_settings)
            answer = assistant_service.answer(
                AssistantQuery(question=arguments.question),
                limit=arguments.limit,
            )
            print(answer.to_json())
            return 0
        if arguments.command == "serve":
            import uvicorn

            from tech_ai.api.app import create_app

            print(f"Assistente médico em http://{arguments.host}:{arguments.port}")
            uvicorn.run(
                create_app(),
                host=arguments.host,
                port=arguments.port,
            )
            return 0
    except (
        AssistantError,
        ConfigurationError,
        DatabaseConnectionError,
        EmbeddingError,
        KnowledgeRetrievalError,
        KnowledgeStoreError,
        ModelArtifactReadError,
        ModelArtifactValidationError,
        ModelRuntimeError,
        TranslationError,
    ) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 2

    parser.error(f"Comando desconhecido: {arguments.command}")
    return 2
