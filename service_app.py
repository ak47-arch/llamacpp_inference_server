"""Dedicated HTTP service for shared LLM inference."""

import inspect
import logging
import os
import time

from flask import Flask, Response, jsonify, request

from . import monitoring
from .provider_base import ProviderTimeoutError, ProviderUnavailableError
from .router import ProviderRouter


_SUPPORTED_CONTENT_PART_TYPES = {"text", "image_url", "input_audio"}
_SERVICE_LOGGER = logging.getLogger("llm.service")


def _validate_content_parts(content_parts: list) -> tuple[list, set[str]]:
    required_modalities: set[str] = set()
    validated_parts: list = []
    for part in content_parts:
        if not isinstance(part, dict):
            raise ValueError("content parts must contain objects")

        part_type = (part.get("type") or "").strip()
        if part_type not in _SUPPORTED_CONTENT_PART_TYPES:
            raise ValueError("unsupported content part type")

        if part_type == "text":
            if not isinstance(part.get("text"), str):
                raise ValueError("text content parts require text")
            required_modalities.add("text")
        elif part_type == "image_url":
            image_url = part.get("image_url")
            if not isinstance(image_url, dict) or not isinstance(image_url.get("url"), str) or not image_url.get("url").strip():
                raise ValueError("image_url content parts require image_url.url")
            required_modalities.add("image")
        elif part_type == "input_audio":
            input_audio = part.get("input_audio")
            if (
                not isinstance(input_audio, dict)
                or not isinstance(input_audio.get("data"), str)
                or not input_audio.get("data")
                or not isinstance(input_audio.get("format"), str)
                or not input_audio.get("format").strip()
            ):
                raise ValueError("input_audio content parts require input_audio.data and input_audio.format")
            required_modalities.add("audio")

        validated_parts.append(dict(part))
    return validated_parts, required_modalities


def _log_service_access(method: str, path: str, status: int, duration_seconds: float) -> None:
    _SERVICE_LOGGER.info(
        "event=access method=%s path=%s status=%s duration_seconds=%.6f",
        method,
        path,
        status,
        duration_seconds,
    )


def _log_service_failure(path: str, status: int, error_class: str) -> None:
    _SERVICE_LOGGER.info(
        "event=failure_summary path=%s status=%s error_class=%s",
        path,
        status,
        error_class,
    )


def _validate_chat_messages(messages: list) -> tuple[list, set[str], bool]:
    validated_messages: list = []
    required_modalities: set[str] = set()
    has_structured_content = False

    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("messages must contain objects")

        role = message.get("role")
        if not isinstance(role, str) or not role.strip():
            raise ValueError("messages must include role")
        if "content" not in message:
            raise ValueError("messages must include content")

        content = message["content"]
        validated_message = dict(message)
        if isinstance(content, str):
            required_modalities.add("text")
        elif isinstance(content, list):
            has_structured_content = True
            validated_content, content_modalities = _validate_content_parts(content)
            validated_message["content"] = validated_content
            required_modalities.update(content_modalities)
        else:
            raise ValueError("message content must be a string or list of content parts")

        validated_messages.append(validated_message)

    return validated_messages, required_modalities, has_structured_content


