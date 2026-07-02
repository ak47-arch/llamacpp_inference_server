"""Typed exceptions for the LLM workflow client."""


class LLMClientError(RuntimeError):
    """Base exception for all LLM client errors."""


class LLMTimeoutError(LLMClientError):
    """Raised when the upstream server fails to respond within the configured timeout."""


class LLMUnavailableError(LLMClientError):
    """Raised when the upstream server is unreachable (connection refused, DNS failure, etc.)."""


class LLMBadResponseError(LLMClientError):
    """Raised when the server returns an unparseable or empty response (e.g. malformed JSON)."""