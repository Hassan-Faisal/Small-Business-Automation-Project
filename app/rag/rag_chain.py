from __future__ import annotations

import logging

from app.rag.domain_boundary import decide_rag_usage, is_dynamic_business_question
from app.services.knowledge_manager import KnowledgeManager, KnowledgeManagerUnavailableError
from app.services.openai_service import OpenAIService

logger = logging.getLogger(__name__)
POLICY_FALLBACK = "I could not find that information in the TiffinAI policy documents. Please contact support."
POLICY_UNAVAILABLE_FALLBACK = "TiffinAI policy information is temporarily unavailable. Please contact support or try again shortly."


class RAGChain:
    """Retrieval-Augmented Generation pipeline for TiffinAI policy and FAQ support."""

    def __init__(self, knowledge_manager: KnowledgeManager | None = None, llm: OpenAIService | None = None):
        self.knowledge_manager = knowledge_manager
        self.retriever = None
        self.llm = llm or OpenAIService()
        self.last_call_metadata: dict[str, int | bool] = {"rag_invoked": False, "rag_generation_count": 0, "embedding_invoked": False}

    def build_prompt(self, question: str, context: str) -> str:
        return f"""You are TiffinAI, a WhatsApp support assistant for a meal ordering business.

You answer only using the retrieved static policy and FAQ context below.

Rules:
- Use only the provided context.
- Never invent business details.
- If the context does not contain the answer, reply exactly: {POLICY_FALLBACK}
- Never use this context as the source of truth for menu availability, meal prices, live order status, customer subscriptions, cart contents, delivery addresses, or any customer-specific data.
- If the customer asks about live or customer-specific data, direct them to the live business workflow instead of answering from policy docs.
- Keep the answer concise, accurate, and customer-friendly.

Context:
--------------------
{context}
--------------------

Customer Question:
{question}

Answer:
"""

    def _safe_static_fallback(self, question: str) -> str:
        if is_dynamic_business_question(question):
            return "That question needs live menu, order, or customer data. Please use the ordering workflow or contact support."
        return POLICY_FALLBACK

    def _get_retriever(self):
        if self.retriever is not None:
            return self.retriever
        if self.knowledge_manager is None:
            raise KnowledgeManagerUnavailableError("RAG knowledge manager is not configured.")
        self.retriever = self.knowledge_manager.get_retriever()
        return self.retriever

    async def ask(self, question: str) -> str:
        self.last_call_metadata = {"rag_invoked": True, "rag_generation_count": 0, "embedding_invoked": False}
        decision = decide_rag_usage(question)
        if not decision.use_rag:
            logger.info("rag_dynamic_question_blocked", extra={"event": "rag_dynamic_question_blocked", "reason": decision.reason})
            return self._safe_static_fallback(question)

        try:
            retriever = self._get_retriever()
        except KnowledgeManagerUnavailableError:
            logger.warning(
                "rag_retriever_unavailable",
                extra={"event": "rag_retriever_unavailable"},
            )
            return POLICY_UNAVAILABLE_FALLBACK
        except Exception:
            logger.exception(
                "rag_retriever_resolution_failed",
                extra={"event": "rag_retriever_resolution_failed"},
            )
            return POLICY_UNAVAILABLE_FALLBACK

        documents = retriever.invoke(question)
        self.last_call_metadata["embedding_invoked"] = True
        context = "\n\n".join(document.page_content for document in documents)
        if not context.strip():
            return POLICY_FALLBACK

        prompt = self.build_prompt(question=question, context=context)
        try:
            response = await self.llm.generate_response(prompt)
            self.last_call_metadata["rag_generation_count"] = 1
        except Exception:
            logger.exception("rag_llm_call_failed", extra={"event": "rag_llm_call_failed"})
            return POLICY_UNAVAILABLE_FALLBACK
        return response or POLICY_FALLBACK
