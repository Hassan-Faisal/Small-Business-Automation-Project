from __future__ import annotations

import asyncio
import json
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.evaluation.pricing import ModelPricing, customer_message_cost
from app.evaluation.schema import EvaluationCase, validate_dataset
from app.evaluation.scoring import score_case, summarize_scores
from app.langgraph.classifier import IntentClassification
from app.services.openai_service import OpenAIService, extract_token_usage
from scripts import benchmark_classifier
from scripts.benchmark_classifier import DEFAULT_DATASET, BenchmarkQuotaError, _is_insufficient_quota_error, run_benchmark
from scripts.compare_benchmarks import eligible_models, format_comparison


def test_dataset_schema_and_unique_ids() -> None:
    dataset = validate_dataset(DEFAULT_DATASET)
    assert len(dataset.cases) == 100
    assert len({case.id for case in dataset.cases}) == len(dataset.cases)
    assert all(case.message and case.expected_intent for case in dataset.cases)


def test_duplicate_case_ids_are_rejected(tmp_path: Path) -> None:
    payload = {"name": "x", "version": "1", "description": "x", "cases": [
        {"id": "same", "message": "hello", "expected_intent": "greeting"},
        {"id": "same", "message": "hi", "expected_intent": "greeting"},
    ]}
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        validate_dataset(path)


def test_scoring_and_cost_math() -> None:
    case = EvaluationCase(id="x", message="two biryani", expected_intent="add_item", expected_item_name="Chicken Biryani", expected_quantity=2, expected_operation="add")
    result = IntentClassification(intent="add_item", item_name=" chicken  biryani ", quantity=2, operation="add", confidence=0.9)
    score = score_case(case, result, input_tokens=100, output_tokens=50, pricing=ModelPricing(1.0, 2.0))
    summary = summarize_scores("candidate", [score], mode="live", pricing=ModelPricing(1.0, 2.0), classifier_rate=0.4)
    assert score.item_correct and score.quantity_correct and score.operation_correct
    assert score.total_tokens == 150
    assert score.estimated_cost_usd == pytest.approx(0.0002)
    assert summary["estimated_cost_usd"]["per_1000_classifications"] == pytest.approx(0.2)
    assert customer_message_cost(0.0002, 0.4) == pytest.approx(0.08)


def test_contextual_item_comparison_uses_expected_entity() -> None:
    case = EvaluationCase(id="ctx", message="acha 2 krdo", context={"cart": [{"name": "Aloo Paratha with Raita", "quantity": 1}]}, expected_intent="change_quantity", expected_item_name="Aloo Paratha with Raita", expected_quantity=2, expected_operation="set")
    result = IntentClassification(intent="change_quantity", referenced_item="Aloo Paratha with Raita", quantity=2, operation="set", confidence=0.9)
    assert score_case(case, result).item_correct


def test_offline_benchmark_writes_gold_replay_without_provider(tmp_path: Path) -> None:
    args = Namespace(model="offline-test", dataset=DEFAULT_DATASET, output_dir=tmp_path, live=False, input_price=None, output_price=None, classifier_rate=0.4, env_gate=None)
    summary = asyncio.run(run_benchmark(args))
    assert summary["mode"] == "offline_reference"
    assert summary["tokens"]["total"] is None
    assert summary["estimated_cost_usd"]["per_1000_classifications"] is None
    assert (tmp_path / "offline-test.json").exists()


def test_live_mode_requires_explicit_environment_gate(tmp_path: Path) -> None:
    args = Namespace(model="candidate", dataset=DEFAULT_DATASET, output_dir=tmp_path, live=True, input_price=None, output_price=None, classifier_rate=1.0, env_gate=None)
    with pytest.raises(RuntimeError, match="RUN_OPENAI_BENCHMARK=1"):
        asyncio.run(run_benchmark(args))


def test_comparison_never_selects_unpriced_model() -> None:
    def result(model: str, cost: float | None) -> dict:
        return {"model": model, "metrics": {"intent_accuracy": 0.96, "structured_output_success_rate": 1.0, "clarification_accuracy": 0.99}, "estimated_cost_usd": {"per_1000_classifications": cost}}
    results = [result("unpriced", None), result("priced", 1.0)]
    assert [item["model"] for item in eligible_models(results)] == ["unpriced", "priced"]
    assert "Candidate for cheapest-model review: priced" in format_comparison(results)


def test_pricing_rejects_negative_values() -> None:
    with pytest.raises(ValueError):
        ModelPricing(-1, 1)

def test_quota_detection_distinguishes_billing_from_rate_limit() -> None:
    class QuotaError(Exception):
        code = "insufficient_quota"

    assert _is_insufficient_quota_error(QuotaError("429")) is True
    assert _is_insufficient_quota_error(RuntimeError("You have no credits remaining")) is True
    assert _is_insufficient_quota_error(RuntimeError("429 rate limit; try again later")) is False


