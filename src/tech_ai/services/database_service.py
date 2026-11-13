"""Caso de uso de diagnóstico da persistência da aplicação."""

from tech_ai.config.database import DatabaseSettings
from tech_ai.integrations.postgres import check_connection
from tech_ai.integrations.postgres_schema import migrate_database


def check_database() -> None:
    check_connection(DatabaseSettings.from_environment())


def initialize_database() -> tuple[int, ...]:
    return migrate_database(DatabaseSettings.from_environment())
