"""Prompt and multimodal asset capture for inference requests."""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
import queue
import re
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from . import monitoring
from .capture_sinks import NDJSONCaptureSink

_ALLOWED_MODES = {"off", "metadata", "full"}
_ALLOWED_REDACTION_LEVELS = {"off", "basic", "strict"}


@dataclass(frozen=True)
class PromptCaptureConfig:
    mode: str = "off"
    redaction_level: str = "off"
    queue_max_records: int = 1000
    store_inline_media: bool = False
    include_system_prompts: bool = False
    include_error_records: bool = False

    def __post_init__(self):
        if self.mode not in _ALLOWED_MODES:
            raise ValueError(f"unsupported capture mode: {self.mode}")
        if self.redaction_level not in _ALLOWED_REDACTION_LEVELS:
            raise ValueError(f"unsupported capture redaction level: {self.redaction_level}")
        if self.queue_max_records <= 0:
            raise ValueError("queue_max_records must be positive")


class _NullCaptureSink:
    def write(self, record: dict) -> None:
        return None


class PromptCaptureManager:
    def __init__(self, config: PromptCaptureConfig | None = None, sink=None, autostart: bool = True):
        self.config = config or PromptCaptureConfig()
        self.sink = sink or _NullCaptureSink()
        self.enabled = self.config.mode != "off"
        self._queue: queue.Queue[Any] = queue.Queue(maxsize=self.config.queue_max_records)
        self._worker = None
        self._stop_sentinel = object()
        if self.enabled and autostart:
            self._worker = threading.Thread(target=self._run_worker, name="llm-prompt-capture", daemon=True)
            self._worker.start()

    def new_request_id(self) -> str:
        return f"req_{uuid.uuid4().hex}"

    def capture_chat_completion(
        self,
        *,
        request_id: str,
        route: str,
        payload: dict,
        model: str,
        provider: str,
        status_code: int,
        outcome: str,
        response_body: dict,
    ) -> None:
        if not self.enabled:
            return
        if outcome != "success" and not self.config.include_error_records:
            return

        record = _build_capture_record(
            config=self.config,
            request_id=request_id,
            route=route,
            payload=payload,
            model=model,
            provider=provider,
            status_code=status_code,
            outcome=outcome,
            response_body=response_body,
        )
        try:
            self._queue.put_nowait(record)
        except queue.Full:
            monitoring.observe_prompt_capture(self.config.mode, "dropped")
            return

        if self._worker is None:
            return

    def flush(self) -> None:
        if not self.enabled or self._worker is None:
            return
        self._queue.join()

    def shutdown(self) -> None:
        if self._worker is None:
            return
        self._queue.put(self._stop_sentinel)
        self._worker.join(timeout=2)

    def _run_worker(self) -> None:
        while True:
            record = self._queue.get()
            try:
                if record is self._stop_sentinel:
                    return
                self.sink.write(record)
            except Exception:
                monitoring.observe_prompt_capture(self.config.mode, "failed")
            else:
                monitoring.observe_prompt_capture(self.config.mode, "written")
            finally:
                self._queue.task_done()


def build_capture_manager_from_env() -> PromptCaptureManager:
    enabled = _env_flag("LLM_CAPTURE_ENABLED", False)
    mode = os.environ.get("LLM_CAPTURE_MODE", "off").strip() or "off"
    if not enabled:
        mode = "off"

    config = PromptCaptureConfig(
        mode=mode,
        redaction_level=os.environ.get("LLM_CAPTURE_REDACTION_LEVEL", "off").strip() or "off",
        queue_max_records=int(os.environ.get("LLM_CAPTURE_QUEUE_MAX_RECORDS", "1000")),
        store_inline_media=_env_flag("LLM_CAPTURE_STORE_INLINE_MEDIA", False),
        include_system_prompts=_env_flag("LLM_CAPTURE_INCLUDE_SYSTEM_PROMPTS", False),
        include_error_records=_env_flag("LLM_CAPTURE_INCLUDE_ERROR_RECORDS", False),
    )
    if config.mode == "off":
        return PromptCaptureManager(config=config)

    sink_name = os.environ.get("LLM_CAPTURE_SINK", "ndjson").strip() or "ndjson"
    if sink_name != "ndjson":
        raise ValueError(f"unsupported capture sink: {sink_name}")
    output_path = os.environ.get("LLM_CAPTURE_FILE_PATH", "").strip()
    if not output_path:
        raise ValueError("LLM_CAPTURE_FILE_PATH is required when prompt capture is enabled")
    return PromptCaptureManager(config=config, sink=NDJSONCaptureSink(output_path))


def _build_capture_record(
    *,
    config: PromptCaptureConfig,
    request_id: str,
    route: str,
    payload: dict,
    model: str,
    provider: str,
    status_code: int,
    outcome: str,
    response_body: dict,
) -> dict:
    return {
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "route": route,
        "model": model,
        "provider": provider,
        "status_code": status_code,
        "outcome": outcome,
        "capture_mode": config.mode,
        "request": _normalize_request(payload, config),
        "response": _normalize_response(response_body, config),
        "usage": dict(response_body.get("usage") or {}),
        "redaction": {
            "level": config.redaction_level,
            "system_prompts_included": config.include_system_prompts,
            "inline_media_stored": config.store_inline_media,
        },
        "metadata": {},
    }


