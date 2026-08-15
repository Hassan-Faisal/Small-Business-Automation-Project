from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.evaluation.pricing import ModelPricing
from app.evaluation.routing import RouteAssessment
from app.evaluation.schema import EvaluationCase
from app.langgraph.classifier import IntentClassification


PRODUCTION_INTENT_NORMALIZATIONS = {
    "cart_total": "view_cart",
    "set_quantity": "change_quantity",
    "increment_quantity": "change_quantity",
    "decrement_quantity": "change_quantity",
}


def _normalize(value: object | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).strip().lower().split())
    return normalized or None


def normalize_production_intent(intent: str | None) -> tuple[str | None, str | None]:
    normalized = _normalize(intent)
    target = PRODUCTION_INTENT_NORMALIZATIONS.get(normalized or "", normalized)
    mapping = f"{normalized} -> {target}" if normalized in PRODUCTION_INTENT_NORMALIZATIONS else None
    return target, mapping


@dataclass
class CaseScore:
    case_id: str
    structured_success: bool
    fallback: bool
    provider_success: bool
    provider_timeout: bool
    fallback_used: bool
    actual: dict[str, Any] | None
    evaluated_by_classifier: bool
    production_route: str
    classifier_expected_to_be_invoked: bool
    deterministic_shortcut: bool
    deterministic_safe: bool
    safety_warning: str | None
    raw_intent_correct: bool | None
    normalized_intent_correct: bool | None
    semantic_equivalence_applied: bool
    semantic_equivalence: str | None
    intent_correct: bool
    item_correct: bool | None
    quantity_correct: bool | None
    operation_correct: bool | None
    clarification_correct: bool | None
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _actual_dict(result: IntentClassification | None) -> dict[str, Any] | None:
    return result.model_dump(mode="json") if result is not None else None


def _is_timeout(error: str | None) -> bool:
    return "timeout" in (error or "").lower()


def score_case(
    case: EvaluationCase,
    result: IntentClassification | None,
    *,
    route: RouteAssessment | None = None,
    latency_ms: float | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    pricing: ModelPricing | None = None,
    error: str | None = None,
) -> CaseScore:
    route = route or RouteAssessment("semantic_classifier", True, False)
    evaluated = route.classifier_expected_to_be_invoked
    provider_success = result is not None
    actual = _actual_dict(result)
    raw_correct: bool | None = None
    normalized_correct: bool | None = None
    equivalence = None
    item_correct = quantity_correct = operation_correct = clarification_correct = None
    if result is not None:
        raw_correct = result.intent == case.expected_intent
        normalized_intent, equivalence = normalize_production_intent(result.intent)
        expected_normalized, _ = normalize_production_intent(case.expected_intent)
        normalized_correct = normalized_intent == expected_normalized
        item_correct = True if case.expected_item_name is None else _normalize(result.item_name or result.referenced_item) == _normalize(case.expected_item_name)
        quantity_correct = True if case.expected_quantity is None else result.quantity == case.expected_quantity
        operation_correct = True if case.expected_operation is None else result.operation == case.expected_operation
        clarification_correct = result.needs_clarification == case.expected_clarification
    elif evaluated:
        raw_correct = normalized_correct = False
        item_correct = case.expected_item_name is None
        quantity_correct = case.expected_quantity is None
        operation_correct = case.expected_operation is None
        clarification_correct = False
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    return CaseScore(
        case_id=case.id,
        structured_success=provider_success,
        fallback=evaluated and not provider_success,
        provider_success=provider_success,
        provider_timeout=evaluated and not provider_success and _is_timeout(error),
        fallback_used=evaluated and not provider_success,
        actual=actual,
        evaluated_by_classifier=evaluated,
        production_route=route.production_route,
        classifier_expected_to_be_invoked=evaluated,
        deterministic_shortcut=route.deterministic_shortcut,
        deterministic_safe=route.deterministic_safe,
        safety_warning=route.safety_warning,
        raw_intent_correct=raw_correct,
        normalized_intent_correct=normalized_correct,
        semantic_equivalence_applied=bool(equivalence and raw_correct is False and normalized_correct is True),
        semantic_equivalence=equivalence if raw_correct is False and normalized_correct is True else None,
        intent_correct=bool(raw_correct),
        item_correct=item_correct,
        quantity_correct=quantity_correct,
        operation_correct=operation_correct,
        clarification_correct=clarification_correct,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=pricing.cost(input_tokens, output_tokens) if pricing else None,
        error=error,
    )


def _metric(scores: list[CaseScore], field: str) -> dict[str, Any]:
    applicable = [score for score in scores if getattr(score, field) is not None]
    correct = sum(bool(getattr(score, field)) for score in applicable)
    return {"correct": correct, "total": len(applicable), "accuracy": correct / len(applicable) if applicable else None}


