"""Transcrição em tempo real com Azure Speech no plano F0."""

from __future__ import annotations

import importlib
import json
import threading
from contextlib import suppress
from pathlib import Path
from typing import Any, cast

from tech_ai.errors import ConfigurationError, SpeechTranscriptionError
from tech_ai.integrations.speech.client import SpeechTranscript, WordTiming
from tech_ai.integrations.speech.conversion import transcription_audio

_TICKS_PER_SECOND = 10_000_000
_SUPPORTED_CONTENT_TYPES = {"audio/wav", "audio/mpeg", "audio/ogg", "audio/mp4"}
_FICTIONAL_SSML = """<speak version="1.0" xml:lang="pt-BR">
<voice name="pt-BR-FranciscaNeural">
Paciente fictício em sessão de fisioterapia. Estou realizando o exercício de sentar e levantar.
<break time="2000ms"/>
Senti cansaço e precisei interromper o exercício por alguns segundos.
</voice></speak>"""


def _speech_sdk() -> Any:
    try:
        return cast(Any, importlib.import_module("azure.cognitiveservices.speech"))
    except ImportError as error:
        raise ConfigurationError(
            "O cliente Azure Speech não está instalado. Execute: uv sync --extra azure"
        ) from error


def _seconds(value: object) -> float:
    if isinstance(value, (int, float)):
        return max(float(value) / _TICKS_PER_SECOND, 0.0)
    return 0.0


def _detail_timings(raw_json: str) -> tuple[tuple[WordTiming, ...], float]:
    """Lê o JSON detalhado sem depender de campos opcionais do SDK."""

    try:
        payload = json.loads(raw_json)
    except (TypeError, json.JSONDecodeError):
        return (), 0.0
    if not isinstance(payload, dict):
        return (), 0.0
    nbest = payload.get("NBest")
    candidate = nbest[0] if isinstance(nbest, list) and nbest else payload
    if not isinstance(candidate, dict):
        return (), 0.0
    timings: list[WordTiming] = []
    words = candidate.get("Words")
    if isinstance(words, list):
        for item in words:
            if not isinstance(item, dict):
                continue
            text = str(item.get("Word", "")).strip()
            if not text:
                continue
            timings.append(
                WordTiming(
                    text=text,
                    offset_seconds=_seconds(item.get("Offset")),
                    duration_seconds=_seconds(item.get("Duration")),
                )
            )
    offset = _seconds(candidate.get("Offset", payload.get("Offset")))
    duration = _seconds(candidate.get("Duration", payload.get("Duration")))
    end = max((word.offset_seconds + word.duration_seconds for word in timings), default=0.0)
    return tuple(timings), max(end, offset + duration)


def synthesize_fictitious_audio(
    path: Path,
    *,
    key: str,
    region: str,
) -> None:
    """Gera um WAV curto e sem dados pessoais para o diagnóstico integrado."""

    speechsdk = _speech_sdk()
    speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
    )
    audio_config = speechsdk.audio.AudioOutputConfig(filename=str(path))
    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )
    try:
        result = synthesizer.speak_ssml_async(_FICTIONAL_SSML).get()
    except Exception as error:
        raise SpeechTranscriptionError("O Azure Speech não iniciou a síntese de teste.") from error
    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        raise SpeechTranscriptionError("O Azure Speech não concluiu a síntese de teste.")


class AzureSpeechTranscriber:
    """Cliente síncrono e limitado para arquivos curtos em português brasileiro."""

    def __init__(
        self,
        *,
        key: str,
        region: str,
        max_audio_seconds: int,
        max_concurrent_requests: int,
        language: str = "pt-BR",
    ) -> None:
        self._key = key
        self._region = region
        self._max_audio_seconds = max_audio_seconds
        self._language = language
        self._semaphore = threading.BoundedSemaphore(max_concurrent_requests)

    def transcribe(self, path: Path, *, content_type: str) -> SpeechTranscript:
        if content_type not in _SUPPORTED_CONTENT_TYPES:
            raise SpeechTranscriptionError("Formato de áudio não suportado pelo transcritor.")
        if not path.is_file():
            raise SpeechTranscriptionError("Arquivo de áudio indisponível para transcrição.")
        with self._semaphore, transcription_audio(
            path, content_type=content_type
        ) as transcription_path:
            return self._transcribe(transcription_path)

    def _transcribe(self, path: Path) -> SpeechTranscript:
        speechsdk = _speech_sdk()
        speech_config = speechsdk.SpeechConfig(subscription=self._key, region=self._region)
        speech_config.speech_recognition_language = self._language
        speech_config.output_format = speechsdk.OutputFormat.Detailed
        speech_config.request_word_level_timestamps()
        audio_config = None
        recognizer = None
        done = threading.Event()
        texts: list[str] = []
        words: list[WordTiming] = []
        ends: list[float] = []
        failure_codes: list[str] = []
        truncated = False

        def recognized(event: Any) -> None:
            nonlocal truncated
            result = event.result
            if result.reason != speechsdk.ResultReason.RecognizedSpeech:
                return
            text = str(result.text).strip()
            if text:
                texts.append(text)
            detail_words, end = _detail_timings(str(result.json))
            words.extend(detail_words)
            ends.append(end)
            if end >= self._max_audio_seconds:
                truncated = True
                done.set()

        def canceled(event: Any) -> None:
            details = speechsdk.CancellationDetails.from_result(event.result)
            if details.reason == speechsdk.CancellationReason.Error:
                failure_codes.append(str(details.error_code))
            done.set()

        timeout_seconds = self._max_audio_seconds + 30
        finished = False
        try:
            audio_config = speechsdk.audio.AudioConfig(filename=str(path))
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config,
                audio_config=audio_config,
            )
            recognizer.recognized.connect(recognized)
            recognizer.canceled.connect(canceled)
            recognizer.session_stopped.connect(lambda _event: done.set())
            recognizer.start_continuous_recognition_async().get()
            finished = done.wait(timeout_seconds)
        except Exception as error:
            raise SpeechTranscriptionError("O Azure Speech não iniciou a transcrição.") from error
        finally:
            if recognizer is not None:
                with suppress(Exception):
                    recognizer.stop_continuous_recognition_async().get()
            del recognizer, audio_config
        if not finished:
            raise SpeechTranscriptionError("A transcrição excedeu o tempo limite da POC.")
        if failure_codes:
            raise SpeechTranscriptionError(
                f"O Azure Speech recusou a transcrição ({failure_codes[0]})."
            )
        transcript = " ".join(texts).strip()
        if not transcript:
            raise SpeechTranscriptionError("Nenhuma fala inteligível foi reconhecida no áudio.")
        ordered_words = tuple(sorted(words, key=lambda item: item.offset_seconds))
        duration = max(ends, default=0.0)
        return SpeechTranscript(
            text=transcript,
            language=self._language,
            duration_seconds=min(duration, float(self._max_audio_seconds)),
            words=ordered_words,
            truncated=truncated,
        )
