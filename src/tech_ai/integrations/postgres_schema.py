"""Migração inicial explícita; não roda no startup da API."""

from tech_ai.config.database import DatabaseSettings
from tech_ai.errors import DatabaseConnectionError
from tech_ai.integrations.postgres import database_connection

_MIGRATION_1 = """
REVOKE ALL ON SCHEMA tech_ai FROM PUBLIC;
CREATE TABLE tech_ai.patients (
    id uuid PRIMARY KEY,
    owner_username text NOT NULL CHECK (length(owner_username) > 0),
    display_name text NOT NULL CHECK (length(btrim(display_name)) BETWEEN 1 AND 120),
    fictional boolean NOT NULL DEFAULT true CHECK (fictional),
    created_at timestamptz NOT NULL
);
CREATE INDEX patients_owner_created_idx
    ON tech_ai.patients (owner_username, created_at DESC, id);
CREATE TABLE tech_ai.conversations (
    id uuid PRIMARY KEY,
    patient_id uuid NOT NULL UNIQUE REFERENCES tech_ai.patients(id),
    created_at timestamptz NOT NULL
);
ALTER TABLE tech_ai.patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE tech_ai.conversations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON tech_ai.patients, tech_ai.conversations FROM PUBLIC;
"""

_MIGRATION_2 = """
CREATE TABLE tech_ai.messages (
    id uuid PRIMARY KEY,
    conversation_id uuid NOT NULL REFERENCES tech_ai.conversations(id),
    role text NOT NULL CHECK (role IN ('user', 'assistant')),
    content text NOT NULL CHECK (length(btrim(content)) BETWEEN 1 AND 20000),
    payload jsonb,
    created_at timestamptz NOT NULL
);
CREATE INDEX messages_conversation_created_idx
    ON tech_ai.messages (conversation_id, created_at ASC, id ASC);
ALTER TABLE tech_ai.messages ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON tech_ai.messages FROM PUBLIC;
"""

_MIGRATION_3 = """
CREATE TABLE tech_ai.attachments (
    id uuid PRIMARY KEY,
    conversation_id uuid NOT NULL REFERENCES tech_ai.conversations(id),
    original_name text NOT NULL CHECK (length(btrim(original_name)) BETWEEN 1 AND 255),
    storage_key text NOT NULL UNIQUE CHECK (length(storage_key) > 0),
    sha256 text NOT NULL CHECK (length(sha256) = 64),
    modality text NOT NULL CHECK (modality IN ('image', 'audio', 'video')),
    content_type text NOT NULL,
    size_bytes bigint NOT NULL CHECK (size_bytes > 0),
    created_at timestamptz NOT NULL
);
CREATE INDEX attachments_conversation_created_idx
    ON tech_ai.attachments (conversation_id, created_at ASC, id ASC);
CREATE TABLE tech_ai.analyses (
    id uuid PRIMARY KEY,
    attachment_id uuid NOT NULL UNIQUE REFERENCES tech_ai.attachments(id),
    status text NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    processor_name text NOT NULL,
    processor_version text NOT NULL,
    attempt integer NOT NULL DEFAULT 0 CHECK (attempt >= 0),
    summary text,
    observations jsonb NOT NULL DEFAULT '[]'::jsonb,
    limitations jsonb NOT NULL DEFAULT '[]'::jsonb,
    error_code text,
    created_at timestamptz NOT NULL,
    started_at timestamptz,
    finished_at timestamptz
);
ALTER TABLE tech_ai.attachments ENABLE ROW LEVEL SECURITY;
ALTER TABLE tech_ai.analyses ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON tech_ai.attachments, tech_ai.analyses FROM PUBLIC;
"""

_MIGRATION_4 = """
ALTER TABLE tech_ai.attachments
    DROP CONSTRAINT attachments_modality_check;
ALTER TABLE tech_ai.attachments
    ADD CONSTRAINT attachments_modality_check
    CHECK (modality IN ('document', 'image', 'audio', 'video'));
"""

_MIGRATIONS = {1: _MIGRATION_1, 2: _MIGRATION_2, 3: _MIGRATION_3, 4: _MIGRATION_4}


def migrate_database(settings: DatabaseSettings) -> tuple[int, ...]:
    """Aplica versões ausentes na mesma transação e retorna as versões aplicadas."""
    with database_connection(settings) as connection:
        lock = connection.execute("SELECT pg_try_advisory_xact_lock(74120401)").fetchone()
        if lock != (True,):
            raise DatabaseConnectionError(
                "Outra migração está em andamento. Tente novamente em instantes."
            )
        connection.execute("CREATE SCHEMA IF NOT EXISTS tech_ai")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS tech_ai.schema_migrations "
            "(version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        row = connection.execute("SELECT max(version) FROM tech_ai.schema_migrations").fetchone()
        version = row[0] if row else None
        latest = max(_MIGRATIONS)
        if version is not None and (not isinstance(version, int) or version > latest):
            raise DatabaseConnectionError("Versão do banco mais recente que esta aplicação.")
        current = version or 0
        applied: list[int] = []
        for migration_version in range(current + 1, latest + 1):
            connection.execute(_MIGRATIONS[migration_version])
            connection.execute(
                "INSERT INTO tech_ai.schema_migrations (version) VALUES (%s)",
                (migration_version,),
            )
            applied.append(migration_version)
        return tuple(applied)
