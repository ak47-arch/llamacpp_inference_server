"""Response types for the LLM workflow client."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowResult:
    """The result of a single LLM workflow invocation.

    Attributes:
        text: Raw response text from the model.
        data: Parsed JSON when output mode is ``json`` and parsing succeeds,
              otherwise ``None``.
        model_id: The logical model name used (from the resolved model entry).
        latency_ms: Round-trip latency in milliseconds.
        success: Whether the call completed without error.
        error: Human-readable error message when ``success`` is ``False``, else ``None``.
        fallback_used: Whether a fallback function was invoked after the primary call failed.
    """

    text: str = ""
    data: dict | list | None = None
    model_id: str = ""
    latency_ms: float = 0.0
    success: bool = True
    error: str | None = None
    fallback_used: bool = False