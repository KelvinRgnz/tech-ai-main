from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from tech_ai.api.app import create_app
from tech_ai.config.settings import AuthSettings, Settings
from tech_ai.errors import (
    AttachmentStorageError,
    AttachmentValidationError,
    DocumentOcrError,
    LanguageAnalysisError,
    SpeechTranscriptionError,
)
from tech_ai.integrations.auth.password import hash_password
from tech_ai.integrations.documents.client import DocumentReader, OcrPage, OcrResult
from tech_ai.integrations.language.client import (
    SentimentConfidence,
    TextAnalysis,
    TextAnalyzer,
)
from tech_ai.integrations.local_attachment_storage import LocalAttachmentStorage
from tech_ai.integrations.speech.client import SpeechTranscriber, SpeechTranscript, WordTiming
from tech_ai.models.attachment import AttachmentAnalysis, StoredAttachment
from tech_ai.services.attachment_service import AttachmentService

PNG = b"\x89PNG\r\n\x1a\n" + b"academic-image"
PDF = b"%PDF-1.7\n% academic fictional report\n%%EOF"
WAV = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"academic-audio"
OGG = b"OggS" + (b"\x00" * 24) + b"OpusHead" + b"academic-audio"
PASSWORD = "test-password"


class MemoryAttachments:
    def __init__(self) -> None:
        self.patients: dict[UUID, tuple[str, UUID]] = {}
        self.attachments: dict[UUID, StoredAttachment] = {}

    def add_patient(self, owner: str, patient_id: UUID) -> None:
        self.patients[patient_id] = (owner, uuid4())

    def create(self, owner: str, patient_id: UUID, attachment: StoredAttachment) -> bool:
        patient = self.patients.get(patient_id)
        if patient is None or patient[0] != owner:
            return False
        self.attachments[attachment.id] = replace(attachment, conversation_id=patient[1])
        return True

    def list_for_patient(
        self, owner: str, patient_id: UUID
    ) -> tuple[StoredAttachment, ...] | None:
        patient = self.patients.get(patient_id)
        if patient is None or patient[0] != owner:
            return None
        return tuple(
            item
            for item in self.attachments.values()
            if item.conversation_id == patient[1]
        )

    def get(
        self, owner: str, patient_id: UUID, attachment_id: UUID
    ) -> StoredAttachment | None:
        attachments = self.list_for_patient(owner, patient_id)
        if attachments is None:
            return None
        return next((item for item in attachments if item.id == attachment_id), None)

    def complete_analysis(
        self,
        owner: str,
        patient_id: UUID,
        attachment_id: UUID,
        analysis: AttachmentAnalysis,
    ) -> bool:
        attachment = self.get(owner, patient_id, attachment_id)
        if attachment is None:
            return False
        self.attachments[attachment_id] = replace(attachment, analysis=analysis)
        return True


class FailingAttachments(MemoryAttachments):
    def create(self, owner: str, patient_id: UUID, attachment: StoredAttachment) -> bool:
        del owner, patient_id, attachment
        raise RuntimeError("database offline")


class FakeSpeechTranscriber:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, str]] = []
        self.error: SpeechTranscriptionError | None = None

    def transcribe(self, path: Path, *, content_type: str) -> SpeechTranscript:
        self.calls.append((path, content_type))
        if self.error is not None:
            raise self.error
        return SpeechTranscript(
            text="Estou com dificuldade para completar o exercício.",
            language="pt-BR",
            duration_seconds=3.2,
            words=(
                WordTiming("Estou", 0.0, 0.3),
                WordTiming("com", 0.4, 0.2),
                WordTiming("dificuldade", 1.8, 0.5),
                WordTiming("exercício", 2.7, 0.5),
            ),
        )


class FakeTextAnalyzer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.error: LanguageAnalysisError | None = None

    def analyze(self, text: str, *, language: str = "pt-BR") -> TextAnalysis:
        self.calls.append((text, language))
        if self.error is not None:
            raise self.error
        return TextAnalysis(
            sentiment="negative",
            confidence=SentimentConfidence(positive=0.04, neutral=0.16, negative=0.8),
            key_phrases=("dificuldade", "exercício"),
        )


class FakeDocumentReader:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, str]] = []
        self.error: DocumentOcrError | None = None

    def read(self, path: Path, *, content_type: str) -> OcrResult:
        self.calls.append((path, content_type))
        if self.error is not None:
            raise self.error
        return OcrResult(
            text="Paciente fictício. Paracetamol 500 mg, uma vez ao dia.",
            pages=(
                OcrPage(
                    number=1,
                    text="Paciente fictício. Paracetamol 500 mg, uma vez ao dia.",
                ),
            ),
        )


