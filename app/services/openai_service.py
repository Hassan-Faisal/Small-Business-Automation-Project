from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.core.config import settings
from app.core.llm import build_llm



def extract_token_usage(response: Any) -> dict[str, int] | None:
    """Extract provider usage from LangChain/OpenAI response metadata."""
    candidates: list[Any] = [response]
    if isinstance(response, Mapping):
        candidates.extend(response.get(key) for key in ("usage_metadata", "response_metadata", "token_usage", "raw"))
    else:
        candidates.extend(getattr(response, key, None) for key in ("usage_metadata", "response_metadata", "token_usage"))
    candidates = [candidate for candidate in candidates if candidate is not None]

    def find(mapping: Mapping[str, Any], names: tuple[str, ...]) -> int | None:
        for name in names:
            value = mapping.get(name)
            if isinstance(value, int):
                return value
        for nested_key in ("token_usage", "usage", "usage_metadata"):
            nested = mapping.get(nested_key)
            if isinstance(nested, Mapping):
                found = find(nested, names)
                if found is not None:
                    return found
        return None

    for candidate in candidates:
        if isinstance(candidate, Mapping):
            input_tokens = find(candidate, ("input_tokens", "prompt_tokens", "input_token_count"))
            output_tokens = find(candidate, ("output_tokens", "completion_tokens", "output_token_count"))
            total_tokens = find(candidate, ("total_tokens", "total_token_count"))
            if input_tokens is not None or output_tokens is not None or total_tokens is not None:
                return {
                    "input_tokens": input_tokens or 0,
                    "output_tokens": output_tokens or 0,
                    "total_tokens": total_tokens if total_tokens is not None else (input_tokens or 0) + (output_tokens or 0),
                }
        else:
            usage = getattr(candidate, "usage_metadata", None) or getattr(candidate, "response_metadata", None)
            if isinstance(usage, Mapping):
                found = extract_token_usage(usage)
                if found is not None:
                    return found
    return None

class OpenAIService:
    """Service responsible for communicating with the OpenAI model."""

    def __init__(self, model: str | None = None, *, max_retries: int = 1, capture_usage: bool = False) -> None:
        self.model = (model or settings.OPENAI_MODEL).strip()
        self.max_retries = max_retries
        self.capture_usage = capture_usage
        self.last_usage: dict[str, int] | None = None
        self._llm = None

    def _get_llm(self):
        if not settings.OPENAI_API_KEY.strip():
            return None
        if self._llm is None:
            self._llm = build_llm(model=self.model, max_retries=self.max_retries)
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

        self.last_usage = None
        if not self.capture_usage:
            structured_llm = llm.with_structured_output(
                schema,
                method="json_schema",
                strict=True,
            )
            return await structured_llm.ainvoke([HumanMessage(content=prompt)])

        structured_llm = llm.with_structured_output(
            schema,
            method="json_schema",
            strict=True,
            include_raw=True,
        )
        envelope = await structured_llm.ainvoke([HumanMessage(content=prompt)])
        if isinstance(envelope, Mapping):
            self.last_usage = extract_token_usage(envelope.get("raw")) or extract_token_usage(envelope)
            return envelope.get("parsed")
        self.last_usage = extract_token_usage(envelope)
        return envelope

openai_service = OpenAIService()
