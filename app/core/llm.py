from langchain_openai import ChatOpenAI

from app.core.config import settings


def build_llm(model: str | None = None, *, max_retries: int = 1) -> ChatOpenAI:
    return ChatOpenAI(
        model=(model or settings.OPENAI_MODEL),
        api_key=settings.OPENAI_API_KEY,
        temperature=0,
        max_retries=max_retries,
        request_timeout=10,
    )
