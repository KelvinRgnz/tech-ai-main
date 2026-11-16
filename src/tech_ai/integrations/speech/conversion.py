"""Conversão local e temporária de áudio para o formato do Azure Speech."""

from __future__ import annotations

import importlib
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from tech_ai.errors import ConfigurationError, SpeechTranscriptionError


def _ffmpeg_executable() -> str:
    try:
        package = cast(Any, importlib.import_module("imageio_ffmpeg"))
    except ImportError as error:
        raise ConfigurationError(
            "O conversor de áudio não está instalado. Execute: uv sync --extra azure"
        ) from error
    return cast(str, package.get_ffmpeg_exe())


def _discard_temporary(path: Path) -> None:
    """Remove the converted WAV even if Windows still holds it briefly."""
    for _attempt in range(20):
        try:
            path.unlink(missing_ok=True)
            return
        except OSError:
            time.sleep(0.05)


def audio_only_container(path: Path) -> bool:
    """True when ffmpeg sees an audio stream and no video stream."""
    try:
        completed = subprocess.run(  # noqa: S603 - executável vem do pacote instalado.
            [
                _ffmpeg_executable(),
                "-nostdin",
                "-hide_banner",
                "-i",
                str(path),
            ],
            check=False,
            capture_output=True,
            timeout=30,
        )
    except (ConfigurationError, OSError, subprocess.SubprocessError):
        return False
    details = completed.stderr.decode("utf-8", errors="replace")
    return "Audio:" in details and "Video:" not in details


@contextmanager
def transcription_audio(path: Path, *, content_type: str) -> Iterator[Path]:
    """Entrega WAV diretamente ou converte OGG/MP3 para PCM sem manter cópia."""

    if content_type == "audio/wav":
        yield path
        return

    converted = path.with_name(f".{path.stem}-{uuid4().hex}.wav")
    command = [
        _ffmpeg_executable(),
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        "-f",
        "wav",
        "-y",
        str(converted),
    ]
    try:
        completed = subprocess.run(  # noqa: S603 - executável vem do pacote instalado.
            command,
            check=False,
            capture_output=True,
            timeout=180,
        )
        header = converted.read_bytes()[:12] if converted.is_file() else b""
        if (
            completed.returncode != 0
            or not header.startswith(b"RIFF")
            or header[8:12] != b"WAVE"
        ):
            raise SpeechTranscriptionError(
                "Não foi possível converter o áudio para WAV PCM."
            )
        yield converted
    except (OSError, subprocess.SubprocessError) as error:
        raise SpeechTranscriptionError(
            "Não foi possível executar a conversão local do áudio."
        ) from error
    finally:
        _discard_temporary(converted)
