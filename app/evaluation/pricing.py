from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPricing:
    """USD per one million tokens; enter current provider pricing explicitly."""

    input_per_million: float | None = None
    output_per_million: float | None = None

    def __post_init__(self) -> None:
        for name, value in (("input_per_million", self.input_per_million), ("output_per_million", self.output_per_million)):
            if value is not None and value < 0:
                raise ValueError(f"{name} must be non-negative")

    def cost(self, input_tokens: int | None, output_tokens: int | None) -> float | None:
        if input_tokens is None or output_tokens is None:
            return None
        if self.input_per_million is None or self.output_per_million is None:
            return None
        return (input_tokens / 1_000_000 * self.input_per_million) + (output_tokens / 1_000_000 * self.output_per_million)


def scale_cost(cost_per_classification: float | None, classifications: int) -> float | None:
    if cost_per_classification is None:
        return None
    return cost_per_classification * classifications


def customer_message_cost(
    cost_per_classification: float | None,
    classifier_rate: float,
    customer_messages: int = 1000,
) -> float | None:
    """Estimate cost when only a fraction of customer messages invoke classification."""
    if cost_per_classification is None:
        return None
    if not 0 <= classifier_rate <= 1:
        raise ValueError("classifier_rate must be between 0 and 1")
    return cost_per_classification * customer_messages * classifier_rate

