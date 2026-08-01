from __future__ import annotations

from langchain_core.messages import HumanMessage

from app.core.config import settings
from app.core.llm import build_llm


class OpenAIService:
    """Service responsible for communicating with the OpenAI model."""

    def __init__(self) -> None:
        self._llm = None

    def _get_llm(self):
        if not settings.OPENAI_API_KEY.strip():
            return None
        if self._llm is None:
            self._llm = build_llm()
        return self._llm

    async def generate_response(self, prompt: str) -> str:
        llm = self._get_llm()
        if llm is None:
            return ""

        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content
        return content if isinstance(content, str) else str(content)


openai_service = OpenAIService()
