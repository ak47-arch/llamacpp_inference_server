"""Dedicated HTTP service for shared LLM inference."""

import logging
import os
import time

from flask import Flask, Response, g, jsonify, request

from . import monitoring, prompt_capture
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
                provider=provider_name,
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

        result = provider.complete(
            prompt=prompt, system=system, params=params or None, messages=validated_messages
        )

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


def _error_body(error_type: str, message: str) -> dict:
    return {"error": {"type": error_type, "message": message}}


def _error_response(status_code: int, error_type: str, message: str):
    return jsonify(_error_body(error_type, message)), status_code


def _openapi_schema() -> dict:
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Generic Inference Server API",
            "version": "1.0.0",
            "description": "OpenAI-compatible chat completions API for local and upstream-backed LLM providers.",
        },
        "paths": {
            "/health": {
                "get": {
                    "summary": "Liveness probe",
                    "responses": {
                        "200": {
                            "description": "Service is alive",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/HealthResponse"}}},
                        }
                    },
                }
            },
            "/ready": {
                "get": {
                    "summary": "Readiness probe",
                    "responses": {
                        "200": {
                            "description": "Configured providers are ready",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ReadinessResponse"}}},
                        },
                        "503": {
                            "description": "Runtime unavailable",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
                        },
                    },
                }
            },
            "/v1/models": {
                "get": {
                    "summary": "List configured models",
                    "responses": {
                        "200": {
                            "description": "Configured logical model ids",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ModelListResponse"}}},
                        }
                    },
                }
            },
            "/v1/chat/completions": {
                "post": {
                    "summary": "OpenAI-compatible chat completions",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ChatCompletionRequest"}
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Successful completion",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ChatCompletionResponse"}}},
                        },
                        "400": {
                            "description": "Invalid request",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
                        },
                        "503": {
                            "description": "Provider unavailable",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
                        },
                        "504": {
                            "description": "Provider timed out",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
                        },
                    },
                }
            },
            "/metrics": {
                "get": {
                    "summary": "Prometheus metrics",
                    "responses": {"200": {"description": "Prometheus text exposition format"}},
                }
            },
        },
        "components": {
            "schemas": {
                "HealthResponse": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "const": "ok"},
                        "service": {"type": "string", "const": "inference-server"},
                    },
                    "required": ["status", "service"],
                },
                "ReadinessResponse": {
                    "type": "object",
                    "properties": {
                        "ready": {"type": "boolean"},
                        "models": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["ready", "models"],
                },
                "Model": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "object": {"type": "string", "const": "model"},
                        "owned_by": {"type": "string", "const": "llm"},
                    },
                    "required": ["id", "object", "owned_by"],
                },
                "ModelListResponse": {
                    "type": "object",
                    "properties": {
                        "object": {"type": "string", "const": "list"},
                        "data": {"type": "array", "items": {"$ref": "#/components/schemas/Model"}},
                    },
                    "required": ["object", "data"],
                },
                "TextContentPart": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "const": "text"},
                        "text": {"type": "string"},
                    },
                    "required": ["type", "text"],
                },
                "ImageUrlContentPart": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "const": "image_url"},
                        "image_url": {
                            "type": "object",
                            "properties": {"url": {"type": "string"}},
                            "required": ["url"],
                        },
                    },
                    "required": ["type", "image_url"],
                },
                "InputAudioContentPart": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "const": "input_audio"},
                        "input_audio": {
                            "type": "object",
                            "properties": {
                                "data": {"type": "string"},
                                "format": {"type": "string"},
                            },
                            "required": ["data", "format"],
                        },
                    },
                    "required": ["type", "input_audio"],
                },
                "ChatMessage": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string"},
                        "content": {
                            "oneOf": [
                                {"type": "string"},
                                {
                                    "type": "array",
                                    "items": {
                                        "oneOf": [
                                            {"$ref": "#/components/schemas/TextContentPart"},
                                            {"$ref": "#/components/schemas/ImageUrlContentPart"},
                                            {"$ref": "#/components/schemas/InputAudioContentPart"},
                                        ]
                                    },
                                },
                            ]
                        },
                    },
                    "required": ["role", "content"],
                },
                "ChatCompletionRequest": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "messages": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/ChatMessage"},
                            "minItems": 1,
                        },
                        "temperature": {"type": "number"},
                        "max_tokens": {"type": "integer"},
                        "timeout_seconds": {"type": "number"},
                    },
                    "required": ["model", "messages"],
                },
                "ChatCompletionChoice": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer"},
                        "message": {
                            "type": "object",
                            "properties": {
                                "role": {"type": "string", "const": "assistant"},
                                "content": {"type": "string"},
                            },
                            "required": ["role", "content"],
                        },
                        "finish_reason": {"type": "string"},
                    },
                    "required": ["index", "message", "finish_reason"],
                },
                "Usage": {
                    "type": "object",
                    "properties": {
                        "prompt_tokens": {"type": ["integer", "null"]},
                        "completion_tokens": {"type": ["integer", "null"]},
                        "total_tokens": {"type": ["integer", "null"]},
                    },
                    "required": ["prompt_tokens", "completion_tokens", "total_tokens"],
                },
                "ChatCompletionResponse": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "object": {"type": "string", "const": "chat.completion"},
                        "created": {"type": "integer"},
                        "model": {"type": "string"},
                        "choices": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/ChatCompletionChoice"},
                        },
                        "usage": {"$ref": "#/components/schemas/Usage"},
                    },
                    "required": ["id", "object", "created", "model", "choices", "usage"],
                },
                "ErrorResponse": {
                    "type": "object",
                    "properties": {
                        "error": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "message": {"type": "string"},
                            },
                            "required": ["type", "message"],
                        }
                    },
                    "required": ["error"],
                },
            }
        },
    }


