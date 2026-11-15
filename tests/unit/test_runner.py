from __future__ import annotations

import json
from pathlib import Path

import pytest

from tech_ai.integrations.speech.client import SpeechTranscript, WordTiming
from tech_ai.runner import main

from .test_model_artifact_service import valid_manifest, write_manifest


def test_inspect_model_command_prints_validated_manifest(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = write_manifest(tmp_path / "model-manifest.json")

    exit_code = main(["inspect-model", "--manifest", str(path)])

    assert exit_code == 0
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["artifact_id"] == "medquad-model-001"


def test_inspect_model_command_returns_error_for_invalid_manifest(tmp_path: Path) -> None:
    manifest = valid_manifest()
    manifest["artifact_type"] = "unknown"
    path = write_manifest(tmp_path / "model-manifest.json", manifest)

    assert main(["inspect-model", "--manifest", str(path)]) == 2


def test_check_speech_uses_fictitious_audio_without_exposing_key(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[tuple[Path, str]] = []

    class FakeTranscriber:
        def __init__(self, **_configuration: object) -> None:
            pass

        def transcribe(self, path: Path, *, content_type: str) -> SpeechTranscript:
            calls.append((path, content_type))
            return SpeechTranscript(
                "Relato fictício transcrito.",
                "pt-BR",
                4.2,
                (WordTiming("Relato", 0.0, 0.4),),
            )

    monkeypatch.setenv("TECH_AI_AZURE_SPEECH_ENABLED", "true")
    monkeypatch.setenv("TECH_AI_AZURE_SPEECH_KEY", "private-test-key")
    monkeypatch.setenv("TECH_AI_AZURE_SPEECH_REGION", "brazilsouth")
    monkeypatch.setattr(
        "tech_ai.integrations.speech.azure.AzureSpeechTranscriber",
        FakeTranscriber,
    )
    monkeypatch.setattr(
        "tech_ai.integrations.speech.azure.synthesize_fictitious_audio",
        lambda _path, **_configuration: None,
    )

    assert main(["check-speech"]) == 0

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["status"] == "ok"
    assert payload["transcript"] == "Relato fictício transcrito."
    assert "private-test-key" not in output
    assert calls[0][1] == "audio/wav"
