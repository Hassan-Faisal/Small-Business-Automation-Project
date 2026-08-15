from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.core.config import settings
from app.core.llm import build_llm


class OpenAIService:
    """Service responsible for communicating with the OpenAI model."""

    def __init__(self, model: str | None = None) -> None:
        self.model = (model or settings.OPENAI_MODEL).strip()
        self._llm = None

    def _get_llm(self):
        if not settings.OPENAI_API_KEY.strip():
            return None
        if self._llm is None:
            self._llm = build_llm(model=self.model)
        return self._llm

    async def generate_response(self, prompt: str) -> str:
        llm = self._get_llm()
        if llm is None:
            return ""

        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content
        return content if isinstance(content, str) else str(content)

    async def generate_structured_response(self, prompt: str, schema: type[BaseModel]) -> Any:
        """Invoke OpenAI with provider-enforced structured output."""
        llm = self._get_llm()
        if llm is None:
            return None

        structured_llm = llm.with_structured_output(
            schema,
            method="json_schema",
            strict=True,
        )
        return await structured_llm.ainvoke([HumanMessage(content=prompt)])

openai_service = OpenAIService()
