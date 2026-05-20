"""Provider that calls any OpenAI-compatible REST API (OpenAI, Ollama, llama.cpp server, etc.)."""

import os
import time
from typing import Optional

import requests

from . import monitoring
from .local_server_runtime import ensure_managed_server

from .provider_base import (
    BaseProvider,
    CompletionResult,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


class OpenAICompatibleProvider(BaseProvider):
    def __init__(
        self,
        model_id: str,
        base_url: str,
        model_name: str,
        api_key: Optional[str] = None,
        default_params: Optional[dict] = None,
        managed_server: Optional[dict] = None,
        input_modalities: Optional[set[str] | list[str] | tuple[str, ...]] = None,
    ):
        self.model_id = model_id
        self.provider_name = "openai_compatible"
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.api_key = api_key
        self.default_params = default_params or {}
        self.managed_server = managed_server
        self._managed_runtime_ready = False
        declared_modalities = set(input_modalities or {"text"})
        invalid_modalities = declared_modalities - {"text", "image", "audio"}
        if invalid_modalities:
            invalid_value = sorted(invalid_modalities)[0]
            raise ValueError(f"Unsupported input modality '{invalid_value}'")
        self._declared_input_modalities = declared_modalities

    def warmup(self) -> None:
        if not self.managed_server:
            return
        ensure_managed_server(
            base_url=self.base_url,
            binary_path=self.managed_server["binary_path"],
            model_path=self.managed_server["model_path"],
            model_name=self.model_name,
            model_id=self.model_id,
            server_config=self.managed_server,
            default_params=self.default_params,
        )
        self._managed_runtime_ready = True

    def resolved_mmproj_path(self) -> Optional[str]:
        server_config = self.managed_server or {}
        env_name = server_config.get("mmproj_path_env")
        if env_name:
            env_value = (os.environ.get(env_name) or "").strip()
            if env_value:
                return env_value
        configured_value = (server_config.get("mmproj_path") or "").strip()
        return configured_value or None

    def supported_input_modalities(self) -> set[str]:
        active_modalities = set(self._declared_input_modalities)
        if "image" in active_modalities and self.managed_server and not self.resolved_mmproj_path():
            active_modalities.remove("image")
        return active_modalities or {"text"}

    def complete(
        self,
        prompt: str = "",
        system: str = "",
        params: Optional[dict] = None,
        messages: Optional[list] = None,
    ) -> CompletionResult:
        if self.managed_server and not self._managed_runtime_ready:
            self.warmup()

        merged = {**self.default_params, **(params or {})}

        if messages is None:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model_name,
            "messages": messages,
        }
        if "temperature" in merged:
            payload["temperature"] = merged["temperature"]
        if "max_tokens" in merged:
            payload["max_tokens"] = merged["max_tokens"]

        timeout = merged.get("timeout_seconds", 120)
        start = time.monotonic()
        try:
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=timeout,
            )
        except requests.exceptions.Timeout as exc:
            monitoring.observe_current_chat_provider_duration(
                outcome="timeout",
                duration_seconds=time.monotonic() - start,
            )
            raise ProviderTimeoutError(
                f"Request to {self.base_url} timed out after {timeout}s"
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            self._managed_runtime_ready = False
            monitoring.observe_current_chat_provider_duration(
                outcome="unavailable",
                duration_seconds=time.monotonic() - start,
            )
            raise ProviderUnavailableError(
                f"Cannot connect to {self.base_url}"
            ) from exc

        latency_ms = int((time.monotonic() - start) * 1000)

        if response.status_code != 200:
            monitoring.observe_current_chat_provider_duration(
                outcome="unavailable",
                duration_seconds=time.monotonic() - start,
            )
            raise ProviderUnavailableError(
                f"API returned {response.status_code}: {response.text[:300]}"
            )

        data = response.json()
        message = data["choices"][0]["message"]
        text = message.get("content") or message.get("reasoning_content") or ""
        tokens_used = data.get("usage", {}).get("total_tokens")

        monitoring.observe_current_chat_provider_duration(
            outcome="success",
            duration_seconds=time.monotonic() - start,
        )

        return CompletionResult(
            text=text.strip(),
            model_id=self.model_id,
            provider="openai_compatible",
            latency_ms=latency_ms,
            tokens_used=tokens_used,
        )
