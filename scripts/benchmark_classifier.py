"""Run the structured-intent evaluation dataset offline or with explicit opt-in.

Offline is the default and never constructs an OpenAI service. Live mode requires
RUN_OPENAI_BENCHMARK=1 and an API key, and must be invoked explicitly with --live.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from typing import Any
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.evaluation.pricing import ModelPricing
from app.evaluation.schema import EvaluationCase, EvaluationDataset, validate_dataset
from app.evaluation.scoring import CaseScore, score_case, summarize_scores
from app.langgraph.classifier import IntentClassification, SemanticContext, StructuredIntentClassifier


DEFAULT_DATASET = PROJECT_ROOT / "app" / "evaluation" / "dataset.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "benchmark_results"

class BenchmarkQuotaError(RuntimeError):
    """Live benchmark stopped because the provider reported unavailable credits."""


def _is_insufficient_quota_error(exc: BaseException) -> bool:
    """Identify billing exhaustion without treating ordinary 429 rate limits as quota failures."""
    details = [
        str(exc),
        getattr(exc, "code", None),
        getattr(exc, "type", None),
        getattr(exc, "body", None),
        getattr(exc, "response", None),
    ]
    text = " ".join(str(value) for value in details if value is not None).lower()
    return "insufficient_quota" in text or "you have no credits remaining" in text


class OfflineReferenceLLM:
    """Deterministic gold replay used only to validate harness plumbing offline."""

    def __init__(self, case: EvaluationCase) -> None:
        self.case = case

    async def generate_structured_response(self, prompt: str, schema: type[IntentClassification]) -> IntentClassification:
        return schema(
            intent=self.case.expected_intent,
            item_name=self.case.expected_item_name,
            quantity=self.case.expected_quantity,
            operation=self.case.expected_operation,
            confidence=1.0,
            needs_clarification=self.case.expected_clarification,
        )


def _context_for_classifier(case: EvaluationCase) -> SemanticContext:
    raw = case.context
    cart = raw.get("cart", [])
    pending = raw.get("pending_options", [])
    candidates = raw.get("catalog_candidates", [])
    recent_turns = list(raw.get("recent_turns", [])) if isinstance(raw.get("recent_turns", []), list) else []
    active_item = raw.get("recent_active_item")
    if active_item:
        recent_turns.append({"role": "user", "content": f"recent active item: {active_item}"})
    return SemanticContext(
        message=case.message,
        recent_turns=recent_turns,
        cart_items=[item for item in cart if isinstance(item, dict)],
        pending_clarification={"pending_action": raw["pending_action"]} if raw.get("pending_action") else None,
        pending_options=[option if isinstance(option, dict) else {"name": option} for option in pending],
        catalog_items=[item if isinstance(item, dict) else {"name": item} for item in candidates],
        active_order=dict(raw.get("active_order", {})) if isinstance(raw.get("active_order", {}), dict) else {},
    )


async def _classify_case(case: EvaluationCase, *, model: str, live: bool) -> tuple[IntentClassification | None, float, str | None]:
    context = _context_for_classifier(case)
    if live:
        from app.core.config import settings
        from app.services.openai_service import OpenAIService

        if not settings.OPENAI_API_KEY.strip():
            raise RuntimeError("Live benchmark requires OPENAI_API_KEY; no request was made.")
        classifier = StructuredIntentClassifier(llm=OpenAIService(model=model, max_retries=0), raise_provider_exceptions=True)
    else:
        classifier = StructuredIntentClassifier(llm=OfflineReferenceLLM(case))
    started = time.perf_counter()
    try:
        result = await classifier.classify(context, message_id=f"benchmark-{case.id}")
        return result, (time.perf_counter() - started) * 1000, None
    except Exception as exc:
        if live and _is_insufficient_quota_error(exc):
            raise BenchmarkQuotaError(f"Model {model} reported insufficient_quota/no credits while processing case {case.id}.") from exc
        return None, (time.perf_counter() - started) * 1000, type(exc).__name__


def _safe_filename(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", model).strip("._") or "model"


async def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    if args.live and args.env_gate != "1":
        raise RuntimeError("Live benchmark blocked. Set RUN_OPENAI_BENCHMARK=1 and pass --live deliberately.")
    dataset = validate_dataset(args.dataset)
    pricing = ModelPricing(args.input_price, args.output_price) if args.input_price is not None or args.output_price is not None else None
    scores: list[CaseScore] = []
    for case in dataset.cases:
        result, latency_ms, error = await _classify_case(case, model=args.model, live=args.live)
        scores.append(score_case(case, result, latency_ms=latency_ms, pricing=pricing, error=error))
    summary = summarize_scores(args.model, scores, mode="live" if args.live else "offline_reference", pricing=pricing, classifier_rate=args.classifier_rate)
    summary["dataset"] = {"name": dataset.name, "version": dataset.version, "path": str(Path(args.dataset))}
    summary["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    summary["warning"] = "Offline reference mode replays gold outputs to validate the harness; it is not a model-quality benchmark." if not args.live else "Live benchmark explicitly enabled by the operator."
    output_path = Path(args.output_dir) / f"{_safe_filename(args.model)}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate StructuredIntentClassifier offline or with explicit live opt-in.")
    parser.add_argument("--model", default="offline-reference", help="Candidate model name; no provider is used in default offline mode.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--live", action="store_true", help="Enable real provider calls; requires RUN_OPENAI_BENCHMARK=1.")
    parser.add_argument("--input-price", type=float, default=None, help="USD per million input tokens.")
    parser.add_argument("--output-price", type=float, default=None, help="USD per million output tokens.")
    parser.add_argument("--classifier-rate", type=float, default=1.0, help="Fraction of customer messages invoking the classifier, e.g. 0.4.")
    parser.add_argument("--env-gate", default=None, help=argparse.SUPPRESS)
    return parser


def main() -> None:
    import os

    parser = build_parser()
    args = parser.parse_args()
    args.env_gate = os.getenv("RUN_OPENAI_BENCHMARK")
    try:
        summary = asyncio.run(run_benchmark(args))
    except BenchmarkQuotaError as exc:
        print("BENCHMARK STOPPED: API credits are unavailable; no partial model-quality result was saved.", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
    except RuntimeError as exc:
        parser.error(str(exc))
    print(json.dumps({"model": summary["model"], "mode": summary["mode"], "case_count": summary["case_count"], "metrics": summary["metrics"]}, indent=2))
    print(f"Saved: {Path(args.output_dir) / (_safe_filename(args.model) + '.json')}")


if __name__ == "__main__":
    main()