def test_production_retry_default_is_preserved() -> None:
    from app.services.openai_service import OpenAIService

    assert OpenAIService(model="production").max_retries == 1
    assert OpenAIService(model="benchmark", max_retries=0).max_retries == 0


def test_classifier_provider_exception_propagation_is_opt_in() -> None:
    class FailingLLM:
        async def generate_structured_response(self, prompt, schema):
            raise RuntimeError("You have no credits remaining")

    StructuredIntentClassifier = benchmark_classifier.StructuredIntentClassifier

    assert asyncio.run(StructuredIntentClassifier(FailingLLM()).classify("hello")) is None
    with pytest.raises(RuntimeError, match="no credits"):
        asyncio.run(StructuredIntentClassifier(FailingLLM(), raise_provider_exceptions=True).classify("hello"))


def test_live_quota_aborts_after_first_case_without_partial_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    async def quota_case(case, *, model, live):
        nonlocal calls
        calls += 1
        raise BenchmarkQuotaError(f"Model {model} reported insufficient_quota/no credits while processing case {case.id}.")

    monkeypatch.setattr(benchmark_classifier, "_classify_case", quota_case)
    dataset_path = tmp_path / "semantic.json"
    dataset_path.write_text(json.dumps({"name": "semantic", "version": "1", "description": "x", "cases": [{"id": "semantic", "message": "same as before but two", "context": {"cart": [{"name": "Chicken Biryani", "quantity": 1}]}, "expected_intent": "change_quantity"}]}), encoding="utf-8")
    args = Namespace(model="quota-model", dataset=dataset_path, output_dir=tmp_path, live=True, input_price=1.0, output_price=1.0, classifier_rate=1.0, env_gate="1")
    with pytest.raises(BenchmarkQuotaError, match="insufficient_quota"):
        asyncio.run(run_benchmark(args))
    assert calls == 1
    assert not (tmp_path / "quota-model.json").exists()


