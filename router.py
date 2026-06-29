"""Loads provider configuration and routes inference calls by logical role."""

import os
import yaml

from .llama_cpp_provider import LlamaCppProvider
from .openai_compatible_provider import OpenAICompatibleProvider
from .provider_base import (
    BaseProvider,
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
                input_modalities=(entry.get("capabilities") or {}).get("input_modalities"),
            )

        raise ValueError(f"Unknown provider_type '{ptype}' for provider '{pid}'")


    def provider_ids(self) -> list:
        return list(self._providers.keys())

    def get_provider(self, provider_id: str) -> BaseProvider:
        provider = self._providers.get(provider_id)
        if provider is None:
            raise KeyError(f"Provider '{provider_id}' not found in registry")
        return provider


