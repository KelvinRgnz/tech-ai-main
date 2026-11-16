"""Validação, persistência e processamento simulado de anexos."""

from __future__ import annotations

from collections.abc import AsyncIterable
from contextlib import suppress
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from tech_ai.errors import (
    AttachmentNotFoundError,
    AttachmentStorageError,
    AttachmentValidationError,
    DocumentOcrError,
    LanguageAnalysisError,
    PatientNotFoundError,
    SpeechTranscriptionError,
    VideoAnalysisError,
)
from tech_ai.integrations.documents.client import DocumentReader, OcrResult
from tech_ai.integrations.language.client import TextAnalysis, TextAnalyzer
from tech_ai.integrations.speech.client import SpeechTranscriber, SpeechTranscript
from tech_ai.integrations.speech.conversion import audio_only_container
from tech_ai.integrations.video.client import VideoMovementAnalysis, VideoMovementAnalyzer
from tech_ai.models.attachment import (
    AttachmentAnalysis,
    AttachmentModality,
    AttachmentView,
    StoredAttachment,
)
from tech_ai.repositories.attachment_repository import AttachmentRepository, AttachmentStorage

_MEBIBYTE = 1024 * 1024
_MAX_BYTES = {
    "document": 25 * _MEBIBYTE,
    "image": 10 * _MEBIBYTE,
    "audio": 25 * _MEBIBYTE,
    "video": 100 * _MEBIBYTE,
}
_EXTENSIONS: dict[str, tuple[AttachmentModality, str]] = {
    ".pdf": ("document", "application/pdf"),
    ".jpg": ("image", "image/jpeg"),
    ".jpeg": ("image", "image/jpeg"),
    ".png": ("image", "image/png"),
    ".wav": ("audio", "audio/wav"),
    ".mp3": ("audio", "audio/mpeg"),
    ".ogg": ("audio", "audio/ogg"),
    ".mp4": ("video", "video/mp4"),
}
_DECLARED_TYPES = {
    "application/pdf": "application/pdf",
    "image/jpeg": "image/jpeg",
    "image/png": "image/png",
    "audio/wav": "audio/wav",
    "audio/x-wav": "audio/wav",
    "audio/mpeg": "audio/mpeg",
    "audio/mp3": "audio/mpeg",
    "audio/ogg": "audio/ogg",
    "application/ogg": "audio/ogg",
    "video/mp4": "video/mp4",
}


