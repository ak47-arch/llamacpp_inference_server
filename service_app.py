"""Dedicated HTTP service for shared LLM inference."""

import os
import time

from flask import Flask, jsonify, request

from .provider_base import ProviderTimeoutError, ProviderUnavailableError
from .router import ProviderRouter


class LLMServiceRuntime:
    def __init__(self, router: ProviderRouter):
        self.router = router
        self._last_probe_ok = False
        self._last_probe_at = 0.0
        self._probe_ttl_seconds = 45.0

    def readiness(self) -> dict:
        now = time.monotonic()
        if self._last_probe_ok and (now - self._last_probe_at) < self._probe_ttl_seconds:
            return {"ready": True, "models": self.router.provider_ids()}

        for provider_id in self.router.provider_ids():
            provider = self.router.get_provider(provider_id)
            provider.warmup()
            provider.complete(
                "Readiness probe: respond with ok.",
                "You are a healthcheck probe. Reply with exactly 'ok'.",
                {
                    "temperature": 0.0,
                    "max_tokens": 4,
                    "timeout_seconds": 20,
                },
            )

        self._last_probe_ok = True
        self._last_probe_at = now
        return {"ready": True, "models": self.router.provider_ids()}

    def complete_chat(self, payload: dict) -> dict:
        model = (payload.get("model") or "").strip()
        if not model:
            raise ValueError("model is required")

        messages = payload.get("messages")
        if not isinstance(messages, list) or not messages:
            raise ValueError("messages must be a non-empty list")

        system_parts = []
        prompt_parts = []
        for message in messages:
            if not isinstance(message, dict):
                raise ValueError("messages must contain objects")
            role = (message.get("role") or "").strip()
            content = str(message.get("content") or "")
            if role == "system":
                system_parts.append(content)
            else:
                prompt_parts.append(content)

        provider = self.router.get_provider(model)
        params = {}
        for key in ("temperature", "max_tokens", "timeout_seconds"):
            if key in payload:
                params[key] = payload[key]

        result = provider.complete(
            "\n\n".join(part for part in prompt_parts if part),
            "\n\n".join(part for part in system_parts if part),
            params or None,
        )

        return {
            "id": f"chatcmpl-{int(time.time() * 1000)}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": result.model_id,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": result.text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": result.tokens_used,
            },
        }


def _error_response(status_code: int, error_type: str, message: str):
    return jsonify({"error": {"type": error_type, "message": message}}), status_code


def create_app(runtime: LLMServiceRuntime | None = None) -> Flask:
    app = Flask(__name__)
    service_runtime = runtime or build_runtime()

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "inference-server"})

    @app.get("/ready")
    def ready():
        try:
            return jsonify(service_runtime.readiness())
        except (ProviderTimeoutError, ProviderUnavailableError, RuntimeError, KeyError, ValueError) as exc:
            return _error_response(503, "runtime_unavailable", str(exc))

    @app.post("/v1/chat/completions")
    def chat_completions():
        payload = request.get_json(silent=True) or {}
        try:
            return jsonify(service_runtime.complete_chat(payload))
        except ValueError as exc:
            return _error_response(400, "invalid_request", str(exc))
        except ProviderTimeoutError as exc:
            return _error_response(504, "timeout", str(exc))
        except (ProviderUnavailableError, RuntimeError, KeyError) as exc:
            return _error_response(503, "runtime_unavailable", str(exc))

    return app


def build_runtime(config_path: str | None = None) -> LLMServiceRuntime:
    if config_path is None:
        repo_root = os.path.dirname(os.path.dirname(__file__))
        config_path = os.environ.get(
            "LLM_SERVER_CONFIG_FILE",
            os.path.join(repo_root, "llm", "service_models.yaml"),
        )
    return LLMServiceRuntime(ProviderRouter(config_path))


app = create_app()


if __name__ == "__main__":
    host = os.environ.get("LLM_SERVER_HOST", "0.0.0.0")
    port = int(os.environ.get("LLM_SERVER_PORT", "8012"))
    app.run(host=host, port=port)