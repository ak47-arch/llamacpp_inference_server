"""Configuration models for the LLM workflow client.

Parses a per-project ``config/workflows.yaml`` file that defines available models
and named workflows. See ``PLAN_shared_llm_client.md`` for the full schema.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator


_ENV_VAR_RE = re.compile(r"\$\{([^}]+)\}")


def _resolve_env_vars(value: str) -> str:
    """Replace ``${VAR_NAME}`` placeholders with ``os.environ`` values.

    Raises ``KeyError`` if a referenced variable is not set.
    """

    def _sub(match: re.Match) -> str:
        var = match.group(1)
        return os.environ[var]

    return _ENV_VAR_RE.sub(_sub, value)


class ModelEntry(BaseModel):
    """A single model definition in the ``models`` section of ``workflows.yaml``.

    Attributes:
        url: The OpenAI-compatible base URL (e.g. ``http://host.containers.internal:8012``).
             Supports ``${VAR}`` environment variable substitution.
        model: The logical model name sent in the ``model`` field of the request body.
        timeout: Request timeout in seconds.
    """

    url: str
    model: str
    timeout: int = Field(default=180, ge=1)

    @field_validator("url")
    @classmethod
    def _resolve_url(cls, v: str) -> str:
        return _resolve_env_vars(v)


class WorkflowDef(BaseModel):
    """A single workflow definition in the ``workflows`` section.

    Attributes:
        model_ref: Key referencing a model in the top-level ``models`` dict.
        temperature: Sampling temperature (``0.0`` for deterministic).
        max_tokens: Maximum tokens in the response.
        output: ``"json"`` to auto-parse the response body, ``"text"`` to return raw.
        system_prompt: Optional default system message. Caller can override via ``system=``.
        fallback: A ``module.function`` import path for fallback logic, or ``"none"``.
    """

    model_ref: str
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=256, ge=1)
    output: Literal["text", "json"] = "text"
    system_prompt: str | None = None
    fallback: str = "none"


class WorkflowConfig(BaseModel):
    """Top-level configuration parsed from ``workflows.yaml``.

    Attributes:
        models: Mapping of model alias → ``ModelEntry``.
        workflows: Mapping of workflow name → ``WorkflowDef``.
    """

    models: dict[str, ModelEntry]
    workflows: dict[str, WorkflowDef]

    @classmethod
    def from_yaml(cls, path: str | Path) -> WorkflowConfig:
        """Load and validate a ``workflows.yaml`` file.

        Args:
            path: Path to the YAML configuration file.

        Returns:
            A validated ``WorkflowConfig`` instance.

        Raises:
            FileNotFoundError: If the file does not exist.
            yaml.YAMLError: If the file contains invalid YAML.
            pydantic.ValidationError: If the structure does not match the schema.
        """
        path = Path(path)
        with path.open("r") as f:
            raw: dict[str, Any] = yaml.safe_load(f)
        return cls.model_validate(raw)