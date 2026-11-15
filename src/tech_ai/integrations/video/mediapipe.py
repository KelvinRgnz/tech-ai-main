"""Adaptador do MediaPipe Pose Landmarker para vídeos MP4 locais."""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

from tech_ai.errors import VideoAnalysisError
from tech_ai.integrations.video.client import PoseSample, VideoMovementAnalysis
from tech_ai.integrations.video.movement import movement_events

_LEFT_SHOULDER = 11
_RIGHT_SHOULDER = 12
_LEFT_HIP = 23
_RIGHT_HIP = 24
_LEFT_KNEE = 25
_RIGHT_KNEE = 26
_LEFT_ANKLE = 27
_RIGHT_ANKLE = 28


class MediaPipeVideoMovementAnalyzer:
    def __init__(self, model_path: Path, *, sample_fps: float = 5.0) -> None:
        if not model_path.is_file():
            raise VideoAnalysisError(
                f"Modelo de pose não encontrado em {model_path}."
            )
        self._model_path = model_path
        self._sample_fps = sample_fps

    def analyze(self, path: Path) -> VideoMovementAnalysis:
        os.environ.setdefault("GLOG_minloglevel", "2")
        os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
        try:
            import cv2
            import mediapipe as mp
        except ImportError as error:
            raise VideoAnalysisError(
                "Instale o extra de vídeo com: uv sync --dev --extra video."
            ) from error

        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            raise VideoAnalysisError("Não foi possível abrir o vídeo MP4.")
        source_fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if source_fps <= 0 or frame_count <= 0:
            capture.release()
            raise VideoAnalysisError("O vídeo não possui duração ou taxa de quadros válida.")
        duration = frame_count / source_fps
        frame_step = max(1, round(source_fps / self._sample_fps))
        analyzed_frames = 0
        samples: list[PoseSample] = []

        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(self._model_path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        try:
            with mp.tasks.vision.PoseLandmarker.create_from_options(options) as landmarker:
                frame_index = 0
                while capture.isOpened():
                    success, frame = capture.read()
                    if not success:
                        break
                    if frame_index % frame_step == 0:
                        timestamp_ms = round(frame_index * 1000 / source_fps)
                        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        result = landmarker.detect_for_video(
                            mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb),
                            timestamp_ms,
                        )
                        analyzed_frames += 1
                        sample = _pose_sample(result, timestamp_ms / 1000)
                        if sample is not None:
                            samples.append(sample)
                    frame_index += 1
        except (RuntimeError, ValueError) as error:
            raise VideoAnalysisError("O modelo de pose não concluiu a análise.") from error
        finally:
            capture.release()

        if not samples:
            raise VideoAnalysisError("Nenhuma pose corporal confiável foi detectada no vídeo.")
        repetitions, events = movement_events(samples)
        angles = [sample.knee_angle_degrees for sample in samples]
        return VideoMovementAnalysis(
            duration,
            analyzed_frames,
            len(samples),
            repetitions,
            min(angles),
            max(angles),
            events,
        )


def _pose_sample(result: Any, timestamp_seconds: float) -> PoseSample | None:
    if not result.pose_landmarks:
        return None
    landmarks = result.pose_landmarks[0]
    side = _best_side(landmarks)
    shoulder, hip, knee, ankle = side
    if min(point.visibility or 0.0 for point in side) < 0.5:
        return None
    return PoseSample(
        timestamp_seconds,
        _angle(hip, knee, ankle),
        _inclination(shoulder, hip),
    )


def _best_side(landmarks: Any) -> tuple[Any, Any, Any, Any]:
    left = tuple(
        landmarks[index]
        for index in (_LEFT_SHOULDER, _LEFT_HIP, _LEFT_KNEE, _LEFT_ANKLE)
    )
    right = tuple(
        landmarks[index]
        for index in (_RIGHT_SHOULDER, _RIGHT_HIP, _RIGHT_KNEE, _RIGHT_ANKLE)
    )
    left_visibility = sum(point.visibility or 0.0 for point in left)
    right_visibility = sum(point.visibility or 0.0 for point in right)
    return left if left_visibility >= right_visibility else right


def _angle(first: Any, vertex: Any, last: Any) -> float:
    vector_a = (first.x - vertex.x, first.y - vertex.y)
    vector_b = (last.x - vertex.x, last.y - vertex.y)
    norm = math.hypot(*vector_a) * math.hypot(*vector_b)
    if norm == 0:
        return 0.0
    cosine = max(
        -1.0,
        min(
            1.0,
            sum(a * b for a, b in zip(vector_a, vector_b, strict=True)) / norm,
        ),
    )
    return math.degrees(math.acos(cosine))


def _inclination(shoulder: Any, hip: Any) -> float:
    horizontal = shoulder.x - hip.x
    vertical = hip.y - shoulder.y
    return math.degrees(math.atan2(abs(horizontal), abs(vertical)))
