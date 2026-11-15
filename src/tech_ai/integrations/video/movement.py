"""Regras temporais experimentais para o exercício de sentar e levantar."""

from __future__ import annotations

from collections.abc import Sequence

from tech_ai.integrations.video.client import MovementEvent, PoseSample

SEATED_MAX_ANGLE = 115.0
STANDING_MIN_ANGLE = 150.0
PROLONGED_PHASE_SECONDS = 5.0


def movement_events(samples: Sequence[PoseSample]) -> tuple[int, tuple[MovementEvent, ...]]:
    """Conta ciclos sentado-em pé-sentado com histerese angular."""

    stable_state: str | None = None
    state_started = 0.0
    stood_since_seated = False
    standing_started: float | None = None
    repetitions = 0
    events: list[MovementEvent] = []

    for sample in samples:
        candidate = _state(sample.knee_angle_degrees)
        if candidate is None or candidate == stable_state:
            continue
        if stable_state is not None:
            duration = sample.timestamp_seconds - state_started
            if duration >= PROLONGED_PHASE_SECONDS:
                events.append(
                    MovementEvent(
                        "prolonged_phase",
                        state_started + PROLONGED_PHASE_SECONDS,
                        f"Permanência em posição {stable_state} por {duration:.1f} s.",
                    )
                )
        stable_state = candidate
        state_started = sample.timestamp_seconds
        if candidate == "em pé":
            stood_since_seated = True
            standing_started = sample.timestamp_seconds
            events.append(
                MovementEvent(
                    "standing",
                    sample.timestamp_seconds,
                    "Extensão dos joelhos compatível com posição em pé.",
                )
            )
        elif stood_since_seated:
            repetitions += 1
            stood_since_seated = False
            standing_started = None
            events.append(
                MovementEvent(
                    "repetition",
                    sample.timestamp_seconds,
                    f"Repetição {repetitions} concluída ao retornar à posição sentada.",
                )
            )

    if stood_since_seated and standing_started is not None and samples:
        events.append(
            MovementEvent(
                "incomplete_cycle",
                samples[-1].timestamp_seconds,
                "Ciclo incompleto: o vídeo terminou em posição em pé, sem retorno à "
                f"posição sentada após {standing_started:.1f} s.",
            )
        )

    return repetitions, tuple(events)


def _state(knee_angle: float) -> str | None:
    if knee_angle <= SEATED_MAX_ANGLE:
        return "sentada"
    if knee_angle >= STANDING_MIN_ANGLE:
        return "em pé"
    return None
