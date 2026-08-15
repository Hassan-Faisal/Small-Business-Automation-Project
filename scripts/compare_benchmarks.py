"""Compare completed benchmark JSON files against configurable quality gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_THRESHOLDS = {"intent_accuracy": 0.95, "structured_output_success_rate": 0.99, "clarification_accuracy": 0.98}


def load_results(paths: list[str | Path]) -> list[dict[str, Any]]:
    return [json.loads(Path(path).read_text(encoding="utf-8")) for path in paths]


def eligible_models(results: list[dict[str, Any]], thresholds: dict[str, float] | None = None) -> list[dict[str, Any]]:
    thresholds = thresholds or DEFAULT_THRESHOLDS
    eligible = []
    for result in results:
        metrics = result.get("metrics", {})
        if all(float(metrics.get(metric, 0.0) or 0.0) >= threshold for metric, threshold in thresholds.items()):
            eligible.append(result)
    return eligible


def format_comparison(results: list[dict[str, Any]], thresholds: dict[str, float] | None = None) -> str:
    eligible = eligible_models(results, thresholds)
    lines = []
    for result in results:
        metrics = result.get("metrics", {})
        cost = result.get("estimated_cost_usd", {}).get("per_1000_classifications")
        latency = result.get("latency_ms", {}).get("average")
        lines.append(
            f"{result.get('model')} ({result.get('mode')}): "
            f"intent={metrics.get('intent_accuracy')!s}, "
            f"entity={metrics.get('item_accuracy')!s}, "
            f"structured={metrics.get('structured_output_success_rate')!s}, "
            f"clarification={metrics.get('clarification_accuracy')!s}, "
            f"avg_latency_ms={latency!s}, cost_1000_classifications={cost!s}"
        )
    if eligible:
        priced = [result for result in eligible if result.get("estimated_cost_usd", {}).get("per_1000_classifications") is not None]
        lines.append(f"Quality-gate eligible models: {', '.join(str(item.get('model')) for item in eligible)}")
        if priced:
            cheapest = min(priced, key=lambda result: float(result["estimated_cost_usd"]["per_1000_classifications"]))
            lines.append(f"Candidate for cheapest-model review: {cheapest.get('model')} (validate configured pricing before selection).")
        else:
            lines.append("Quality-gate eligible models have no configured prices; no cost-based candidate selected.")
    else:
        lines.append("No model meets all configured quality thresholds; do not select on price alone.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare completed classifier benchmark result files.")
    parser.add_argument("results", nargs="+", type=Path)
    parser.add_argument("--intent-threshold", type=float, default=DEFAULT_THRESHOLDS["intent_accuracy"])
    parser.add_argument("--structured-threshold", type=float, default=DEFAULT_THRESHOLDS["structured_output_success_rate"])
    parser.add_argument("--clarification-threshold", type=float, default=DEFAULT_THRESHOLDS["clarification_accuracy"])
    args = parser.parse_args()
    thresholds = {"intent_accuracy": args.intent_threshold, "structured_output_success_rate": args.structured_threshold, "clarification_accuracy": args.clarification_threshold}
    print(format_comparison(load_results(args.results), thresholds))


if __name__ == "__main__":
    main()

