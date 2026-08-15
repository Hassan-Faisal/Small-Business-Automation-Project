from __future__ import annotations

import asyncio
import json
from argparse import Namespace
from pathlib import Path

import pytest

from app.evaluation.pricing import ModelPricing, customer_message_cost
from app.evaluation.schema import EvaluationCase, validate_dataset
from app.evaluation.scoring import score_case, summarize_scores
from app.langgraph.classifier import IntentClassification
from scripts.benchmark_classifier import DEFAULT_DATASET, run_benchmark
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