async def stream(data: bytes) -> AsyncIterator[bytes]:
    yield data


def build_client(
    repository: MemoryAttachments,
    root: Path,
    *,
    transcriber: SpeechTranscriber | None = None,
    text_analyzer: TextAnalyzer | None = None,
    document_reader: DocumentReader | None = None,
) -> TestClient:
    password_hash = hash_password(PASSWORD)
    service = AttachmentService(
        repository,
        LocalAttachmentStorage(root),
        audio_transcriber=transcriber,
        text_analyzer=text_analyzer,
        document_reader=document_reader,
    )
    client = TestClient(
        create_app(
            settings=Settings(),
            auth_settings=AuthSettings(
                secret="test-secret-long-enough",
                users=(("alice", password_hash), ("bob", password_hash)),
            ),
            attachment_service=service,
        )
    )
    response = client.post("/api/login", json={"username": "alice", "password": PASSWORD})
    assert response.status_code == 200
    return client


def test_upload_process_list_and_authorized_content(tmp_path: Path) -> None:
    repository = MemoryAttachments()
    patient_id = uuid4()
    repository.add_patient("alice", patient_id)
    client = build_client(repository, tmp_path)

    uploaded = client.post(
        f"/api/patients/{patient_id}/attachments?filename=laudo.png",
        content=PNG,
        headers={"Content-Type": "image/png"},
    )
    assert uploaded.status_code == 201
    payload = uploaded.json()
    assert payload["original_name"] == "laudo.png"
    assert payload["modality"] == "image"
    assert payload["analysis"]["status"] == "pending"
    assert "storage_key" not in payload
    assert "sha256" not in payload

    processed = client.post(
        f"/api/patients/{patient_id}/attachments/{payload['id']}/process"
    )
    assert processed.status_code == 200
    assert processed.json()["analysis"]["status"] == "completed"
    assert processed.json()["analysis"]["attempt"] == 1
    assert "simulado" in processed.json()["analysis"]["limitations"][0].lower()

    listed = client.get(f"/api/patients/{patient_id}/attachments")
    content = client.get(
        f"/api/patients/{patient_id}/attachments/{payload['id']}/content"
    )
    assert len(listed.json()) == 1
    assert listed.json()[0]["analysis"]["status"] == "completed"
    assert content.status_code == 200
    assert content.content == PNG
    assert content.headers["content-type"] == "image/png"


