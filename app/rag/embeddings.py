from __future__ import annotations

import hashlib

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from app.core.config import settings


class _DeterministicEmbeddings(Embeddings):
    def _vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [round(byte / 255.0, 6) for byte in digest[:32]]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


if settings.OPENAI_API_KEY:
    embeddings: Embeddings = OpenAIEmbeddings(
        model=settings.OPENAI_EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
        max_retries=1,
        request_timeout=10,
    )
else:
    embeddings = _DeterministicEmbeddings()
