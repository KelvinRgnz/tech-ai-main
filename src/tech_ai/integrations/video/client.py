"""Contrato independente de biblioteca para análise de movimento."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class PoseSample:
    timestamp_seconds: float
    knee_angle_degrees: float
    trunk_inclination_degrees: float


@dataclass(frozen=True, slots=True)
class MovementEvent:
    kind: str
    timestamp_seconds: float
    description: str


@dataclass(frozen=True, slots=True)
class VideoMovementAnalysis:
    duration_seconds: float
    analyzed_frames: int
    frames_with_pose: int
    repetitions: int
    minimum_knee_angle: float
    maximum_knee_angle: float
    events: tuple[MovementEvent, ...]

    @property
    def pose_coverage(self) -> float:
        if self.analyzed_frames == 0:
            return 0.0
        return self.frames_with_pose / self.analyzed_frames


class VideoMovementAnalyzer(Protocol):
    def analyze(self, path: Path) -> VideoMovementAnalysis: ...
