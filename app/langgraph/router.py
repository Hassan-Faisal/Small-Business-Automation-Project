from __future__ import annotations

from app.langgraph.parsing import infer_intent
from app.langgraph.state import Intent


def classify_intent(message: str) -> Intent:
    return infer_intent(message)