def test_live_rate_limit_is_recorded_as_failure_instead_of_billing_abort(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def rate_limited_case(case, *, model, live):
        return None, 2.0, "RateLimitError"

    monkeypatch.setattr(benchmark_classifier, "_classify_case", rate_limited_case)
    args = Namespace(model="rate-limit-model", dataset=DEFAULT_DATASET, output_dir=tmp_path, live=True, input_price=1.0, output_price=1.0, classifier_rate=1.0, env_gate="1")
    summary = asyncio.run(run_benchmark(args))
    assert summary["case_count"] == 100
    assert summary["failed_cases"] == 100
    assert (tmp_path / "rate-limit-model.json").exists()
def test_token_usage_extraction_supports_langchain_metadata_shapes() -> None:
    assert extract_token_usage(SimpleNamespace(usage_metadata={"input_tokens": 120, "output_tokens": 30, "total_tokens": 150})) == {
        "input_tokens": 120, "output_tokens": 30, "total_tokens": 150
    }
    assert extract_token_usage({"response_metadata": {"token_usage": {"prompt_tokens": 200, "completion_tokens": 40, "total_tokens": 240}}}) == {
        "input_tokens": 200, "output_tokens": 40, "total_tokens": 240
    }


def test_structured_service_captures_raw_response_usage_without_changing_parsed_result(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeRunnable:
        async def ainvoke(self, messages):
            return {
                "raw": SimpleNamespace(usage_metadata={"input_tokens": 111, "output_tokens": 22, "total_tokens": 133}),
                "parsed": IntentClassification(intent="greeting", confidence=0.95),
                "parsing_error": None,
            }

    class FakeChatModel:
        def __init__(self):
            self.kwargs = None

        def with_structured_output(self, schema, **kwargs):
            self.kwargs = kwargs
            return FakeRunnable()

    service = OpenAIService(model="mock", capture_usage=True)
    service._llm = FakeChatModel()
    monkeypatch.setattr("app.services.openai_service.settings.OPENAI_API_KEY", "test-key")
    result = asyncio.run(service.generate_structured_response("hello", IntentClassification))
    assert isinstance(result, IntentClassification)
    assert service.last_usage == {"input_tokens": 111, "output_tokens": 22, "total_tokens": 133}
    assert service._llm.kwargs["include_raw"] is True


def test_actual_cost_and_projection_aggregate_provider_usage() -> None:
    case = EvaluationCase(id="cost", message="hello", expected_intent="greeting")
    result = IntentClassification(intent="greeting", confidence=0.9)
    pricing = ModelPricing(1.0, 2.0)
    first = score_case(case, result, input_tokens=100, output_tokens=50, pricing=pricing)
    second = score_case(case, result, input_tokens=200, output_tokens=100, pricing=pricing)
    summary = summarize_scores("mock", [first, second], mode="live", pricing=pricing, classifier_rate=0.4)
    assert summary["tokens"] == {"input": 300, "output": 150, "total": 450}
    assert summary["provider_calls"] == {"successful_structured_classifications": 2, "fallback_or_failed_cases": 0}
    assert summary["token_telemetry"]["complete_for_successful_calls"] is True
    assert summary["estimated_cost_usd"]["actual_benchmark_cost"] == pytest.approx(0.0006)
    assert summary["estimated_cost_usd"]["per_classification"] == pytest.approx(0.0003)
    assert summary["estimated_cost_usd"]["per_100"] == pytest.approx(0.03)
    assert summary["estimated_cost_usd"]["per_1000_classifications"] == pytest.approx(0.3)
    assert summary["estimated_cost_usd"]["per_1000_customer_messages"] == pytest.approx(0.12)


def test_success_and_fallback_telemetry_are_distinguished() -> None:
    case = EvaluationCase(id="telemetry", message="hello", expected_intent="greeting")
    result = IntentClassification(intent="greeting", confidence=0.9)
    successful = score_case(case, result, input_tokens=10, output_tokens=5, pricing=ModelPricing(1.0, 1.0))
    fallback = score_case(case, None, error="TimeoutError")
    summary = summarize_scores("mock", [successful, fallback], mode="live", pricing=ModelPricing(1.0, 1.0))
    assert summary["provider_calls"]["successful_structured_classifications"] == 1
    assert summary["provider_calls"]["fallback_or_failed_cases"] == 1
    assert summary["token_telemetry"]["successful_without_usage"] == 0
    assert summary["tokens"]["total"] == 15



def test_actual_prediction_and_timeout_are_persisted_separately() -> None:
    case = EvaluationCase(id="actual", message="set it to two", expected_intent="change_quantity", expected_quantity=2)
    result = IntentClassification(intent="set_quantity", referenced_item="Biryani", quantity=2, operation="set", confidence=0.8, needs_clarification=False)
    success = score_case(case, result)
    failed = score_case(case, None, error="APITimeoutError")
    assert success.actual["intent"] == "set_quantity"
    assert success.actual["quantity"] == 2
    assert success.semantic_equivalence_applied is True
    assert success.semantic_equivalence == "set_quantity -> change_quantity"
    assert failed.actual is None
    assert failed.provider_timeout is True
    assert failed.error == "APITimeoutError"


def test_route_probe_uses_production_shortcuts_without_case_ids() -> None:
    from app.evaluation.routing import assess_case
    quantity = EvaluationCase(id="q", message="acha 2 krdo", context={"cart": [{"name": "Aloo Paratha with Raita", "quantity": 1}]}, expected_intent="change_quantity")
    semantic = EvaluationCase(id="s", message="same as before but two", context={"cart": [{"name": "Aloo Paratha with Raita", "quantity": 1}]}, expected_intent="change_quantity")
    pending = EvaluationCase(id="p", message="the second one", context={"pending_options": ["A", "B"]}, expected_intent="add_item")
    assert assess_case(quantity).classifier_expected_to_be_invoked is False
    assert assess_case(quantity).deterministic_shortcut is True
    assert assess_case(semantic).classifier_expected_to_be_invoked is True
    assert assess_case(pending).classifier_expected_to_be_invoked is False


def test_quality_views_have_explicit_provider_and_reachability_denominators() -> None:
    from app.evaluation.routing import RouteAssessment
    case = EvaluationCase(id="v", message="x", expected_intent="greeting")
    deterministic = score_case(case, None, route=RouteAssessment("deterministic", False, False))
    semantic = score_case(case, IntentClassification(intent="greeting", confidence=1), route=RouteAssessment("semantic_classifier", True, False), input_tokens=100, output_tokens=50, pricing=ModelPricing(1, 2))
    summary = summarize_scores("m", [deterministic, semantic], mode="live", pricing=ModelPricing(1, 2), classifier_rate=0.4)
    assert summary["quality_views"]["raw_all_case_classifier"]["intent"] == {"correct": 1, "total": 1, "accuracy": 1.0}
    assert summary["quality_views"]["deterministic_bypass"] == {"correct": 1, "total": 2, "percentage": 0.5}
    assert summary["estimated_cost_usd"]["observed_classifier_rate"] == 0.5
    assert summary["estimated_cost_usd"]["per_1000_customer_messages_observed_rate"] == pytest.approx(0.1)


def test_zero_quantity_shortcut_is_marked_unsafe() -> None:
    from app.evaluation.routing import assess_case
    case = EvaluationCase(id="zero", message="add chicken biryani 0", context={}, expected_intent="add_item")
    route = assess_case(case)
    assert route.deterministic_shortcut is True
    assert route.deterministic_safe is False
    assert route.safety_warning
