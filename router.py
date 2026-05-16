"""Loads provider configuration and routes inference calls by logical role."""

import os
from typing import Optional

import yaml

from .llama_cpp_provider import LlamaCppProvider
from .openai_compatible_provider import OpenAICompatibleProvider
from .provider_base import (
    BaseProvider,
    CompletionResult,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


class ProviderRouter:
    def __init__(self, config_path: str):
        config_path = os.path.expanduser(config_path)
        base_dir = os.path.dirname(os.path.abspath(config_path))

        with open(config_path) as f:
            config = yaml.safe_load(f)

        self._providers: dict[str, BaseProvider] = {}
        for entry in config.get("providers", []):
            provider = self._build_provider(entry, base_dir)
            self._providers[entry["id"]] = provider

        self._routing: dict[str, str] = config.get("pipeline_routing", {})

    def _build_provider(self, entry: dict, base_dir: str) -> BaseProvider:
        ptype = entry["provider_type"]
        pid = entry["id"]
        conn = entry.get("connection", {})
        default_params = entry.get("default_params", {})

        if ptype == "llama_cpp":
            model_path = conn["model_path"]
            # Resolve relative model paths against the config file's directory
            if not os.path.isabs(model_path) and not model_path.startswith("~"):
                model_path = os.path.join(base_dir, model_path)
            return LlamaCppProvider(
                model_id=pid,
                binary_path=conn["binary_path"],
                model_path=model_path,
                default_params=default_params,
            )

        if ptype == "openai_compatible":
            base_url = conn.get("base_url", "")
            base_url_env = conn.get("base_url_env")
            if base_url_env:
                base_url = os.environ.get(base_url_env, base_url)
            return OpenAICompatibleProvider(
                model_id=pid,
                base_url=base_url,
                model_name=entry["model_name"],
                api_key=conn.get("api_key"),
                default_params=default_params,
                managed_server=conn.get("managed_server"),
            )

        raise ValueError(f"Unknown provider_type '{ptype}' for provider '{pid}'")

    def route(
        self,
        role: str,
        prompt: str,
        system: str = "",
        params: Optional[dict] = None,
    ) -> CompletionResult:
        provider_ids = self._resolve_provider_ids(role)
        if not provider_ids:
            raise KeyError(f"No provider configured for role '{role}'")

        last_error = None
        for provider_id in provider_ids:
            provider = self._providers.get(provider_id)
            if not provider:
                raise KeyError(f"Provider '{provider_id}' not found in registry")
            try:
                return provider.complete(prompt, system, params)
            except (ProviderTimeoutError, ProviderUnavailableError) as exc:
                last_error = exc

        raise last_error

    def _resolve_provider_ids(self, role: str) -> list[str]:
        route_entry = self._routing.get(role)
        if route_entry is None:
            return []
        if isinstance(route_entry, str):
            return [route_entry]
        if isinstance(route_entry, dict):
            primary = route_entry.get("primary")
            fallback_ids = route_entry.get("fallback_ids", [])
            return [provider_id for provider_id in [primary, *fallback_ids] if provider_id]
        raise ValueError(f"Invalid routing entry for role '{role}'")

    def provider_ids(self) -> list:
        return list(self._providers.keys())

    def get_provider(self, provider_id: str) -> BaseProvider:
        provider = self._providers.get(provider_id)
        if provider is None:
            raise KeyError(f"Provider '{provider_id}' not found in registry")
        return provider

    def routing(self) -> dict:
        return dict(self._routing)

    def ensure_runtime_ready(self, role: Optional[str] = None) -> None:
        provider_ids = self._resolve_provider_ids(role) if role else self.provider_ids()
        for provider_id in provider_ids:
            provider = self._providers.get(provider_id)
            if provider is None:
                continue
            provider.warmup()
