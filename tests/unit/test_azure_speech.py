import json
from pathlib import Path

import pytest

from tech_ai.errors import ConfigurationError, SpeechTranscriptionError
from tech_ai.integrations.speech.azure import (
    AzureSpeechTranscriber,
    _detail_timings,
    _speech_sdk,
)


def test_detail_timings_normalizes_word_offsets() -> None:
    payload = json.dumps(
        {
            "NBest": [
                {
                    "Offset": 5_000_000,
                    "Duration": 20_000_000,
                    "Words": [
                        {"Word": "olá", "Offset": 5_000_000, "Duration": 3_000_000},
                        {"Word": "mundo", "Offset": 15_000_000, "Duration": 5_000_000},
                    ],
                }
            ]
        }
    )

    words, end = _detail_timings(payload)

    assert [word.text for word in words] == ["olá", "mundo"]
    assert words[0].offset_seconds == 0.5
    assert words[1].duration_seconds == 0.5
    assert end == 2.5


@pytest.mark.parametrize("raw", ["", "[]", '{"NBest": []}', '{"NBest": [null]}'])
def test_detail_timings_tolerates_missing_optional_fields(raw: str) -> None:
    assert _detail_timings(raw) == ((), 0.0)


def test_missing_sdk_has_install_instruction(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(_name: str) -> None:
        raise ImportError("missing")

    monkeypatch.setattr("tech_ai.integrations.speech.azure.importlib.import_module", missing)
    with pytest.raises(ConfigurationError, match="uv sync --extra azure"):
        _speech_sdk()


def test_transcriber_rejects_unsupported_or_missing_file(tmp_path: Path) -> None:
    transcriber = AzureSpeechTranscriber(
        key="secret",
        region="brazilsouth",
        max_audio_seconds=120,
        max_concurrent_requests=1,
    )
    audio = tmp_path / "audio.flac"
    audio.write_bytes(b"audio")
    with pytest.raises(SpeechTranscriptionError, match="Formato"):
        transcriber.transcribe(audio, content_type="audio/flac")
    with pytest.raises(SpeechTranscriptionError, match="indisponível"):
        transcriber.transcribe(tmp_path / "missing.wav", content_type="audio/wav")