def test_upload_accepts_pdf_as_document(tmp_path: Path) -> None:
    repository = MemoryAttachments()
    patient_id = uuid4()
    repository.add_patient("alice", patient_id)
    client = build_client(repository, tmp_path)
    response = client.post(
        f"/api/patients/{patient_id}/attachments?filename=prescricao.pdf",
        content=PDF,
        headers={"Content-Type": "application/pdf"},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["modality"] == "document"
    assert payload["content_type"] == "application/pdf"
    processed = client.post(
        f"/api/patients/{patient_id}/attachments/{payload['id']}/process"
    )
    assert processed.status_code == 200
    assert processed.json()["analysis"]["summary"].startswith("Documento PDF")


def test_document_uses_azure_ocr_and_reuses_persisted_result(tmp_path: Path) -> None:
    repository = MemoryAttachments()
    patient_id = uuid4()
    repository.add_patient("alice", patient_id)
    reader = FakeDocumentReader()
    client = build_client(repository, tmp_path, document_reader=reader)
    uploaded = client.post(
        f"/api/patients/{patient_id}/attachments?filename=prescricao-ficticia.pdf",
        content=PDF,
        headers={"Content-Type": "application/pdf"},
    ).json()

    first = client.post(
        f"/api/patients/{patient_id}/attachments/{uploaded['id']}/process"
    )
    second = client.post(
        f"/api/patients/{patient_id}/attachments/{uploaded['id']}/process"
    )

    analysis = first.json()["analysis"]
    assert analysis["status"] == "completed"
    assert analysis["processor_name"] == "azure-document-intelligence-read"
    assert "Paracetamol 500 mg" in analysis["summary"]
    assert "Páginas processadas pelo OCR: 1" in " ".join(analysis["observations"])
    assert "revisão humana" in " ".join(analysis["limitations"])
    assert second.json() == first.json()
    assert len(reader.calls) == 1
    assert reader.calls[0][1] == "application/pdf"


def test_document_persists_sanitized_ocr_failure(tmp_path: Path) -> None:
    repository = MemoryAttachments()
    patient_id = uuid4()
    repository.add_patient("alice", patient_id)
    reader = FakeDocumentReader()
    reader.error = DocumentOcrError("Nenhum texto legível foi reconhecido no documento.")
    client = build_client(repository, tmp_path, document_reader=reader)
    uploaded = client.post(
        f"/api/patients/{patient_id}/attachments?filename=ilegivel.png",
        content=PNG,
        headers={"Content-Type": "image/png"},
    ).json()

    response = client.post(
        f"/api/patients/{patient_id}/attachments/{uploaded['id']}/process"
    )

    analysis = response.json()["analysis"]
    assert analysis["status"] == "failed"
    assert analysis["error_code"] == "document_ocr_failed"
    assert "Nenhum texto legível" in analysis["limitations"][0]


def test_audio_uses_azure_transcriber_reports_pauses_and_reuses_result(
    tmp_path: Path,
) -> None:
    repository = MemoryAttachments()
    patient_id = uuid4()
    repository.add_patient("alice", patient_id)
    transcriber = FakeSpeechTranscriber()
    client = build_client(repository, tmp_path, transcriber=transcriber)
    uploaded = client.post(
        f"/api/patients/{patient_id}/attachments?filename=relato.wav",
        content=WAV,
        headers={"Content-Type": "audio/wav"},
    ).json()

    first = client.post(
        f"/api/patients/{patient_id}/attachments/{uploaded['id']}/process"
    )
    second = client.post(
        f"/api/patients/{patient_id}/attachments/{uploaded['id']}/process"
    )

    assert first.status_code == 200
    analysis = first.json()["analysis"]
    assert analysis["status"] == "completed"
    assert analysis["processor_name"] == "azure-speech-realtime"
    assert "dificuldade" in analysis["summary"]
    assert "pelo menos 0.8 s: 1" in " ".join(analysis["observations"])
    assert "não permitem concluir" in " ".join(analysis["limitations"])
    assert second.json() == first.json()
    assert len(transcriber.calls) == 1
    assert transcriber.calls[0][1] == "audio/wav"


def test_whatsapp_ogg_is_accepted_as_opus_audio(tmp_path: Path) -> None:
    repository = MemoryAttachments()
    patient_id = uuid4()
    repository.add_patient("alice", patient_id)
    transcriber = FakeSpeechTranscriber()
    client = build_client(repository, tmp_path, transcriber=transcriber)

    uploaded = client.post(
        f"/api/patients/{patient_id}/attachments?filename=whatsapp.ogg",
        content=OGG,
        headers={"Content-Type": "audio/ogg"},
    )
    processed = client.post(
        f"/api/patients/{patient_id}/attachments/{uploaded.json()['id']}/process"
    )

    assert uploaded.status_code == 201
    assert uploaded.json()["content_type"] == "audio/ogg"
    assert processed.json()["analysis"]["status"] == "completed"
    assert transcriber.calls[0][1] == "audio/ogg"


def test_audio_persists_sanitized_transcription_failure(tmp_path: Path) -> None:
    repository = MemoryAttachments()
    patient_id = uuid4()
    repository.add_patient("alice", patient_id)
    transcriber = FakeSpeechTranscriber()
    transcriber.error = SpeechTranscriptionError("Nenhuma fala inteligível foi reconhecida.")
    client = build_client(repository, tmp_path, transcriber=transcriber)
    uploaded = client.post(
        f"/api/patients/{patient_id}/attachments?filename=relato.wav",
        content=WAV,
        headers={"Content-Type": "audio/wav"},
    ).json()

    response = client.post(
        f"/api/patients/{patient_id}/attachments/{uploaded['id']}/process"
    )

    assert response.status_code == 200
    analysis = response.json()["analysis"]
    assert analysis["status"] == "failed"
    assert analysis["error_code"] == "speech_transcription_failed"
    assert "Nenhuma fala" in analysis["limitations"][0]


def test_audio_adds_language_analysis_without_repeating_cloud_calls(tmp_path: Path) -> None:
    repository = MemoryAttachments()
    patient_id = uuid4()
    repository.add_patient("alice", patient_id)
    transcriber = FakeSpeechTranscriber()
    text_analyzer = FakeTextAnalyzer()
    client = build_client(
        repository,
        tmp_path,
        transcriber=transcriber,
        text_analyzer=text_analyzer,
    )
    uploaded = client.post(
        f"/api/patients/{patient_id}/attachments?filename=relato-language.wav",
        content=WAV,
        headers={"Content-Type": "audio/wav"},
    ).json()

    first = client.post(
        f"/api/patients/{patient_id}/attachments/{uploaded['id']}/process"
    )
    second = client.post(
        f"/api/patients/{patient_id}/attachments/{uploaded['id']}/process"
    )

    analysis = first.json()["analysis"]
    rendered = " ".join(analysis["observations"])
    assert analysis["processor_name"] == "azure-speech-language"
    assert "dificuldade, exercício" in rendered
    assert "negativo" in rendered
    assert "80%" in rendered
    assert "não o estado clínico" in " ".join(analysis["limitations"])
    assert second.json() == first.json()
    assert len(transcriber.calls) == 1
    assert text_analyzer.calls == [
        ("Estou com dificuldade para completar o exercício.", "pt-BR")
    ]


def test_audio_preserves_transcription_when_language_analysis_fails(tmp_path: Path) -> None:
    repository = MemoryAttachments()
    patient_id = uuid4()
    repository.add_patient("alice", patient_id)
    transcriber = FakeSpeechTranscriber()
    text_analyzer = FakeTextAnalyzer()
    text_analyzer.error = LanguageAnalysisError(
        "O Azure Language não concluiu a análise textual."
    )
    client = build_client(
        repository,
        tmp_path,
        transcriber=transcriber,
        text_analyzer=text_analyzer,
    )
    uploaded = client.post(
        f"/api/patients/{patient_id}/attachments?filename=relato-fallback.wav",
        content=WAV,
        headers={"Content-Type": "audio/wav"},
    ).json()

    response = client.post(
        f"/api/patients/{patient_id}/attachments/{uploaded['id']}/process"
    )

    analysis = response.json()["analysis"]
    assert analysis["status"] == "completed"
    assert analysis["processor_name"] == "azure-speech-realtime"
    assert "dificuldade" in analysis["summary"]
    assert "preservada" in " ".join(analysis["limitations"])


@pytest.mark.parametrize(
    "filename,content_type,data",
    [
        ("laudo.exe", "application/octet-stream", PNG),
        ("laudo.png", "image/jpeg", PNG),
        ("laudo.png", "image/png", b"not-a-png"),
        ("laudo.pdf", "application/pdf", PNG),
        ("../laudo.png", "image/png", PNG),
    ],
)
def test_rejects_unsupported_mismatched_or_unsafe_file(
    tmp_path: Path, filename: str, content_type: str, data: bytes
) -> None:
    repository = MemoryAttachments()
    patient_id = uuid4()
    repository.add_patient("alice", patient_id)
    client = build_client(repository, tmp_path)
    response = client.post(
        f"/api/patients/{patient_id}/attachments",
        params={"filename": filename},
        content=data,
        headers={"Content-Type": content_type},
    )
    assert response.status_code == 422
    assert repository.attachments == {}
    assert not tuple(tmp_path.rglob("*.png"))


def test_attachment_is_isolated_by_owner_and_patient(tmp_path: Path) -> None:
    repository = MemoryAttachments()
    patient_id = uuid4()
    repository.add_patient("alice", patient_id)
    client = build_client(repository, tmp_path)
    uploaded = client.post(
        f"/api/patients/{patient_id}/attachments?filename=laudo.png",
        content=PNG,
        headers={"Content-Type": "image/png"},
    ).json()
    client.post("/api/logout")
    login = client.post("/api/login", json={"username": "bob", "password": PASSWORD})
    assert login.status_code == 200
    assert client.get(f"/api/patients/{patient_id}/attachments").status_code == 404
    assert (
        client.get(
            f"/api/patients/{patient_id}/attachments/{uploaded['id']}/content"
        ).status_code
        == 404
    )


def test_service_removes_file_when_patient_does_not_exist(tmp_path: Path) -> None:
    repository = MemoryAttachments()
    service = AttachmentService(repository, LocalAttachmentStorage(tmp_path))
    with pytest.raises(LookupError, match="Paciente"):
        asyncio.run(
            service.upload(
                "alice",
                uuid4(),
                original_name="laudo.png",
                declared_content_type="image/png",
                chunks=stream(PNG),
            )
        )
    assert not tuple(path for path in tmp_path.rglob("*") if path.is_file())


def test_service_removes_file_when_metadata_persistence_fails(tmp_path: Path) -> None:
    service = AttachmentService(FailingAttachments(), LocalAttachmentStorage(tmp_path))
    with pytest.raises(RuntimeError, match="database offline"):
        asyncio.run(
            service.upload(
                "alice",
                uuid4(),
                original_name="laudo.png",
                declared_content_type="image/png",
                chunks=stream(PNG),
            )
        )
    assert not tuple(path for path in tmp_path.rglob("*") if path.is_file())


def test_local_storage_enforces_limit_and_blocks_traversal(tmp_path: Path) -> None:
    storage = LocalAttachmentStorage(tmp_path)
    with pytest.raises(AttachmentValidationError, match="limite"):
        asyncio.run(storage.write_temporary(stream(b"1234"), max_bytes=3))
    with pytest.raises(AttachmentStorageError, match="Chave"):
        storage.resolve("../outside.png")
