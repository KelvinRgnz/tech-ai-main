from __future__ import annotations

from tech_ai.integrations.video.client import PoseSample
from tech_ai.integrations.video.movement import movement_events


def sample(second: float, knee_angle: float) -> PoseSample:
    return PoseSample(second, knee_angle, 10.0)


def test_counts_complete_sit_to_stand_cycles_with_hysteresis() -> None:
    repetitions, events = movement_events(
        (
            sample(0.0, 90.0),
            sample(1.0, 130.0),
            sample(2.0, 165.0),
            sample(3.0, 135.0),
            sample(4.0, 95.0),
            sample(5.0, 160.0),
            sample(6.0, 100.0),
        )
    )

    assert repetitions == 2
    assert [event.kind for event in events] == [
        "standing",
        "repetition",
        "standing",
        "repetition",
    ]
    assert events[-1].timestamp_seconds == 6.0


def test_reports_long_stable_phase_without_calling_it_clinical_anomaly() -> None:
    repetitions, events = movement_events(
        (sample(0.0, 90.0), sample(6.5, 165.0), sample(8.0, 90.0))
    )

    assert repetitions == 1
    assert events[0].kind == "prolonged_phase"
    assert events[0].timestamp_seconds == 5.0
    assert "6.5 s" in events[0].description


def test_does_not_count_incomplete_transition() -> None:
    repetitions, events = movement_events(
        (sample(0.0, 90.0), sample(1.0, 130.0), sample(2.0, 145.0))
    )

    assert repetitions == 0
    assert events == ()


def test_reports_cycle_that_ends_standing_as_incomplete() -> None:
    repetitions, events = movement_events(
        (sample(0.0, 90.0), sample(2.0, 165.0), sample(3.0, 170.0))
    )

    assert repetitions == 0
    assert [event.kind for event in events] == ["standing", "incomplete_cycle"]
    assert events[-1].timestamp_seconds == 3.0
    assert "após 2.0 s" in events[-1].description
