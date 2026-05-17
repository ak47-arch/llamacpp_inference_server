"""Provider that calls any OpenAI-compatible REST API (OpenAI, Ollama, llama.cpp server, etc.)."""

import time
from typing import Optional

import requests

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
    ):
        self.model_id = model_id
        self.provider_name = "openai_compatible"
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.api_key = api_key
        self.default_params = default_params or {}
        self.managed_server = managed_server
        self._managed_runtime_ready = False

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

    def complete(
        self,
        prompt: str,
        system: str = "",
        params: Optional[dict] = None,
    ) -> CompletionResult:
        if self.managed_server and not self._managed_runtime_ready:
            self.warmup()

        merged = {**self.default_params, **(params or {})}

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
            raise ProviderTimeoutError(
                f"Request to {self.base_url} timed out after {timeout}s"
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            self._managed_runtime_ready = False
            raise ProviderUnavailableError(
                f"Cannot connect to {self.base_url}"
            ) from exc

        latency_ms = int((time.monotonic() - start) * 1000)

        if response.status_code != 200:
            raise ProviderUnavailableError(
                f"API returned {response.status_code}: {response.text[:300]}"
            )

        data = response.json()
        text = data["choices"][0]["message"]["content"]
        tokens_used = data.get("usage", {}).get("total_tokens")

        return CompletionResult(
            text=text.strip(),
            model_id=self.model_id,
            provider="openai_compatible",
            latency_ms=latency_ms,
            tokens_used=tokens_used,
        )
