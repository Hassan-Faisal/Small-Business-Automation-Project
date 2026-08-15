from langchain_openai import ChatOpenAI

from app.core.config import settings


def build_llm(model: str | None = None) -> ChatOpenAI:
    return ChatOpenAI(
        model=(model or settings.OPENAI_MODEL),
        api_key=settings.OPENAI_API_KEY,
        temperature=0,
        max_retries=1,
        request_timeout=10,
    )
