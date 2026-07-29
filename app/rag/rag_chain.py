from __future__ import annotations

import logging

from app.rag.domain_boundary import decide_rag_usage, is_dynamic_business_question
from app.services.knowledge_manager import KnowledgeManager
from app.services.openai_service import OpenAIService

logger = logging.getLogger(__name__)


class RAGChain:
    """
    Retrieval-Augmented Generation pipeline for TiffinAI policy and FAQ support.
    """

    def __init__(self, knowledge_manager: KnowledgeManager | None = None):
        self.knowledge_manager = knowledge_manager
        self.retriever = None
        self.llm = OpenAIService()

        if knowledge_manager is not None:
            self.retriever = knowledge_manager.get_retriever()

    def build_prompt(self, question: str, context: str) -> str:
        """Build the prompt for the language model."""

        return f"""You are TiffinAI, a WhatsApp support assistant for a meal ordering business.

You answer only using the retrieved static policy and FAQ context below.

Rules:
- Use only the provided context.
- Never invent business details.
- If the context does not contain the answer, say that the information is not available and guide the customer to the business workflow or owner confirmation.
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
            return (
                "That question needs live menu, order, or customer data, so I cannot answer it from the policy documents. "
                "Please use the ordering workflow or ask the owner to check the live record."
            )
        return (
            "I could not find that information in the policy documents. Please ask the owner to confirm it."
        )

    async def ask(self, question: str) -> str:
        """Answer a user's question using Retrieval-Augmented Generation."""
        if self.retriever is None:
            return "I don't have knowledge access configured yet."

        decision = decide_rag_usage(question)
        if not decision.use_rag:
            logger.info(
                "rag_dynamic_question_blocked",
                extra={
                    "event": "rag_dynamic_question_blocked",
                    "reason": decision.reason,
                },
            )
            return self._safe_static_fallback(question)

        documents = self.retriever.invoke(question)
        context = "\n\n".join(document.page_content for document in documents)
        prompt = self.build_prompt(question=question, context=context)
        response = await self.llm.generate_response(prompt)
        return response
