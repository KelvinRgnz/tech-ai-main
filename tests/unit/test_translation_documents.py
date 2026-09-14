from __future__ import annotations

from tech_ai.integrations.translation.documents import (
    excerpt_from_knowledge_text,
    localize_knowledge_text,
    localize_search_result,
    parse_knowledge_text,
)
from tech_ai.models.knowledge import KnowledgeSearchResult


class StubTranslator:
    def translate(self, text: str, *, source: str, target: str) -> str:
        del source
        return f"{target}:{text}"


def test_parse_and_excerpt_english_medquad_document() -> None:
    text = (
        "Medical topic: Stress\n"
        "Question: What is (are) Stress ?\n"
        "Answer: Stress is a response of the body."
    )

    sections = parse_knowledge_text(text)

    assert sections.topic == "Stress"
    assert sections.question == "What is (are) Stress ?"
    assert sections.answer == "Stress is a response of the body."
    assert excerpt_from_knowledge_text(text) == "Stress is a response of the body."


def test_localize_knowledge_text_rewrites_labels_and_content() -> None:
    text = (
        "Medical topic: Diabetes\n"
        "Question: What are the symptoms of diabetes?\n"
        "Answer: Thirst and fatigue can occur."
    )

    localized = localize_knowledge_text(text, StubTranslator())

    assert localized == (
        "Tópico médico: pt:Diabetes\n"
        "Pergunta: pt:What are the symptoms of diabetes?\n"
        "Resposta: pt:Thirst and fatigue can occur."
    )


def test_localize_search_result_translates_focus_and_keeps_portuguese_text() -> None:
    result = KnowledgeSearchResult(
        record_id="id-1",
        text="Tópico médico: Diabetes\nPergunta: Quais são os sintomas?\nResposta: Sede e cansaço.",
        metadata={"focus": "Diabetes", "source_url": "https://example.test"},
        distance=0.2,
    )

    localized = localize_search_result(result, StubTranslator())

    assert "Resposta: Sede e cansaço." in localized.text
    assert localized.focus == "pt:Diabetes"
    assert localized.record_id == "id-1"


def test_excerpt_returns_full_text_when_structure_is_missing() -> None:
    assert excerpt_from_knowledge_text("trecho livre") == "trecho livre"
    assert excerpt_from_knowledge_text("   ") is None


def test_localize_plain_english_block() -> None:
    localized = localize_knowledge_text("Stress is a response of the body.", StubTranslator())

    assert localized == "pt:Stress is a response of the body."
