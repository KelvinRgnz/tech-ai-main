"""Entrevista determinística para perguntas ainda sem informação clínica útil."""

import re

_VAGUE_PATTERNS = (
    re.compile(r"\b(estou|tô|to) (tendo|com) (um )?problema\b", re.IGNORECASE),
    re.compile(r"\b(pode|consegue) me ajudar\b", re.IGNORECASE),
    re.compile(r"\bpreciso de ajuda\b", re.IGNORECASE),
    re.compile(r"\bn[aã]o estou (bem|me sentindo bem)\b", re.IGNORECASE),
    re.compile(r"\bo que eu tenho\b", re.IGNORECASE),
    re.compile(r"\bestou me sentindo mal\b", re.IGNORECASE),
)

CLARIFICATION_ANSWER = (
    "Claro. Para entender melhor o que está acontecendo, conte:\n\n"
    "1. Qual é o principal sintoma ou dificuldade?\n"
    "2. Quando começou e houve piora?\n"
    "3. Onde ocorre e qual a intensidade de 0 a 10?\n"
    "4. Há outros sinais, como febre, falta de ar, dor, tontura ou fraqueza?\n\n"
    "Com esses detalhes, consigo pesquisar evidências mais relacionadas ao relato."
)


def needs_clarification(question: str) -> bool:
    normalized = " ".join(question.strip().split())
    return any(pattern.search(normalized) for pattern in _VAGUE_PATTERNS)
