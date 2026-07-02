"""WorkflowClient — the main entry point for calling LLM workflows.

Usage::

    client = WorkflowClient("config/workflows.yaml")
    result = client.complete_text("classify_tweet", prompt=tweet_text)
"""

from __future__ import annotations

import importlib
import json
import time
from pathlib import Path
from typing import Any, Callable

import requests

from .config import WorkflowConfig
from .errors import LLMBadResponseError, LLMTimeoutError, LLMUnavailableError
from .schemas import WorkflowResult


class WorkflowClient:
    """A shared LLM workflow client driven by a per-project YAML config.

    Args:
        config_path: Path to a ``workflows.yaml`` file. See ``WorkflowConfig``.
    """

    def __init__(self, config_path: str | Path) -> None:
        self._config = WorkflowConfig.from_yaml(config_path)
        self._fallback_cache: dict[str, Callable] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def complete(
        self,
        workflow_name: str,
        *,
        messages: list[dict[str, str]] | None = None,
        user_prompt: str | None = None,
        system: str | None = None,
        **override_params: Any,
    ) -> WorkflowResult:
        """Execute an LLM workflow.

        Args:
            workflow_name: Key in the ``workflows`` section of ``workflows.yaml``.
            messages: Full OpenAI messages array. Mutually exclusive with
                      ``user_prompt``/``system``.
            user_prompt: Shortcut for ``{"role": "user", "content": prompt}``.
            system: Shortcut for a system message. Prepended when ``messages`` is
                    not provided; ignored otherwise.
            **override_params: Override any ``WorkflowDef`` field at call time
                (e.g. ``temperature=0.5``, ``max_tokens=512``).

        Returns:
            A ``WorkflowResult`` with parsed response, timing, and error info.
        """
        # 1. Resolve the workflow definition (merged with overrides)
        workflow = self._resolve_workflow(workflow_name, override_params)

        # 2. Resolve the model entry
        model_entry = self._config.models[workflow["model_ref"]]

        # 3. Build the messages array
        request_messages = self._build_messages(
            workflow.get("system_prompt"),
            messages=messages,
            user_prompt=user_prompt,
            system=system,
        )

        # 4. Build and send the request
        url = f"{model_entry.url.rstrip('/')}/v1/chat/completions"
        payload: dict[str, Any] = {
            "model": model_entry.model,
            "messages": request_messages,
            "temperature": workflow["temperature"],
            "max_tokens": workflow["max_tokens"],
        }

        start = time.monotonic()
        try:
            resp = requests.post(url, json=payload, timeout=model_entry.timeout)
            resp.raise_for_status()
        except requests.exceptions.ConnectionError as exc:
            return self._fallback_or_error(
                workflow_name, workflow,
                error=f"Connection refused: {exc}",
                user_prompt=user_prompt,
            )
        except requests.exceptions.Timeout as exc:
            return self._fallback_or_error(
                workflow_name, workflow,
                error=f"Timed out after {model_entry.timeout}s: {exc}",
                user_prompt=user_prompt,
            )
        except requests.exceptions.HTTPError as exc:
            latency = (time.monotonic() - start) * 1000
            return WorkflowResult(
                success=False,
                error=f"HTTP {resp.status_code}: {exc}",
                latency_ms=latency,
            )
        except requests.exceptions.RequestException as exc:
            return self._fallback_or_error(
                workflow_name, workflow,
                error=str(exc),
                user_prompt=user_prompt,
            )

        latency = (time.monotonic() - start) * 1000
        body = resp.json()

        # 5. Extract response text
        try:
            raw_text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            return self._fallback_or_error(
                workflow_name, workflow,
                error=f"Unexpected response structure: {exc}",
                raw_text=str(body),
                user_prompt=user_prompt,
            )

        result = WorkflowResult(
            text=raw_text,
            model_id=model_entry.model,
            latency_ms=latency,
        )

        # 6. Parse JSON output if requested
        if workflow["output"] == "json":
            parsed = self._try_parse_json(raw_text)
            if parsed is None:
                return self._fallback_or_error(
                    workflow_name, workflow,
                    error="Failed to parse response as JSON",
                    raw_text=raw_text,
                    user_prompt=user_prompt,
                )
            result.data = parsed

        return result

    def complete_text(
        self,
        workflow_name: str,
        prompt: str,
        system: str | None = None,
        **override_params: Any,
    ) -> WorkflowResult:
        """Convenience wrapper around :meth:`complete` using ``user_prompt``.

        Args:
            workflow_name: Key in ``workflows.yaml``.
            prompt: User message content.
            system: Optional system message.
            **override_params: Override any ``WorkflowDef`` field.

        Returns:
            ``WorkflowResult``.
        """
        return self.complete(
            workflow_name,
            user_prompt=prompt,
            system=system,
            **override_params,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_workflow(
        self,
        name: str,
        overrides: dict[str, Any],
    ) -> dict[str, Any]:
        """Return the workflow definition dict, merged with call-site overrides."""
        if name not in self._config.workflows:
            raise KeyError(
                f"Unknown workflow {name!r}. "
                f"Available: {list(self._config.workflows.keys())}"
            )
        base = self._config.workflows[name].model_dump()
        base.update(overrides)
        return base  # type: ignore[return-value]

    def _build_messages(
        self,
        config_system: str | None,
        *,
        messages: list[dict[str, str]] | None,
        user_prompt: str | None,
        system: str | None,
    ) -> list[dict[str, str]]:
        """Build the messages array for the API call."""
        if messages is not None:
            return messages  # caller supplied the full array

        result: list[dict[str, str]] = []

        # System message: caller < config default < none
        system_text = system if system is not None else config_system
        if system_text:
            result.append({"role": "system", "content": system_text})

        if user_prompt is not None:
            result.append({"role": "user", "content": user_prompt})

        return result

    def _try_parse_json(self, text: str) -> dict | list | None:
        """Attempt to extract and parse a JSON payload from model output.

        Tries the whole body first; falls back to the first ``{...}`` or ``[...]``
        block found via regex.
        """
        text = text.strip()

        # Direct parse
        try:
            return json.loads(text)  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            pass

        # Try extracting a JSON object
        import re

        for pattern in (r"\{.*\}", r"\[.*\]"):
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))  # type: ignore[no-any-return]
                except json.JSONDecodeError:
                    continue

        return None

    def _resolve_fallback(self, fallback_path: str) -> Callable | None:
        """Lazily import and cache a fallback function from a ``module.function`` path."""
        if fallback_path == "none":
            return None
        if fallback_path in self._fallback_cache:
            return self._fallback_cache[fallback_path]

        module_path, _, func_name = fallback_path.rpartition(".")
        if not module_path:
            raise ValueError(
                f"Invalid fallback path {fallback_path!r}: expected 'module.function'"
            )

        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            raise ImportError(
                f"Cannot import fallback module {module_path!r} "
                f"(from {fallback_path!r}): {exc}"
            ) from exc

        func = getattr(module, func_name, None)
        if func is None:
            raise AttributeError(
                f"Module {module_path!r} has no function {func_name!r} "
                f"(from {fallback_path!r})"
            )

        self._fallback_cache[fallback_path] = func
        return func

    def _fallback_or_error(
        self,
        workflow_name: str,
        workflow: dict[str, Any],
        *,
        error: str,
        raw_text: str = "",
        user_prompt: str | None = None,
    ) -> WorkflowResult:
        """Try the configured fallback, or return an error result.

        If a fallback function is configured, it is called with the
        ``user_prompt`` text (or the raw response text if no prompt was given).
        If the fallback itself raises, its exception message is reflected
        in the error result.
        """
        fallback_path = workflow.get("fallback", "none")
        fallback_fn = self._resolve_fallback(fallback_path)

        if fallback_fn is None:
            return WorkflowResult(
                text=raw_text,
                success=False,
                error=error,
            )

        fallback_input = user_prompt if user_prompt is not None else raw_text
        try:
            fallback_result = fallback_fn(fallback_input)
            return WorkflowResult(
                data=fallback_result if isinstance(fallback_result, (dict, list)) else None,
                text=str(fallback_result) if not isinstance(fallback_result, (dict, list)) else "",
                model_id="fallback",
                success=True,
                fallback_used=True,
            )
        except Exception as exc:
            return WorkflowResult(
                text=raw_text,
                success=False,
                error=f"Primary: {error}. Fallback also failed: {exc}",
                fallback_used=True,
            )