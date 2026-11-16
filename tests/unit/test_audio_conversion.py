from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tech_ai.errors import ConfigurationError, SpeechTranscriptionError
from tech_ai.integrations.speech.conversion import (
    _ffmpeg_executable,
    transcription_audio,
)


def test_wav_is_used_without_conversion(tmp_path: Path) -> None:
    source = tmp_path / "audio.wav"
    source.write_bytes(b"RIFF-test-WAVE")

    with transcription_audio(source, content_type="audio/wav") as converted:
        assert converted == source

    assert source.is_file()


def test_ogg_is_converted_to_temporary_pcm_and_removed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "whatsapp.ogg"
    source.write_bytes(b"OggS-OpusHead")
    command_seen: list[str] = []

    def convert(command: list[str], **_options: object) -> subprocess.CompletedProcess[bytes]:
        command_seen.extend(command)
        Path(command[-1]).write_bytes(b"RIFF\x00\x00\x00\x00WAVEpcm")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(
        "tech_ai.integrations.speech.conversion._ffmpeg_executable",
        lambda: "bundled-ffmpeg",
    )
    monkeypatch.setattr("tech_ai.integrations.speech.conversion.subprocess.run", convert)

    with transcription_audio(source, content_type="audio/ogg") as converted:
        assert converted.is_file()
        converted_path = converted
        assert "16000" in command_seen
        assert "pcm_s16le" in command_seen

    assert not converted_path.exists()
    assert source.is_file()


def test_failed_conversion_is_sanitized_and_removes_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "invalid.ogg"
    source.write_bytes(b"OggS-invalid")
    monkeypatch.setattr(
        "tech_ai.integrations.speech.conversion._ffmpeg_executable",
        lambda: "bundled-ffmpeg",
    )
    monkeypatch.setattr(
        "tech_ai.integrations.speech.conversion.subprocess.run",
        lambda *_args, **_options: subprocess.CompletedProcess([], 1, b"", b"private error"),
    )

    with (
        pytest.raises(SpeechTranscriptionError, match="converter"),
        transcription_audio(source, content_type="audio/ogg"),
    ):
        pass

    assert list(tmp_path.glob("*.wav")) == []


def test_missing_converter_has_install_instruction(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(_name: str) -> None:
        raise ImportError("missing")

    monkeypatch.setattr(
        "tech_ai.integrations.speech.conversion.importlib.import_module",
        missing,
    )
    with pytest.raises(ConfigurationError, match="uv sync --extra azure"):
        _ffmpeg_executable()
