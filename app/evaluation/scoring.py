from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from app.langgraph.classifier import IntentClassification
from app.evaluation.pricing import ModelPricing
from app.evaluation.schema import EvaluationCase


def _normalize(value: object | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).strip().lower().split())
    return normalized or None


@dataclass
class CaseScore:
    case_id: str
    structured_success: bool
    fallback: bool
    intent_correct: bool
    item_correct: bool
    quantity_correct: bool
    operation_correct: bool
    clarification_correct: bool
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def score_case(
    case: EvaluationCase,
    result: IntentClassification | None,
    *,
    latency_ms: float | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    pricing: ModelPricing | None = None,
    error: str | None = None,
) -> CaseScore:
    if result is None:
        return CaseScore(
            case_id=case.id,
            structured_success=False,
            fallback=True,
            intent_correct=False,
            item_correct=case.expected_item_name is None,
            quantity_correct=case.expected_quantity is None,
            operation_correct=case.expected_operation is None,
            clarification_correct=False,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=(input_tokens + output_tokens) if input_tokens is not None and output_tokens is not None else None,
            estimated_cost_usd=pricing.cost(input_tokens, output_tokens) if pricing else None,
            error=error,
        )

    item_correct = True if case.expected_item_name is None else _normalize(result.item_name or result.referenced_item) == _normalize(case.expected_item_name)
    quantity_correct = True if case.expected_quantity is None else result.quantity == case.expected_quantity
    operation_correct = True if case.expected_operation is None else result.operation == case.expected_operation
    return CaseScore(
        case_id=case.id,
        structured_success=True,
        fallback=False,
        intent_correct=result.intent == case.expected_intent,
        item_correct=item_correct,
        quantity_correct=quantity_correct,
        operation_correct=operation_correct,
        clarification_correct=result.needs_clarification == case.expected_clarification,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=(input_tokens + output_tokens) if input_tokens is not None and output_tokens is not None else None,
        estimated_cost_usd=pricing.cost(input_tokens, output_tokens) if pricing else None,
        error=error,
    )


def summarize_scores(model: str, scores: list[CaseScore], *, mode: str, pricing: ModelPricing | None = None, classifier_rate: float = 1.0) -> dict[str, Any]:
    if not 0 <= classifier_rate <= 1:
        raise ValueError("classifier_rate must be between 0 and 1")
    total = len(scores)
    def rate(field: str) -> float | None:
        return sum(bool(getattr(score, field)) for score in scores) / total if total else None

    input_tokens = sum(score.input_tokens or 0 for score in scores) if any(score.input_tokens is not None for score in scores) else None
    output_tokens = sum(score.output_tokens or 0 for score in scores) if any(score.output_tokens is not None for score in scores) else None
    total_tokens = sum(score.total_tokens or 0 for score in scores) if any(score.total_tokens is not None for score in scores) else None
    total_cost = sum(score.estimated_cost_usd or 0 for score in scores) if any(score.estimated_cost_usd is not None for score in scores) else None
    avg_latency = (sum(score.latency_ms or 0 for score in scores) / total) if total and any(score.latency_ms is not None for score in scores) else None
    per_classification = (total_cost / total) if total_cost is not None and total else None
    return {
        "model": model,
        "mode": mode,
        "case_count": total,
        "passed_cases": sum(score.intent_correct and score.structured_success for score in scores),
        "failed_cases": sum(not (score.intent_correct and score.structured_success) for score in scores),
        "metrics": {
            "intent_accuracy": rate("intent_correct"),
            "item_accuracy": rate("item_correct"),
            "quantity_accuracy": rate("quantity_correct"),
            "operation_accuracy": rate("operation_correct"),
            "clarification_accuracy": rate("clarification_correct"),
            "structured_output_success_rate": rate("structured_success"),
            "fallback_rate": rate("fallback"),
        },
        "latency_ms": {"average": avg_latency},
        "tokens": {"input": input_tokens, "output": output_tokens, "total": total_tokens},
        "estimated_cost_usd": {
            "per_classification": per_classification,
            "per_100": per_classification * 100 if per_classification is not None else None,
            "per_1000_classifications": per_classification * 1000 if per_classification is not None else None,
            "per_1000_customer_messages": per_classification * 1000 * classifier_rate if per_classification is not None else None,
            "classifier_rate": classifier_rate,
            "pricing_configured": pricing is not None and pricing.input_per_million is not None and pricing.output_per_million is not None,
        },
        "failures": [score.as_dict() for score in scores if not (score.intent_correct and score.structured_success)],
        "cases": [score.as_dict() for score in scores],
    }