class LLMServiceRuntime:
    def __init__(self, router: ProviderRouter):
        self.router = router
        self._last_probe_ok = False
        self._last_probe_at = 0.0
        self._probe_ttl_seconds = 45.0

    def readiness(self) -> dict:
        now = time.monotonic()

        for provider_id in self.router.provider_ids():
            provider = self.router.get_provider(provider_id)
            provider_name = monitoring.provider_identity(provider)
            start = time.monotonic()
            try:
                provider.warmup()
                result = provider.complete(
                    "Readiness probe: respond with ok.",
                    "You are a healthcheck probe. Reply with exactly 'ok'.",
                    {
                        "temperature": 0.0,
                        "max_tokens": 4,
                        "timeout_seconds": 20,
                    },
                )
            except Exception as exc:
                monitoring.observe_readiness(
                    model=provider_id,
                    provider=provider_name,
                    outcome=monitoring.classify_readiness_exception(exc),
                    duration_seconds=time.monotonic() - start,
                )
                raise

            monitoring.observe_readiness(
                model=provider_id,
                provider=result.provider or provider_name,
                outcome="success",
                duration_seconds=time.monotonic() - start,
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

        validated_messages, required_modalities, has_structured_content = _validate_chat_messages(messages)

        monitoring.set_resolved_model(model)
        provider = self.router.get_provider(model)
        provider_name = monitoring.provider_identity(provider)
        monitoring.set_resolved_provider(provider_name)

        if has_structured_content and provider_name != "openai_compatible":
            raise ValueError("structured multimodal requests are only supported for openai_compatible providers")

        if hasattr(provider, "supported_input_modalities"):
            active_modalities = provider.supported_input_modalities()
        else:
            active_modalities = {"text"}
        for modality in ("image", "audio"):
            if modality in required_modalities and modality not in active_modalities:
                raise ValueError(f"provider '{model}' does not support {modality} input")

        params = {}
        for key in ("temperature", "max_tokens", "timeout_seconds"):
            if key in payload:
                params[key] = payload[key]

        system_parts = [message["content"] for message in validated_messages if message["role"] == "system"]
        prompt_parts = [message["content"] for message in validated_messages if message["role"] != "system"]
        prompt = "\n\n".join(part for part in prompt_parts if isinstance(part, str) and part)
        system = "\n\n".join(part for part in system_parts if isinstance(part, str) and part)

        supports_messages_arg = "messages" in inspect.signature(provider.complete).parameters
        if provider_name == "openai_compatible" and supports_messages_arg:
            result = provider.complete(params=params or None, messages=validated_messages)
        else:
            result = provider.complete(prompt, system, params or None)

        monitoring.set_resolved_provider(result.provider or provider_name)

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
        route = "/health"
        start = time.monotonic()
        with monitoring.request_context(route), monitoring.track_in_flight(route):
            try:
                response = jsonify({"status": "ok", "service": "inference-server"})
                outcome = "success"
                status_code = 200
            except Exception as exc:
                duration_seconds = time.monotonic() - start
                _log_service_failure(route, 500, "server_error")
                _log_service_access(request.method, route, 500, duration_seconds)
                model, provider = monitoring.current_request_labels()
                monitoring.observe_request(
                    route=route,
                    model=model,
                    provider=provider,
                    outcome=monitoring.classify_exception(exc),
                    duration_seconds=duration_seconds,
                )
                raise

            duration_seconds = time.monotonic() - start
            _log_service_access(request.method, route, status_code, duration_seconds)
            model, provider = monitoring.current_request_labels()
            monitoring.observe_request(
                route=route,
                model=model,
                provider=provider,
                outcome=outcome,
                duration_seconds=duration_seconds,
            )
            return response

    @app.get("/ready")
    def ready():
        route = "/ready"
        start = time.monotonic()
        with monitoring.request_context(route), monitoring.track_in_flight(route):
            try:
                response = jsonify(service_runtime.readiness())
                outcome = "success"
                status_code = 200
            except ProviderTimeoutError as exc:
                outcome = "timeout"
                status_code = 503
                response = _error_response(503, "runtime_unavailable", str(exc))
            except (ProviderUnavailableError, RuntimeError, KeyError, ValueError) as exc:
                outcome = monitoring.classify_readiness_exception(exc)
                status_code = 503
                response = _error_response(503, "runtime_unavailable", str(exc))
            except Exception as exc:
                duration_seconds = time.monotonic() - start
                _log_service_failure(route, 500, "server_error")
                _log_service_access(request.method, route, 500, duration_seconds)
                model, provider = monitoring.current_request_labels()
                monitoring.observe_request(
                    route=route,
                    model=model,
                    provider=provider,
                    outcome=monitoring.classify_exception(exc),
                    duration_seconds=duration_seconds,
                )
                raise

            duration_seconds = time.monotonic() - start
            if outcome != "success":
                _log_service_failure(route, status_code, outcome)
            _log_service_access(request.method, route, status_code, duration_seconds)
            model, provider = monitoring.current_request_labels()
            monitoring.observe_request(
                route=route,
                model=model,
                provider=provider,
                outcome=outcome,
                duration_seconds=duration_seconds,
            )
            return response

    @app.post("/v1/chat/completions")
    def chat_completions():
        route = "/v1/chat/completions"
        start = time.monotonic()
        payload = request.get_json(silent=True) or {}
        with monitoring.request_context(route), monitoring.track_in_flight(route):
            try:
                response = jsonify(service_runtime.complete_chat(payload))
                outcome = "success"
                status_code = 200
            except ValueError as exc:
                outcome = "client_error"
                status_code = 400
                response = _error_response(400, "invalid_request", str(exc))
            except ProviderTimeoutError as exc:
                outcome = "timeout"
                status_code = 504
                response = _error_response(504, "timeout", str(exc))
            except (ProviderUnavailableError, RuntimeError, KeyError) as exc:
                outcome = monitoring.classify_exception(exc)
                status_code = 503
                response = _error_response(503, "runtime_unavailable", str(exc))
            except Exception as exc:
                duration_seconds = time.monotonic() - start
                _log_service_failure(route, 500, "server_error")
                _log_service_access(request.method, route, 500, duration_seconds)
                model, provider = monitoring.current_request_labels()
                monitoring.observe_request(
                    route=route,
                    model=model,
                    provider=provider,
                    outcome=monitoring.classify_exception(exc),
                    duration_seconds=duration_seconds,
                )
                raise

            duration_seconds = time.monotonic() - start
            if outcome != "success":
                _log_service_failure(route, status_code, outcome)
            _log_service_access(request.method, route, status_code, duration_seconds)
            model, provider = monitoring.current_request_labels()
            monitoring.observe_request(
                route=route,
                model=model,
                provider=provider,
                outcome=outcome,
                duration_seconds=duration_seconds,
            )
            return response

    @app.get("/metrics")
    def metrics():
        payload, content_type = monitoring.metrics_response()
        return Response(payload, mimetype=content_type)

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