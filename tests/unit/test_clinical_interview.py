import pytest

from tech_ai.services.clinical_interview import needs_clarification


@pytest.mark.parametrize(
    "question",
    [
        "Estou tendo um problema, consegue me ajudar?",
        "Não estou me sentindo bem",
        "Preciso de ajuda",
        "O que eu tenho?",
    ],
)
def test_detects_vague_requests(question: str) -> None:
    assert needs_clarification(question)


@pytest.mark.parametrize(
    "question",
    [
        "Quais são os sintomas da diabetes?",
        "Estou com falta de ar há dois dias",
        "O que causa pressão alta?",
    ],
)
def test_keeps_specific_medical_questions(question: str) -> None:
    assert not needs_clarification(question)
