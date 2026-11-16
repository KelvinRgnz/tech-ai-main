from pathlib import Path

import pytest

from tech_ai.config.video import VideoSettings
from tech_ai.errors import ConfigurationError


def test_video_settings_are_disabled_by_default() -> None:
    settings = VideoSettings.from_environment({})

    assert settings.enabled is False
    assert settings.model_path == Path(".data/models/pose_landmarker_lite.task")
    assert settings.sample_fps == 5.0


@pytest.mark.parametrize("value", ["0", "16", "invalid"])
def test_video_settings_reject_invalid_sample_rate(value: str) -> None:
    with pytest.raises(ConfigurationError, match="SAMPLE_FPS"):
        VideoSettings.from_environment({"TECH_AI_VIDEO_SAMPLE_FPS": value})
