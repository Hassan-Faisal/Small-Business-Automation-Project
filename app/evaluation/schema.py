from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)
    expected_intent: str = Field(min_length=1)
    expected_item_name: str | None = None
    expected_quantity: int | None = Field(default=None, ge=1, le=50)
    expected_operation: str | None = None
    expected_clarification: bool = False
    notes: str = ""


class EvaluationDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    description: str
    source_dataset: str | None = None
    selection_policy: str | None = None
    cases: list[EvaluationCase] = Field(min_length=1)

    @classmethod
    def from_path(cls, path: str | Path) -> "EvaluationDataset":
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        dataset = cls.model_validate(payload)
        ids = [case.id for case in dataset.cases]
        duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
        if duplicates:
            raise ValueError(f"Duplicate evaluation case IDs: {', '.join(duplicates)}")
        return dataset


def validate_dataset(path: str | Path) -> EvaluationDataset:
    """Load and validate a dataset, including unique case IDs."""
    try:
        return EvaluationDataset.from_path(path)
    except (OSError, json.JSONDecodeError, ValidationError, ValueError):
        raise

