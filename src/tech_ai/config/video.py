"""Configuração local da análise experimental de vídeo."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from tech_ai.errors import ConfigurationError


def _boolean(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError("TECH_AI_VIDEO_ENABLED deve ser true ou false.")


@dataclass(frozen=True, slots=True)
class VideoSettings:
    enabled: bool = False
    model_path: Path = Path(".data/models/pose_landmarker_lite.task")
    sample_fps: float = 5.0

    def __post_init__(self) -> None:
        if not str(self.model_path).strip():
            raise ConfigurationError("TECH_AI_VIDEO_MODEL_PATH inválido.")
        if not 1.0 <= self.sample_fps <= 15.0:
            raise ConfigurationError("TECH_AI_VIDEO_SAMPLE_FPS deve ficar entre 1 e 15.")

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> VideoSettings:
        values = os.environ if environment is None else environment
        try:
            sample_fps = float(values.get("TECH_AI_VIDEO_SAMPLE_FPS", "5"))
        except ValueError as error:
            raise ConfigurationError("TECH_AI_VIDEO_SAMPLE_FPS deve ser numérico.") from error
        return cls(
            enabled=_boolean(values.get("TECH_AI_VIDEO_ENABLED", "false")),
            model_path=Path(
                values.get(
                    "TECH_AI_VIDEO_MODEL_PATH",
                    ".data/models/pose_landmarker_lite.task",
                ).strip()
            ),
            sample_fps=sample_fps,
        )