def _normalize_request(payload: dict, config: PromptCaptureConfig) -> dict:
    messages = payload.get("messages") if isinstance(payload.get("messages"), list) else []
    request_data = {
        "message_count": len(messages),
        "input_modalities": sorted(_detect_input_modalities(messages)),
        "system_prompt_included": config.include_system_prompts,
    }
    params = {key: payload[key] for key in ("temperature", "max_tokens", "timeout_seconds") if key in payload}
    if params:
        request_data["params"] = params

    if config.mode == "metadata":
        return request_data

    normalized_messages = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "")
        if role == "system" and not config.include_system_prompts:
            continue
        normalized_messages.append(
            {
                "role": role,
                "content": _normalize_message_content(message.get("content"), config),
            }
        )
    request_data["messages"] = normalized_messages
    return request_data


def _normalize_response(response_body: dict, config: PromptCaptureConfig) -> dict:
    error = response_body.get("error") if isinstance(response_body, dict) else None
    if isinstance(error, dict):
        return {
            "error_type": error.get("type"),
            "error_message": _redact_text(str(error.get("message") or ""), config.redaction_level),
        }

    choices = response_body.get("choices") if isinstance(response_body, dict) else None
    if not isinstance(choices, list) or not choices:
        return {}

    message = choices[0].get("message") if isinstance(choices[0], dict) else {}
    content = message.get("content") if isinstance(message, dict) else ""
    finish_reason = choices[0].get("finish_reason") if isinstance(choices[0], dict) else None
    if config.mode == "metadata":
        return {
            "assistant_text_present": bool(content),
            "assistant_text_length": len(content or ""),
            "finish_reason": finish_reason,
        }
    return {
        "assistant_text": _redact_text(str(content or ""), config.redaction_level),
        "finish_reason": finish_reason,
    }


def _normalize_message_content(content: Any, config: PromptCaptureConfig):
    if isinstance(content, str):
        return _redact_text(content, config.redaction_level)
    if not isinstance(content, list):
        return content
    return [_normalize_content_part(part, config) for part in content if isinstance(part, dict)]


def _normalize_content_part(part: dict, config: PromptCaptureConfig) -> dict:
    part_type = str(part.get("type") or "")
    if part_type == "text":
        text = str(part.get("text") or "")
        if config.mode == "metadata":
            return {"type": "text", "text_length": len(text)}
        return {"type": "text", "text": _redact_text(text, config.redaction_level)}

    if part_type == "image_url":
        image_url = part.get("image_url") if isinstance(part.get("image_url"), dict) else {}
        url = str(image_url.get("url") or "")
        if config.mode == "metadata":
            return {"type": "image_url", **_media_metadata_from_url(url)}
        if _is_inline_data_url(url) and not config.store_inline_media:
            return {"type": "image_url", "image_url": {"stored": False, **_media_metadata_from_url(url)}}
        return {"type": "image_url", "image_url": {"url": url}}

    if part_type == "input_audio":
        input_audio = part.get("input_audio") if isinstance(part.get("input_audio"), dict) else {}
        audio_data = str(input_audio.get("data") or "")
        audio_format = str(input_audio.get("format") or "")
        if config.mode == "metadata" or not config.store_inline_media:
            return {
                "type": "input_audio",
                "input_audio": {
                    "stored": False,
                    "format": audio_format,
                    **_inline_payload_metadata(audio_data),
                },
            }
        return {
            "type": "input_audio",
            "input_audio": {
                "data": audio_data,
                "format": audio_format,
            },
        }

    return dict(part)


def _detect_input_modalities(messages: list) -> set[str]:
    modalities: set[str] = set()
    for message in messages:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str):
            modalities.add("text")
        elif isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                part_type = str(part.get("type") or "")
                if part_type == "text":
                    modalities.add("text")
                elif part_type == "image_url":
                    modalities.add("image")
                elif part_type == "input_audio":
                    modalities.add("audio")
    return modalities or {"text"}


def _media_metadata_from_url(url: str) -> dict:
    if _is_inline_data_url(url):
        header, _, payload = url.partition(",")
        mime_type = header[5:].split(";", 1)[0] if header.startswith("data:") else "application/octet-stream"
        payload_metadata = _inline_payload_metadata(payload)
        return {
            "stored": False,
            "source": "inline",
            "mime_type": mime_type,
            **payload_metadata,
        }
    return {
        "stored": True,
        "source": "url",
        "url": url,
        "sha256": hashlib.sha256(url.encode("utf-8")).hexdigest(),
        "byte_length": len(url.encode("utf-8")),
    }


def _inline_payload_metadata(payload: str) -> dict:
    raw_bytes = _decode_base64_payload(payload)
    return {
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "byte_length": len(raw_bytes),
    }


def _decode_base64_payload(payload: str) -> bytes:
    try:
        return base64.b64decode(payload, validate=True)
    except (ValueError, binascii.Error):
        return payload.encode("utf-8")


def _is_inline_data_url(value: str) -> bool:
    return value.startswith("data:")


def _redact_text(text: str, level: str) -> str:
    if level == "off":
        return text

    redacted = re.sub(r"(?i)bearer\s+[a-z0-9._\-]+", "[redacted-bearer-token]", text)
    redacted = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[redacted-email]", redacted)
    redacted = re.sub(r"\b\+?\d[\d\-() ]{6,}\d\b", "[redacted-phone]", redacted)
    if level == "strict":
        redacted = re.sub(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*\S+", r"\1=[redacted]", redacted)
    return redacted


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


__all__ = [
    "NDJSONCaptureSink",
    "PromptCaptureConfig",
    "PromptCaptureManager",
    "build_capture_manager_from_env",
]