class AttachmentService:
    def __init__(
        self,
        repository: AttachmentRepository,
        storage: AttachmentStorage,
        *,
        audio_transcriber: SpeechTranscriber | None = None,
        text_analyzer: TextAnalyzer | None = None,
        document_reader: DocumentReader | None = None,
        video_analyzer: VideoMovementAnalyzer | None = None,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._audio_transcriber = audio_transcriber
        self._text_analyzer = text_analyzer
        self._document_reader = document_reader
        self._video_analyzer = video_analyzer

    async def upload(
        self,
        owner: str,
        patient_id: UUID,
        *,
        original_name: str,
        declared_content_type: str,
        chunks: AsyncIterable[bytes],
    ) -> AttachmentView:
        name, extension, expected_modality, expected_type = self._validate_metadata(
            original_name, declared_content_type
        )
        temporary = await self._storage.write_temporary(
            chunks, max_bytes=_MAX_BYTES[expected_modality]
        )
        try:
            detected_modality, detected_type = _detect_content(temporary.header)
            if (detected_modality, detected_type) != (expected_modality, expected_type):
                raise AttachmentValidationError(
                    "A extensão, o tipo declarado e o conteúdo real do arquivo não coincidem."
                )
            attachment_id = uuid4()
            analysis_id = uuid4()
            now = datetime.now(UTC)
            storage_key = f"{attachment_id.hex[:2]}/{attachment_id}{extension}"
            analysis = AttachmentAnalysis(
                analysis_id,
                "pending",
                "simulated-multimodal-processor",
                "1.0",
                0,
                None,
                (),
                ("Processamento ainda não iniciado.",),
                None,
                now,
                None,
                None,
            )
            attachment = StoredAttachment(
                attachment_id,
                UUID(int=0),
                name,
                storage_key,
                temporary.sha256,
                detected_modality,
                detected_type,
                temporary.size_bytes,
                now,
                analysis,
            )
            self._storage.promote(temporary, storage_key=storage_key)
            try:
                created = self._repository.create(owner, patient_id, attachment)
            except Exception:
                with suppress(AttachmentStorageError):
                    self._storage.remove(storage_key)
                raise
            if not created:
                self._storage.remove(storage_key)
                raise PatientNotFoundError("Paciente não encontrado.")
            return AttachmentView.from_stored(attachment)
        except Exception:
            temporary.path.unlink(missing_ok=True)
            raise

    def list_for_patient(self, owner: str, patient_id: UUID) -> tuple[AttachmentView, ...]:
        attachments = self._repository.list_for_patient(owner, patient_id)
        if attachments is None:
            raise PatientNotFoundError("Paciente não encontrado.")
        return tuple(AttachmentView.from_stored(item) for item in attachments)

    def process(self, owner: str, patient_id: UUID, attachment_id: UUID) -> AttachmentView:
        attachment = self._get(owner, patient_id, attachment_id)
        simulated = attachment.analysis.processor_name == "simulated-multimodal-processor"
        if attachment.analysis.status == "completed" and not simulated:
            return AttachmentView.from_stored(attachment)
        transcriber = self._audio_transcriber
        if attachment.modality == "audio" and transcriber is not None:
            return self._process_audio(owner, patient_id, attachment, transcriber)
        if attachment.modality in {"document", "image"} and self._document_reader is not None:
            return self._process_document(
                owner,
                patient_id,
                attachment,
                self._document_reader,
            )
        if attachment.modality == "video" and self._video_analyzer is not None:
            return self._process_video(owner, patient_id, attachment, self._video_analyzer)
        if (
            attachment.modality == "video"
            and transcriber is not None
            and audio_only_container(self._storage.resolve(attachment.storage_key))
        ):
            return self._process_audio(
                owner,
                patient_id,
                attachment,
                transcriber,
                content_type="audio/mp4",
            )
        return self._process_simulated(owner, patient_id, attachment)

    def _process_video(
        self,
        owner: str,
        patient_id: UUID,
        attachment: StoredAttachment,
        analyzer: VideoMovementAnalyzer,
    ) -> AttachmentView:
        started = datetime.now(UTC)
        try:
            result = analyzer.analyze(self._storage.resolve(attachment.storage_key))
        except VideoAnalysisError as error:
            finished = datetime.now(UTC)
            analysis = AttachmentAnalysis(
                attachment.analysis.id,
                "failed",
                "mediapipe-pose-sit-to-stand",
                "1.0",
                attachment.analysis.attempt + 1,
                "Não foi possível analisar o movimento no vídeo.",
                (),
                (str(error), "Nenhuma conclusão clínica foi produzida a partir do vídeo."),
                "video_analysis_failed",
                attachment.analysis.created_at,
                started,
                finished,
            )
            return self._save_analysis(owner, patient_id, attachment, analysis)

        finished = datetime.now(UTC)
        analysis = AttachmentAnalysis(
            attachment.analysis.id,
            "completed",
            "mediapipe-pose-sit-to-stand",
            "1.0",
            attachment.analysis.attempt + 1,
            f"Análise de pose: {result.repetitions} repetição(ões) de sentar e levantar.",
            _video_observations(result),
            _video_limitations(),
            None,
            attachment.analysis.created_at,
            started,
            finished,
        )
        return self._save_analysis(owner, patient_id, attachment, analysis)

    def _process_document(
        self,
        owner: str,
        patient_id: UUID,
        attachment: StoredAttachment,
        reader: DocumentReader,
    ) -> AttachmentView:
        started = datetime.now(UTC)
        try:
            result = reader.read(
                self._storage.resolve(attachment.storage_key),
                content_type=attachment.content_type,
            )
        except DocumentOcrError as error:
            finished = datetime.now(UTC)
            analysis = AttachmentAnalysis(
                attachment.analysis.id,
                "failed",
                "azure-document-intelligence-read",
                "1.0",
                attachment.analysis.attempt + 1,
                "Não foi possível extrair o texto do documento.",
                (),
                (
                    str(error),
                    "Nenhum campo ausente foi preenchido por suposição.",
                ),
                "document_ocr_failed",
                attachment.analysis.created_at,
                started,
                finished,
            )
            return self._save_analysis(owner, patient_id, attachment, analysis)

        finished = datetime.now(UTC)
        analysis = AttachmentAnalysis(
            attachment.analysis.id,
            "completed",
            "azure-document-intelligence-read",
            "1.0",
            attachment.analysis.attempt + 1,
            f"Texto original do OCR: {result.text}",
            _document_observations(result),
            _document_limitations(result),
            None,
            attachment.analysis.created_at,
            started,
            finished,
        )
        return self._save_analysis(owner, patient_id, attachment, analysis)

    def _process_audio(
        self,
        owner: str,
        patient_id: UUID,
        attachment: StoredAttachment,
        transcriber: SpeechTranscriber,
        content_type: str | None = None,
    ) -> AttachmentView:
        started = datetime.now(UTC)
        try:
            transcript = transcriber.transcribe(
                self._storage.resolve(attachment.storage_key),
                content_type=content_type or attachment.content_type,
            )
        except SpeechTranscriptionError as error:
            finished = datetime.now(UTC)
            analysis = AttachmentAnalysis(
                attachment.analysis.id,
                "failed",
                "azure-speech-realtime",
                "1.0",
                attachment.analysis.attempt + 1,
                "Não foi possível transcrever o áudio.",
                (),
                (
                    str(error),
                    "Nenhuma conclusão clínica foi produzida a partir deste áudio.",
                ),
                "speech_transcription_failed",
                attachment.analysis.created_at,
                started,
                finished,
            )
            return self._save_analysis(owner, patient_id, attachment, analysis)

        text_analysis: TextAnalysis | None = None
        language_failure: str | None = None
        if self._text_analyzer is not None:
            try:
                text_analysis = self._text_analyzer.analyze(
                    transcript.text,
                    language=transcript.language,
                )
            except LanguageAnalysisError as error:
                language_failure = str(error)

        finished = datetime.now(UTC)
        observations = list(_speech_observations(transcript))
        limitations = list(_speech_limitations(transcript))
        processor_name = "azure-speech-realtime"
        processor_version = "1.0"
        if text_analysis is not None:
            observations.extend(_language_observations(text_analysis))
            limitations.extend(_language_limitations())
            processor_name = "azure-speech-language"
            processor_version = "1.1"
        elif language_failure is not None:
            limitations.append(language_failure)
            limitations.append(
                "A transcrição foi preservada sem a análise textual complementar."
            )
        analysis = AttachmentAnalysis(
            attachment.analysis.id,
            "completed",
            processor_name,
            processor_version,
            attachment.analysis.attempt + 1,
            f"Transcrição: {transcript.text}",
            tuple(observations),
            tuple(limitations),
            None,
            attachment.analysis.created_at,
            started,
            finished,
        )
        return self._save_analysis(owner, patient_id, attachment, analysis)

    def _process_simulated(
        self,
        owner: str,
        patient_id: UUID,
        attachment: StoredAttachment,
    ) -> AttachmentView:
        now = datetime.now(UTC)
        modality_label = {
            "document": "Documento PDF",
            "image": "Imagem",
            "audio": "Áudio",
            "video": "Vídeo",
        }[attachment.modality]
        analysis = AttachmentAnalysis(
            attachment.analysis.id,
            "completed",
            "simulated-multimodal-processor",
            "1.0",
            attachment.analysis.attempt + 1,
            f"{modality_label} recebido e validado para o fluxo acadêmico.",
            (
                f"Formato confirmado: {attachment.content_type}.",
                f"Tamanho recebido: {attachment.size_bytes} bytes.",
            ),
            (
                "Resultado simulado: nenhum conteúdo clínico foi extraído.",
                "A integração Azure ainda não foi acionada.",
            ),
            None,
            attachment.analysis.created_at,
            now,
            now,
        )
        return self._save_analysis(owner, patient_id, attachment, analysis)

    def _save_analysis(
        self,
        owner: str,
        patient_id: UUID,
        attachment: StoredAttachment,
        analysis: AttachmentAnalysis,
    ) -> AttachmentView:
        if not self._repository.complete_analysis(owner, patient_id, attachment.id, analysis):
            raise AttachmentNotFoundError("Anexo não encontrado.")
        return AttachmentView.from_stored(replace(attachment, analysis=analysis))

    def content(self, owner: str, patient_id: UUID, attachment_id: UUID) -> tuple[Path, str, str]:
        attachment = self._get(owner, patient_id, attachment_id)
        return (
            self._storage.resolve(attachment.storage_key),
            attachment.content_type,
            attachment.original_name,
        )

    def _get(self, owner: str, patient_id: UUID, attachment_id: UUID) -> StoredAttachment:
        attachment = self._repository.get(owner, patient_id, attachment_id)
        if attachment is None:
            raise AttachmentNotFoundError("Anexo não encontrado.")
        return attachment

    @staticmethod
    def _validate_metadata(
        original_name: str, declared_content_type: str
    ) -> tuple[str, str, AttachmentModality, str]:
        name = original_name.strip()
        if not name or len(name) > 255 or any(char in name for char in ("/", "\\", "\0")):
            raise AttachmentValidationError("Nome de arquivo inválido.")
        extension = Path(name).suffix.lower()
        expected = _EXTENSIONS.get(extension)
        if expected is None:
            raise AttachmentValidationError(
                "Formato não aceito. Use PDF, JPEG, PNG, WAV, MP3, OGG ou MP4."
            )
        declared = declared_content_type.split(";", 1)[0].strip().lower()
        normalized_declared = _DECLARED_TYPES.get(declared)
        if normalized_declared != expected[1]:
            raise AttachmentValidationError(
                "O tipo declarado não corresponde à extensão do arquivo."
            )
        return name, extension, expected[0], expected[1]


def _detect_content(header: bytes) -> tuple[AttachmentModality, str]:
    if header.startswith(b"%PDF-"):
        return "document", "application/pdf"
    if header.startswith(b"\xff\xd8\xff"):
        return "image", "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image", "image/png"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WAVE":
        return "audio", "audio/wav"
    if header.startswith(b"ID3") or (
        len(header) >= 2 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0
    ):
        return "audio", "audio/mpeg"
    if header.startswith(b"OggS") and b"Opus" in header:
        return "audio", "audio/ogg"
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return "video", "video/mp4"
    raise AttachmentValidationError("O conteúdo do arquivo não corresponde a um formato aceito.")


def _speech_observations(transcript: SpeechTranscript) -> tuple[str, ...]:
    observations = [
        f"Idioma de reconhecimento: {transcript.language}.",
        f"Duração transcrita aproximada: {transcript.duration_seconds:.1f} s.",
    ]
    threshold_seconds = 0.8
    pauses = tuple(
        (
            previous.offset_seconds + previous.duration_seconds,
            current.offset_seconds,
        )
        for previous, current in zip(transcript.words, transcript.words[1:], strict=False)
        if current.offset_seconds
        - (previous.offset_seconds + previous.duration_seconds)
        >= threshold_seconds
    )
    observations.append(
        f"Pausas entre palavras de pelo menos {threshold_seconds:.1f} s: {len(pauses)}."
    )
    if pauses:
        longest_start, longest_end = max(pauses, key=lambda item: item[1] - item[0])
        observations.append(
            "Maior pausa estimada: "
            f"{longest_end - longest_start:.1f} s, entre {longest_start:.1f} s e "
            f"{longest_end:.1f} s."
        )
    if not transcript.words:
        observations.append("O provedor não devolveu marcações temporais por palavra.")
    return tuple(observations)


def _speech_limitations(transcript: SpeechTranscript) -> tuple[str, ...]:
    limitations = [
        "As pausas são estimativas experimentais baseadas nas marcações do reconhecimento.",
        "Pausas isoladas não permitem concluir desconforto ou dificuldade respiratória.",
        "Ruído, dicção e múltiplos falantes podem alterar a transcrição e os intervalos.",
    ]
    if transcript.truncated:
        limitations.append("O áudio foi interrompido ao atingir o limite de duração da POC.")
    return tuple(limitations)


_SENTIMENT_LABELS = {
    "positive": "positivo",
    "neutral": "neutro",
    "negative": "negativo",
    "mixed": "misto",
}


def _language_observations(analysis: TextAnalysis) -> tuple[str, ...]:
    phrases = ", ".join(analysis.key_phrases) if analysis.key_phrases else "nenhuma"
    sentiment = _SENTIMENT_LABELS.get(analysis.sentiment.casefold(), analysis.sentiment)
    confidence = analysis.confidence
    return (
        f"Frases-chave extraídas do texto: {phrases}.",
        "Sentimento textual predominante: "
        f"{sentiment} (positivo {confidence.positive:.0%}, "
        f"neutro {confidence.neutral:.0%}, negativo {confidence.negative:.0%}).",
    )


def _language_limitations() -> tuple[str, ...]:
    return (
        "O sentimento descreve o texto transcrito, não o estado clínico da pessoa.",
        "Frases-chave são termos relevantes do texto e não constituem achados clínicos.",
        "Erros da transcrição podem alterar as frases-chave e o sentimento estimado.",
    )


def _document_observations(result: OcrResult) -> tuple[str, ...]:
    return (
        f"Páginas processadas pelo OCR: {len(result.pages)}.",
        f"Caracteres reconhecidos: {len(result.text)}.",
    )


def _document_limitations(result: OcrResult) -> tuple[str, ...]:
    limitations = [
        "O texto foi extraído automaticamente e precisa de revisão humana.",
        "Trechos ilegíveis, manuscritos ou com baixa qualidade podem conter erros ou omissões.",
        "Nenhum valor ausente foi completado por suposição.",
    ]
    if len(result.pages) >= 2:
        limitations.append("No plano F0, somente as duas primeiras páginas são processadas.")
    return tuple(limitations)


def _video_observations(result: VideoMovementAnalysis) -> tuple[str, ...]:
    observations = [
        f"Duração analisada: {result.duration_seconds:.1f} s.",
        f"Cobertura de pose: {result.pose_coverage:.0%} dos quadros amostrados.",
        f"Ângulo de joelho observado: {result.minimum_knee_angle:.0f}° a "
        f"{result.maximum_knee_angle:.0f}°.",
    ]
    observations.extend(
        f"Evento em {event.timestamp_seconds:.1f} s: {event.description}"
        for event in result.events
    )
    return tuple(observations)


def _video_limitations() -> tuple[str, ...]:
    return (
        "Os limiares angulares são experimentais e específicos desta demonstração.",
        "A contagem depende de câmera fixa, visão lateral e corpo inteiro visível.",
        "O relatório descreve movimento aparente e não constitui avaliação clínica.",
        "Uma gravação isolada não demonstra monitoramento contínuo de internação.",
    )
