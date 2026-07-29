from __future__ import annotations

from dataclasses import dataclass

STATIC_RAG_TOPICS = {
    "policy",
    "policies",
    "faq",
    "faqs",
    "delivery hours",
    "operating hours",
    "delivery area",
    "delivery areas",
    "delivery window",
    "delivery windows",
    "delivery guidance",
    "refund policy",
    "cancellation policy",
    "subscription policy",
    "payment methods",
    "allergen guidance",
    "food safety",
    "support",
    "escalation",
}

DYNAMIC_BUSINESS_TOPICS = {
    "today's menu",
    "today menu",
    "menu",
    "price",
    "prices",
    "availability",
    "available",
    "order status",
    "order",
    "subscription",
    "subscriptions",
    "cart",
    "address",
    "skip meal",
    "meal skip",
}

DYNAMIC_BUSINESS_PHRASES = (
    "today's menu",
    "today menu",
    "weekly menu",
    "what is today's menu",
    "what is the price",
    "how much is",
    "is lunch available",
    "where is my order",
    "what subscription do i have",
    "skip tomorrow's meal",
    "can you skip tomorrow's meal",
)


@dataclass(frozen=True)
class RagBoundaryDecision:
    use_rag: bool
    reason: str | None = None


def _normalize(question: str) -> str:
    return " ".join(question.lower().split())


def is_dynamic_business_question(question: str) -> bool:
    normalized = _normalize(question)
    return any(phrase in normalized for phrase in DYNAMIC_BUSINESS_PHRASES)


def is_static_policy_question(question: str) -> bool:
    normalized = _normalize(question)
    return any(topic in normalized for topic in STATIC_RAG_TOPICS)


def decide_rag_usage(question: str) -> RagBoundaryDecision:
    if is_dynamic_business_question(question):
        return RagBoundaryDecision(
            use_rag=False,
            reason="dynamic_business_data",
        )

    if is_static_policy_question(question):
        return RagBoundaryDecision(
            use_rag=True,
            reason="static_policy_question",
        )

    return RagBoundaryDecision(
        use_rag=True,
        reason="general_policy_question",
    )
