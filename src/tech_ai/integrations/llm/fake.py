"""Implementação determinística para testes e demonstrações leves."""

from __future__ import annotations

from collections.abc import Sequence


class FakeLlmClient:
    """Retorna respostas configuradas e registra o último prompt."""

    def __init__(self, response: str | Sequence[str] = "Resposta simulada.") -> None:
        self._responses = (response,) if isinstance(response, str) else tuple(response)
        if not self._responses:
            raise ValueError("FakeLlmClient exige ao menos uma resposta.")
        self.response = self._responses[0]
        self.system_prompt: str | None = None
        self.user_prompt: str | None = None
        self.call_count = 0

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        index = min(self.call_count, len(self._responses) - 1)
        self.call_count += 1
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return self._responses[index]
