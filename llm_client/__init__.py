"""llm_client — A uniform Python client for LLM workflows.

Usage:
    from llm_client import WorkflowClient, WorkflowResult

    client = WorkflowClient("config/workflows.yaml")
    result = client.complete_text("classify_tweet", prompt=tweet_text)
    print(result.data)  # parsed JSON if output=json
"""

from .workflow_client import WorkflowClient
from .schemas import WorkflowResult
from .errors import LLMClientError, LLMTimeoutError, LLMUnavailableError, LLMBadResponseError

__all__ = [
    "WorkflowClient",
    "WorkflowResult",
    "LLMClientError",
    "LLMTimeoutError",
    "LLMUnavailableError",
    "LLMBadResponseError",
]