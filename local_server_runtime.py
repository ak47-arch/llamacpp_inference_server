"""Managed local llama.cpp server lifecycle for low-latency HTTP inference."""

import os
import subprocess
import time
import urllib.error
import urllib.request


_managed_servers = {}


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

    extra_args = server_config.get("extra_args") or []
    if extra_args:
        command.extend([str(arg) for arg in extra_args])

    return command


def _wait_for_server(base_url: str, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _server_is_ready(base_url):
            return
        time.sleep(0.1)
    raise RuntimeError(f"Managed local server at {base_url} did not become ready")


def ensure_managed_server(
    base_url: str,
    binary_path: str,
    model_path: str,
    model_name: str,
    server_config: dict | None = None,
    default_params: dict | None = None,
) -> None:
    if _server_is_ready(base_url):
        return

    existing = _managed_servers.get(base_url)
    if existing is not None and existing.poll() is None:
        _wait_for_server(base_url, (server_config or {}).get("startup_timeout_seconds", 30))
        return

    command = _build_server_command(
        binary_path=binary_path,
        model_path=model_path,
        model_name=model_name,
        base_url=base_url,
        server_config=server_config,
        default_params=default_params,
    )

    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        _wait_for_server(base_url, (server_config or {}).get("startup_timeout_seconds", 30))
    except Exception:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
        raise

    _managed_servers[base_url] = process


def reset_managed_servers() -> None:
    for process in _managed_servers.values():
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
    _managed_servers.clear()