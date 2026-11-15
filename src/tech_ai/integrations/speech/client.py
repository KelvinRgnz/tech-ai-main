"""Contrato independente de provedor para transcrição de arquivos de áudio."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class WordTiming:
    """Palavra reconhecida e sua posição aproximada no áudio."""

    text: str
    offset_seconds: float
    duration_seconds: float


@dataclass(frozen=True, slots=True)
class SpeechTranscript:
    """Resultado normalizado entregue ao caso de uso de anexos."""

    text: str
    language: str
    duration_seconds: float
    words: tuple[WordTiming, ...]
    truncated: bool = False


class SpeechTranscriber(Protocol):
    """Fronteira implementada pelo Azure e por dublês de teste."""

    def transcribe(self, path: Path, *, content_type: str) -> SpeechTranscript: ...
