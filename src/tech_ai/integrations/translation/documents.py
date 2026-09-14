"""Converte o formato MedQuAD indexado para rótulos e conteúdo em português."""

from __future__ import annotations

from dataclasses import dataclass

from tech_ai.integrations.translation.client import TranslationClient
from tech_ai.integrations.translation.language import looks_portuguese
from tech_ai.models.knowledge import KnowledgeSearchResult, MetadataValue

_TOPIC_MARKERS = ("Medical topic:", "Tópico médico:")
_QUESTION_MARKERS = ("Question:", "Pergunta:")
_ANSWER_MARKERS = ("Answer:", "Resposta:")


@dataclass(frozen=True, slots=True)
class KnowledgeSections:
    topic: str | None
    question: str | None
    answer: str | None


def parse_knowledge_text(text: str) -> KnowledgeSections:
    """Extrai tópico, pergunta e resposta do documento indexado."""

    topic, rest = _extract_prefixed_line(text.strip(), _TOPIC_MARKERS)
    question, rest = _extract_section(rest, _QUESTION_MARKERS, _ANSWER_MARKERS)
    answer = _extract_prefixed_block(rest, _ANSWER_MARKERS)
    if question is None and answer is None and topic is None:
        return KnowledgeSections(topic=None, question=None, answer=None)
    return KnowledgeSections(topic=topic, question=question, answer=answer)


def excerpt_from_knowledge_text(text: str) -> str | None:
    """Devolve o trecho de resposta, já no idioma do documento apresentado."""

    sections = parse_knowledge_text(text)
    if sections.answer:
        return sections.answer
    stripped = text.strip()
    return stripped or None


def localize_knowledge_text(text: str, translator: TranslationClient) -> str:
    """Traduz o corpo do documento e troca os rótulos para português."""

    sections = parse_knowledge_text(text)
    if sections.topic is None and sections.question is None and sections.answer is None:
        return _translate_if_needed(text, translator)
    parts: list[str] = []
    if sections.topic:
        parts.append(f"Tópico médico: {_translate_if_needed(sections.topic, translator)}")
    if sections.question:
        parts.append(f"Pergunta: {_translate_if_needed(sections.question, translator)}")
    if sections.answer:
        parts.append(f"Resposta: {_translate_if_needed(sections.answer, translator)}")
    return "\n".join(parts)


def localize_search_result(
    result: KnowledgeSearchResult,
    translator: TranslationClient,
) -> KnowledgeSearchResult:
    """Devolve uma cópia do resultado com texto e foco em português."""

    metadata: dict[str, MetadataValue] = dict(result.metadata)
    focus = result.focus
    if isinstance(focus, str) and focus.strip():
        metadata["focus"] = _translate_if_needed(focus, translator)
    return KnowledgeSearchResult(
        record_id=result.record_id,
        text=localize_knowledge_text(result.text, translator),
        metadata=metadata,
        distance=result.distance,
    )


def _translate_if_needed(text: str, translator: TranslationClient) -> str:
    stripped = text.strip()
    if not stripped or looks_portuguese(stripped):
        return stripped
    return translator.translate(stripped, source="en", target="pt").strip()


def _extract_prefixed_line(text: str, markers: tuple[str, ...]) -> tuple[str | None, str]:
    for marker in markers:
        if text.startswith(marker):
            remainder = text[len(marker) :].lstrip()
            line, separator, rest = remainder.partition("\n")
            return line.strip() or None, rest.lstrip() if separator else ""
    return None, text


def _extract_section(
    text: str,
    start_markers: tuple[str, ...],
    stop_markers: tuple[str, ...],
) -> tuple[str | None, str]:
    for marker in start_markers:
        if text.startswith(marker):
            remainder = text[len(marker) :].lstrip()
            for stop in stop_markers:
                before, found, after = remainder.partition(f"\n{stop}")
                if found:
                    return before.strip() or None, f"{stop}{after}"
            return remainder.strip() or None, ""
    return None, text


def _extract_prefixed_block(text: str, markers: tuple[str, ...]) -> str | None:
    stripped = text.strip()
    for marker in markers:
        if stripped.startswith(marker):
            return stripped[len(marker) :].strip() or None
    return None
