"""Diagnóstico PostgreSQL sem expor credenciais ou alterar dados."""

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from tech_ai.config.database import DatabaseSettings
from tech_ai.errors import DatabaseConnectionError


@contextmanager
def database_connection(
    settings: DatabaseSettings, *, read_only: bool = False
) -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    options = "-c statement_timeout=10000 -c lock_timeout=5000"
    if read_only:
        options += " -c default_transaction_read_only=on"
    try:
        with psycopg.connect(
            settings.url, sslmode="require", connect_timeout=10, options=options
        ) as connection:
            yield connection
    except psycopg.Error:
        raise DatabaseConnectionError(
            "Banco indisponível. Verifique a conexão e execute as migrações."
        ) from None


def check_connection(settings: DatabaseSettings) -> None:
    try:
        with psycopg.connect(
            settings.url,
            sslmode="require",
            connect_timeout=10,
            options="-c default_transaction_read_only=on -c statement_timeout=5000",
        ) as connection:
            row = connection.execute("SELECT 1").fetchone()
            if row != (1,):
                raise DatabaseConnectionError("Resposta inesperada do PostgreSQL.")
    except psycopg.Error:
        raise DatabaseConnectionError(
            "Não foi possível verificar o PostgreSQL. Confira rede e credenciais locais."
        ) from None