def create_app(runtime: LLMServiceRuntime | None = None, capture_manager: prompt_capture.PromptCaptureManager | None = None) -> Flask:
    app = Flask(__name__)
    service_runtime = runtime or build_runtime()
    prompt_capture_manager = capture_manager or prompt_capture.build_capture_manager_from_env()
    app.extensions["prompt_capture_manager"] = prompt_capture_manager

    # ----- Request lifecycle hooks -----

    @app.before_request
    def _before_request():
        g.start_time = time.monotonic()
        g.route = request.path
        if g.route != "/metrics":
            monitoring.start_request_context(g.route)

    @app.after_request
    def _after_request(response):
        if not hasattr(g, "start_time"):
            return response
        duration = time.monotonic() - g.start_time
        outcome = getattr(g, "outcome", "success")
        model, provider = monitoring.current_request_labels()
        _log_service_access(request.method, g.route, response.status_code, duration)
        if outcome != "success":
            _log_service_failure(g.route, response.status_code, outcome)
        if g.route != "/metrics":
            monitoring.observe_request(
                route=g.route, model=model, provider=provider,
                outcome=outcome, duration_seconds=duration,
            )
        # Prompt capture for chat-completions traffic
        if g.route == "/v1/chat/completions" and hasattr(g, "_capture_data"):
            data = g._capture_data
            capture_body = response.get_json()
            if capture_body is None:
                capture_body = {}
            try:
                app.extensions["prompt_capture_manager"].capture_chat_completion(
                    request_id=data["request_id"],
                    route=g.route,
                    payload=data["payload"],
                    model=model,
                    provider=provider,
                    status_code=response.status_code,
                    outcome=outcome,
                    response_body=capture_body,
                )
            except Exception:
                _SERVICE_LOGGER.exception("Prompt capture failed")
        return response

    @app.teardown_request
    def _teardown_request(exc=None):
        if hasattr(g, "route") and g.route != "/metrics":
            monitoring.end_request_context(g.route)

    # ----- Error handlers -----

    @app.errorhandler(ValueError)
    def _value_error(exc):
        if getattr(g, "route", "") == "/ready":
            g.outcome = "unavailable"
            return _error_response(503, "runtime_unavailable", str(exc))
        g.outcome = "client_error"
        return _error_response(400, "invalid_request", str(exc))

    @app.errorhandler(ProviderTimeoutError)
    def _provider_timeout(exc):
        g.outcome = "timeout"
        if getattr(g, "route", "") == "/ready":
            return _error_response(503, "runtime_unavailable", str(exc))
        return _error_response(504, "timeout", str(exc))

    @app.errorhandler(ProviderUnavailableError)
    @app.errorhandler(RuntimeError)
    @app.errorhandler(KeyError)
    def _provider_unavailable(exc):
        g.outcome = "unavailable"
        return _error_response(503, "runtime_unavailable", str(exc))

    @app.errorhandler(Exception)
    def _server_error(exc):
        g.outcome = "server_error"
        _SERVICE_LOGGER.exception("Unhandled exception serving request")
        return _error_response(500, "server_error", str(exc))

    # ----- Routes -----

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "inference-server"})

    @app.get("/ready")
    def ready():
        return jsonify(service_runtime.readiness())

    @app.get("/v1/models")
    def list_models():
        return jsonify(
            {
                "object": "list",
                "data": [
                    {"id": model_id, "object": "model", "owned_by": "llm"}
                    for model_id in service_runtime.router.provider_ids()
                ],
            }
        )

    @app.post("/v1/chat/completions")
    def chat_completions():
        payload = request.get_json(silent=True) or {}
        g._capture_data = {
            "request_id": prompt_capture_manager.new_request_id(),
            "payload": payload,
        }
        response_body = service_runtime.complete_chat(payload)
        return jsonify(response_body)

    @app.get("/openapi.json")
    def openapi_schema():
        return jsonify(_openapi_schema())

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