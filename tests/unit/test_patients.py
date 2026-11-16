from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from tech_ai.api.app import create_app
from tech_ai.config.settings import AuthSettings, Settings
from tech_ai.errors import DatabaseConnectionError, PatientValidationError
from tech_ai.integrations.auth.password import hash_password
from tech_ai.models.patient import PatientConversation
from tech_ai.services.patient_service import PatientService


class MemoryPatients:
    def __init__(self) -> None:
        self.records: dict[UUID, tuple[str, PatientConversation]] = {}

    def create(self, owner: str, patient: PatientConversation) -> None:
        self.records[patient.id] = (owner, patient)

    def list_for_owner(
        self, owner: str, *, limit: int, offset: int
    ) -> tuple[PatientConversation, ...]:
        return tuple(p for user, p in self.records.values() if user == owner)[
            offset : offset + limit
        ]

    def get(self, owner: str, patient_id: UUID) -> PatientConversation | None:
        record = self.records.get(patient_id)
        return record[1] if record is not None and record[0] == owner else None


def client(service: PatientService) -> TestClient:
    hashed = hash_password("test-password")
    return TestClient(
        create_app(
            settings=Settings(),
            auth_settings=AuthSettings(
                secret="test-secret-long-enough", users=(("alice", hashed), ("bob", hashed))
            ),
            patient_service=service,
        )
    )


def login(api: TestClient, username: str) -> None:
    assert (
        api.post("/api/login", json={"username": username, "password": "test-password"}).status_code
        == 200
    )


def test_patient_creation_retrieval_isolation_and_reload() -> None:
    repository = MemoryPatients()
    api = client(PatientService(repository))
    assert api.get("/api/patients").status_code == 401
    assert api.post("/api/patients", json={"display_name": "Paciente"}).status_code == 401
    login(api, "alice")
    response = api.post("/api/patients", json={"display_name": "  Paciente fictício A  "})
    assert response.status_code == 201
    patient = response.json()
    assert patient["display_name"] == "Paciente fictício A"
    assert patient["fictional"] is True
    assert patient["id"] != patient["conversation_id"]
    assert "owner_username" not in patient
    path = f"/api/patients/{patient['id']}/conversation"
    assert api.get(path).json() == patient
    assert api.get(path).json()["conversation_id"] == patient["conversation_id"]
    login(api, "bob")
    assert api.get("/api/patients").json() == []
    assert api.get(path).status_code == 404
    assert api.get(f"/api/patients/{uuid4()}/conversation").status_code == 404
    # Recriar serviço/API mantém os dados do repositório; teste não usa Supabase real.
    other = client(PatientService(repository))
    login(other, "alice")
    assert other.get("/api/patients").json() == [patient]


@pytest.mark.parametrize(
    "body",
    [
        {"display_name": " "},
        {"display_name": "a" * 121},
        {"display_name": "Teste", "owner_username": "bob"},
        {"display_name": "Teste", "fictional": False},
    ],
)
def test_rejects_invalid_or_client_owned_fields(body: dict[str, object]) -> None:
    api = client(PatientService(MemoryPatients()))
    login(api, "alice")
    assert api.post("/api/patients", json=body).status_code == 422


def test_pagination_validation_and_missing_database(monkeypatch: pytest.MonkeyPatch) -> None:
    service = PatientService(MemoryPatients())
    api = client(service)
    login(api, "alice")
    for name in ("A", "B"):
        api.post("/api/patients", json={"display_name": name})
    assert len(api.get("/api/patients?limit=1&offset=1").json()) == 1
    assert api.get("/api/patients?limit=101").status_code == 422
    assert api.get("/api/patients?offset=-1").status_code == 422
    assert api.get("/api/patients/not-a-uuid/conversation").status_code == 422

    def unavailable(*args: object, **kwargs: object) -> None:
        raise DatabaseConnectionError("private credentials")

    monkeypatch.setattr(service, "list_for_owner", unavailable)
    response = api.get("/api/patients")
    assert response.status_code == 503
    assert "private credentials" not in response.text


def test_service_validation() -> None:
    service = PatientService(MemoryPatients())
    with pytest.raises(PatientValidationError):
        service.create("alice", " ")
    with pytest.raises(PatientValidationError):
        service.list_for_owner("alice", limit=0)