def _view(scores: list[CaseScore]) -> dict[str, Any]:
    return {
        "case_count": len(scores),
        "intent": _metric(scores, "raw_intent_correct"),
        "normalized_intent": _metric(scores, "normalized_intent_correct"),
        "item": _metric(scores, "item_correct"),
        "quantity": _metric(scores, "quantity_correct"),
        "operation": _metric(scores, "operation_correct"),
        "clarification": _metric(scores, "clarification_correct"),
        "structured_output": _metric(scores, "structured_success"),
    }


def summarize_scores(model: str, scores: list[CaseScore], *, mode: str, pricing: ModelPricing | None = None, classifier_rate: float = 1.0) -> dict[str, Any]:
    if not 0 <= classifier_rate <= 1:
        raise ValueError("classifier_rate must be between 0 and 1")
    total = len(scores)
    evaluated = [score for score in scores if score.evaluated_by_classifier]
    successful = [score for score in evaluated if score.provider_success]
    deterministic = [score for score in scores if not score.classifier_expected_to_be_invoked]
    total_cost = sum(score.estimated_cost_usd or 0 for score in scores) if any(score.estimated_cost_usd is not None for score in scores) else None
    measured_per_call = total_cost / len(successful) if total_cost is not None and successful else None
    usage_cases = sum(score.input_tokens is not None and score.output_tokens is not None and score.total_tokens is not None for score in successful)
    usage_complete = usage_cases == len(successful)
    observed_rate = len(evaluated) / total if total else 0.0
    per_1000 = measured_per_call * 1000 if measured_per_call is not None else None
    return {
        "model": model,
        "mode": mode,
        "case_count": total,
        "passed_cases": sum(score.intent_correct and score.structured_success for score in scores),
        "failed_cases": sum(not (score.intent_correct and score.structured_success) for score in scores),
        "metrics": {
            "intent_accuracy": _metric(scores, "intent_correct")["accuracy"],
            "item_accuracy": _metric(scores, "item_correct")["accuracy"],
            "quantity_accuracy": _metric(scores, "quantity_correct")["accuracy"],
            "operation_accuracy": _metric(scores, "operation_correct")["accuracy"],
            "clarification_accuracy": _metric(scores, "clarification_correct")["accuracy"],
            "structured_output_success_rate": _metric(scores, "structured_success")["accuracy"],
            "fallback_rate": sum(score.fallback_used for score in scores) / total if total else None,
        },
        "quality_views": {
            "raw_all_case_classifier": _view(evaluated),
            "provider_success_only": _view(successful),
            "production_reachable_semantic_classifier": _view(evaluated),
            "production_reachable_provider_success_only": _view(successful),
            "deterministic_bypass": {"correct": len(deterministic), "total": total, "percentage": len(deterministic) / total if total else None},
        },
        "latency_ms": {"average_successful_provider_call": (sum(score.latency_ms for score in successful if score.latency_ms is not None) / len([score for score in successful if score.latency_ms is not None])) if any(score.latency_ms is not None for score in successful) else None},
        "provider_calls": {"successful_structured_classifications": len(successful), "fallback_or_failed_cases": sum(score.fallback_used for score in scores)},
        "token_telemetry": {"cases_with_usage": usage_cases, "successful_without_usage": len(successful) - usage_cases, "complete_for_successful_calls": usage_complete},
        "tokens": {"input": sum(score.input_tokens or 0 for score in scores) if any(score.input_tokens is not None for score in scores) else None, "output": sum(score.output_tokens or 0 for score in scores) if any(score.output_tokens is not None for score in scores) else None, "total": sum(score.total_tokens or 0 for score in scores) if any(score.total_tokens is not None for score in scores) else None},
        "estimated_cost_usd": {
            "actual_benchmark_cost": total_cost,
            "measured_cost_per_successful_classifier_invocation": measured_per_call,
            "per_classification": measured_per_call,
            "per_100": measured_per_call * 100 if measured_per_call is not None else None,
            "per_1000_classifications": per_1000,
            "per_1000_classifier_invocations": per_1000,
            "per_1000_customer_messages_manual_rate": measured_per_call * 1000 * classifier_rate if measured_per_call is not None else None,
            "per_1000_customer_messages_observed_rate": measured_per_call * 1000 * observed_rate if measured_per_call is not None else None,
            "per_1000_customer_messages": measured_per_call * 1000 * classifier_rate if measured_per_call is not None else None,
            "classifier_rate": classifier_rate,
            "observed_classifier_rate": observed_rate,
            "pricing_configured": pricing is not None and pricing.input_per_million is not None and pricing.output_per_million is not None,
            "cost_coverage_complete": usage_complete and pricing is not None,
        },
        "failures": [score.as_dict() for score in scores if score.evaluated_by_classifier and not (score.intent_correct and score.structured_success)],
        "cases": [score.as_dict() for score in scores],
    }
