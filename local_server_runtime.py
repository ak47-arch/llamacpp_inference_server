"""Managed local llama.cpp server lifecycle for low-latency HTTP inference."""

import logging
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request

from . import monitoring


_managed_servers = {}
_RUNTIME_LOGGER = logging.getLogger("llm.runtime")


def _healthcheck_urls(base_url: str) -> list[str]:
    return [
        f"{base_url.rstrip('/')}/health",
        f"{base_url.rstrip('/')}/v1/models",
    ]


def _server_is_ready(base_url: str, timeout_seconds: float = 1.0) -> bool:
    for url in _healthcheck_urls(base_url):
        try:
            with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError):
            continue
    return False


def _resolve_mmproj_path(server_config: dict | None = None) -> str | None:
    server_config = server_config or {}
    env_name = server_config.get("mmproj_path_env")
    if env_name:
        env_value = (os.environ.get(env_name) or "").strip()
        if env_value:
            return os.path.expanduser(env_value)
    configured_path = (server_config.get("mmproj_path") or "").strip()
    if configured_path:
        return os.path.expanduser(configured_path)
    return None


def _build_server_command(
    binary_path: str,
    model_path: str,
    model_name: str,
    base_url: str,
    server_config: dict | None = None,
    default_params: dict | None = None,
) -> list[str]:
    server_config = server_config or {}
    default_params = default_params or {}
    binary_path = os.path.expanduser(binary_path)
    model_path = os.path.expanduser(model_path)

    host = server_config.get("host", "127.0.0.1")
    port = server_config.get("port")
    if port is None:
        port = int(base_url.rsplit(":", 1)[-1])

    command = [
        binary_path,
        "-m",
        model_path,
        "--host",
        host,
        "--port",
        str(port),
        "-a",
        model_name,
    ]

    threads = server_config.get("threads", default_params.get("threads"))
    if threads is not None:
        command.extend(["-t", str(threads)])

    ctx_size = server_config.get("ctx_size")
    if ctx_size is not None:
        command.extend(["-c", str(ctx_size)])

    batch_size = server_config.get("batch_size")
    if batch_size is not None:
        command.extend(["-b", str(batch_size)])

    mmproj_path = _resolve_mmproj_path(server_config)
    if mmproj_path:
        command.extend(["--mmproj", mmproj_path])

    extra_args = server_config.get("extra_args") or []
    if extra_args:
        command.extend([str(arg) for arg in extra_args])

    return command


def _sanitize_child_log_line(line: str) -> str | None:
    sanitized = line.strip()
    if not sanitized:
        return None

    lowered = sanitized.lower()
    blocked_markers = (
        "authorization:",
        "bearer ",
        "api_key",
        '"messages"',
        "data:",
        "http://",
        "https://",
    )
    if any(marker in lowered for marker in blocked_markers):
        return None
    return sanitized


def _forward_child_stream(stream, stream_name: str, model: str, base_url: str) -> None:
    if stream is None:
        return
    try:
        iterator = iter(stream)
    except TypeError:
        return
    for raw_line in iterator:
        sanitized = _sanitize_child_log_line(raw_line)
        if sanitized is None:
            continue
        _RUNTIME_LOGGER.info(
            "event=child_log model=%s base_url=%s stream=%s message=%s",
            model,
            base_url,
            stream_name,
            sanitized,
        )


def _start_child_log_forwarders(process: subprocess.Popen, model: str, base_url: str) -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(process, stream_name, None)
        if stream is None:
            continue
        thread = threading.Thread(
            target=_forward_child_stream,
            args=(stream, stream_name, model, base_url),
            daemon=True,
        )
        thread.start()


def _wait_for_server(base_url: str, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _server_is_ready(base_url):
            return
        time.sleep(0.1)
    raise RuntimeError(f"Managed local server at {base_url} did not become ready")


def _build_subprocess_env(binary_path: str) -> dict[str, str]:
    env = dict(os.environ)
    binary_dir = os.path.dirname(os.path.expanduser(binary_path))
    existing = env.get("LD_LIBRARY_PATH", "")
    paths = [path for path in existing.split(":") if path]
    if binary_dir and binary_dir not in paths:
        paths.insert(0, binary_dir)
    env["LD_LIBRARY_PATH"] = ":".join(paths)
    return env


def ensure_managed_server(
    base_url: str,
    binary_path: str,
    model_path: str,
    model_name: str,
    model_id: str | None = None,
    server_config: dict | None = None,
    default_params: dict | None = None,
) -> None:
    metric_model = model_id or model_name
    if _server_is_ready(base_url):
        return

    existing = _managed_servers.get(base_url)
    if existing is not None and existing.poll() is None:
        _wait_for_server(base_url, (server_config or {}).get("startup_timeout_seconds", 30))
        return
    if existing is not None and existing.poll() is not None:
        _RUNTIME_LOGGER.info("event=restart model=%s base_url=%s", metric_model, base_url)
        monitoring.increment_managed_server_restart(metric_model, base_url)

    command = _build_server_command(
        binary_path=binary_path,
        model_path=model_path,
        model_name=model_name,
        base_url=base_url,
        server_config=server_config,
        default_params=default_params,
    )

    start = time.monotonic()
    _RUNTIME_LOGGER.info("event=launch model=%s base_url=%s", metric_model, base_url)
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        env=_build_subprocess_env(binary_path),
    )
    _start_child_log_forwarders(process, metric_model, base_url)
    try:
        _wait_for_server(base_url, (server_config or {}).get("startup_timeout_seconds", 30))
    except Exception:
        duration_seconds = time.monotonic() - start
        _RUNTIME_LOGGER.info(
            "event=failure model=%s base_url=%s duration_seconds=%.6f error_class=unavailable",
            metric_model,
            base_url,
            duration_seconds,
        )
        monitoring.observe_managed_server_startup(
            model=metric_model,
            base_url=base_url,
            outcome="unavailable",
            duration_seconds=duration_seconds,
        )
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
        raise

    duration_seconds = time.monotonic() - start
    _RUNTIME_LOGGER.info(
        "event=ready model=%s base_url=%s duration_seconds=%.6f",
        metric_model,
        base_url,
        duration_seconds,
    )
    monitoring.observe_managed_server_startup(
        model=metric_model,
        base_url=base_url,
        outcome="success",
        duration_seconds=duration_seconds,
    )
    _managed_servers[base_url] = process


def reset_managed_servers() -> None:
    for base_url, process in list(_managed_servers.items()):
        if process.poll() is None:
            _RUNTIME_LOGGER.info("event=terminate model=unknown base_url=%s", base_url)
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
    _managed_servers.clear()