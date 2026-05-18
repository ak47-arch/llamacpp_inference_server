"""Provider that calls a local llama-cli binary via subprocess."""

import os
import subprocess
import time
from typing import Optional

from . import monitoring
from .provider_base import (
    BaseProvider,
    CompletionResult,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


class LlamaCppProvider(BaseProvider):
    def __init__(
        self,
        model_id: str,
        binary_path: str,
        model_path: str,
        default_params: Optional[dict] = None,
    ):
        self.model_id = model_id
        self.provider_name = "llama_cpp"
        self.binary_path = os.path.expanduser(binary_path)
        self.model_path = os.path.expanduser(model_path)
        self.default_params = default_params or {}

    def complete(
        self,
        prompt: str = "",
        system: str = "",
        params: Optional[dict] = None,
        messages: Optional[list] = None,
    ) -> CompletionResult:
        merged = {**self.default_params, **(params or {})}

        full_prompt = f"{system}\n\n{prompt}".strip() if system else prompt

        cmd = [
            self.binary_path,
            "-m", self.model_path,
            "-p", full_prompt,
            "--temp", str(merged.get("temperature", 0.1)),
            "-n", str(merged.get("max_tokens", 512)),
            "-t", str(merged.get("threads", 8)),
            "-st",
            "--simple-io",
            "--no-display-prompt",
            "--log-disable",
        ]

        timeout = merged.get("timeout_seconds", 120)
        start = time.monotonic()
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError as exc:
            raise ProviderUnavailableError(
                f"llama-cli binary not found: {self.binary_path}"
            ) from exc

        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            self._cleanup_process(process)
            monitoring.observe_current_chat_provider_duration(
                outcome="timeout",
                duration_seconds=time.monotonic() - start,
            )
            raise ProviderTimeoutError(
                f"llama-cli timed out after {timeout}s"
            ) from exc

        latency_ms = int((time.monotonic() - start) * 1000)

        if process.returncode != 0:
            monitoring.observe_current_chat_provider_duration(
                outcome="unavailable",
                duration_seconds=time.monotonic() - start,
            )
            raise ProviderUnavailableError(
                f"llama-cli exited {process.returncode}: {stderr[:300]}"
            )

        # llama-cli echoes the prompt before the completion; strip the prefix.
        output = stdout
        if output.startswith(full_prompt):
            output = output[len(full_prompt):]

        monitoring.observe_current_chat_provider_duration(
            outcome="success",
            duration_seconds=time.monotonic() - start,
        )

        return CompletionResult(
            text=output.strip(),
            model_id=self.model_id,
            provider="llama_cpp",
            latency_ms=latency_ms,
        )

    def _cleanup_process(self, process: subprocess.Popen) -> None:
        """Terminate a timed-out process and escalate to kill if needed."""
        try:
            process.terminate()
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
