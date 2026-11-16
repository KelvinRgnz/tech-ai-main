from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from tech_ai.api.app import create_app
from tech_ai.config.settings import AuthSettings, Settings
from tech_ai.integrations.auth.password import hash_password
from tech_ai.models.conversation import ConversationMessage
from tech_ai.models.knowledge import KnowledgeSearchResult
from tech_ai.services.conversation_service import ConversationService
from tech_ai.services.knowledge_retrieval_service import KnowledgeRetrievalService


class MemoryConversations:
    def __init__(self) -> None:
        self.patients: dict[UUID, tuple[str, UUID]] = {}
        self.messages: list[ConversationMessage] = []

    def add_patient(self, owner: str, patient_id: UUID) -> None:
        self.patients[patient_id] = (owner, uuid4())

    def append(self, owner: str, patient_id: UUID, message: ConversationMessage) -> bool:
        patient = self.patients.get(patient_id)
        if patient is None or patient[0] != owner:
            return False
        self.messages.append(
            ConversationMessage(
                message.id,
                patient[1],
                message.role,
                message.content,
                message.payload,
                message.created_at,
            )
        )
        return True

    def list_messages(
        self, owner: str, patient_id: UUID, *, limit: int
    ) -> tuple[ConversationMessage, ...] | None:
        patient = self.patients.get(patient_id)
        if patient is None or patient[0] != owner:
            return None
        return tuple(message for message in self.messages if message.conversation_id == patient[1])[
            :limit
        ]

    def clear_messages(self, owner: str, patient_id: UUID) -> int | None:
        patient = self.patients.get(patient_id)
        if patient is None or patient[0] != owner:
            return None
        remaining = [
            message for message in self.messages if message.conversation_id != patient[1]
        ]
        deleted = len(self.messages) - len(remaining)
        self.messages = remaining
        return deleted


class Retrieval:
    def search(self, query: str, *, limit: int) -> tuple[KnowledgeSearchResult, ...]:
        del query, limit
        return (
            KnowledgeSearchResult(
                record_id="rec-1",
                text="Medical topic: Test\nQuestion: Q?\nAnswer: Evidence.",
                metadata={"focus": "Test"},
                distance=0.2,
            ),
        )


def build_client(repository: MemoryConversations) -> TestClient:
    password = hash_password("test-password")
    return TestClient(
        create_app(
            settings=Settings(),
            auth_settings=AuthSettings(
                secret="test-secret-long-enough",
                users=(("alice", password), ("bob", password)),
            ),
            conversation_service=ConversationService(repository),
            retrieval_service=cast(KnowledgeRetrievalService, Retrieval()),
        )
    )


def login(client: TestClient, username: str) -> None:
    response = client.post("/api/login", json={"username": username, "password": "test-password"})
    assert response.status_code == 200


def test_consult_persists_and_reloads_patient_history() -> None:
    repository = MemoryConversations()
    patient_id = uuid4()
    repository.add_patient("alice", patient_id)
    client = build_client(repository)
    login(client, "alice")
    response = client.post(
        "/api/consult", json={"question": "  My question  ", "patient_id": str(patient_id)}
    )
    assert response.status_code == 200
    history = client.get(f"/api/patients/{patient_id}/messages")
    assert history.status_code == 200
    messages = history.json()
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "My question"
    assert messages[1]["payload"]["mode"] == "evidence"
    assert messages[0]["conversation_id"] == messages[1]["conversation_id"]


def test_history_and_consult_are_isolated_by_owner() -> None:
    repository = MemoryConversations()
    patient_id = uuid4()
    repository.add_patient("alice", patient_id)
    client = build_client(repository)
    login(client, "bob")
    assert client.get(f"/api/patients/{patient_id}/messages").status_code == 404
    response = client.post(
        "/api/consult", json={"question": "question", "patient_id": str(patient_id)}
    )
    assert response.status_code == 404
    assert repository.messages == []


def test_owner_can_clear_only_their_history() -> None:
    repository = MemoryConversations()
    patient_id = uuid4()
    other_patient = uuid4()
    repository.add_patient("alice", patient_id)
    repository.add_patient("alice", other_patient)
    client = build_client(repository)
    login(client, "alice")
    assert (
        client.post(
            "/api/consult", json={"question": "question", "patient_id": str(patient_id)}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/consult", json={"question": "other", "patient_id": str(other_patient)}
        ).status_code
        == 200
    )
    cleared = client.delete(f"/api/patients/{patient_id}/messages")
    assert cleared.status_code == 200
    assert cleared.json() == {"deleted": 2}
    assert client.get(f"/api/patients/{patient_id}/messages").json() == []
    assert len(client.get(f"/api/patients/{other_patient}/messages").json()) == 2
    login(client, "bob")
    assert client.delete(f"/api/patients/{other_patient}/messages").status_code == 404
    assert len(repository.messages) == 2


def test_legacy_consult_without_patient_remains_available() -> None:
    repository = MemoryConversations()
    client = build_client(repository)
    login(client, "alice")
    assert client.post("/api/consult", json={"question": "question"}).status_code == 200
    assert repository.messages == []
