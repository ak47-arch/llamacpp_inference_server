"""Abstract base for all LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


class ProviderUnavailableError(Exception):
    """Raised when the provider binary or endpoint cannot be reached."""


class ProviderTimeoutError(Exception):
    """Raised when the provider exceeds the configured timeout."""


@dataclass
class CompletionResult:
    text: str
    model_id: str
    provider: str
    latency_ms: int
    tokens_used: Optional[int] = None


class BaseProvider(ABC):
    def warmup(self) -> None:
        """Prepare the runtime for future completions."""

    def supported_input_modalities(self) -> set[str]:
        """Return the active input modalities supported by this provider."""
        return {"text"}

    @abstractmethod
    def complete(
        self,
        prompt: str = "",
        system: str = "",
        params: Optional[dict] = None,
        messages: Optional[list] = None,
    ) -> CompletionResult:
        """Run inference and return a CompletionResult."""
