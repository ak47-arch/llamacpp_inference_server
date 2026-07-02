"""Tests for the ``llm_client`` package.

Run with ::

    pytest tests/test_workflow_client.py -v

Integration tests (require a running server) are marked ``integration``::

    pytest tests/test_workflow_client.py -v -m integration
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from llm_client import (
    LLMBadResponseError,
    LLMClientError,
    LLMTimeoutError,
    LLMUnavailableError,
    WorkflowClient,
    WorkflowResult,
)
from llm_client.config import ModelEntry, WorkflowConfig, WorkflowDef


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def sample_yaml() -> dict:
    return {
        "models": {
            "fast": {
                "url": "http://localhost:8012",
                "model": "gemma_e2b_q4_local",
                "timeout": 180,
            },
            "quality": {
                "url": "http://llm-inference-server:8012",
                "model": "gemma_e2b_q4_local",
                "timeout": 300,
            },
        },
        "workflows": {
            "classify_tweet": {
                "model_ref": "fast",
                "temperature": 0.0,
                "max_tokens": 256,
                "output": "json",
                "system_prompt": "Respond only with JSON.",
                "fallback": "none",
            },
            "wiki_synthesis": {
                "model_ref": "quality",
                "temperature": 0.3,
                "max_tokens": 2048,
                "output": "text",
                "system_prompt": None,
                "fallback": "none",
            },
            "scout_project_card": {
                "model_ref": "fast",
                "temperature": 0.0,
                "max_tokens": 512,
                "output": "json",
                "fallback": "none",
            },
        },
    }


@pytest.fixture
def sample_yaml_path(sample_yaml: dict) -> Path:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    yaml.dump(sample_yaml, tmp)
    tmp.close()
    yield Path(tmp.name)
    Path(tmp.name).unlink(missing_ok=True)


@pytest.fixture
def client(sample_yaml_path: Path) -> WorkflowClient:
    return WorkflowClient(sample_yaml_path)


# ======================================================================
# Config loading
# ======================================================================


class TestConfigLoading:
    def test_loads_valid_yaml(self, sample_yaml_path: Path):
        config = WorkflowConfig.from_yaml(sample_yaml_path)
        assert "fast" in config.models
        assert "quality" in config.models
        assert "classify_tweet" in config.workflows
        assert "wiki_synthesis" in config.workflows

    def test_model_entry_fields(self, sample_yaml_path: Path):
        config = WorkflowConfig.from_yaml(sample_yaml_path)
        fast = config.models["fast"]
        assert fast.url == "http://localhost:8012"
        assert fast.model == "gemma_e2b_q4_local"
        assert fast.timeout == 180

    def test_workflow_def_fields(self, sample_yaml_path: Path):
        config = WorkflowConfig.from_yaml(sample_yaml_path)
        wf = config.workflows["classify_tweet"]
        assert wf.model_ref == "fast"
        assert wf.temperature == 0.0
        assert wf.max_tokens == 256
        assert wf.output == "json"
        assert wf.system_prompt == "Respond only with JSON."
        assert wf.fallback == "none"

    def test_defaults_applied(self, sample_yaml_path: Path):
        """Workflow without optional fields should use defaults."""
        config = WorkflowConfig.from_yaml(sample_yaml_path)
        wf = config.workflows["scout_project_card"]
        assert wf.output == "json"
        assert wf.fallback == "none"

    def test_missing_file(self):
        with pytest.raises(FileNotFoundError):
            WorkflowConfig.from_yaml("/nonexistent/path.yaml")

    def test_invalid_yaml(self):
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        tmp.write(":: not yaml :: {{")
        tmp.close()
        path = Path(tmp.name)
        try:
            with pytest.raises(yaml.YAMLError):
                WorkflowConfig.from_yaml(path)
        finally:
            path.unlink(missing_ok=True)

    def test_env_var_substitution(self):
        os.environ["_TEST_LLM_URL"] = "http://test-server:9999"
        yml = {
            "models": {
                "m1": {
                    "url": "${_TEST_LLM_URL}",
                    "model": "test-model",
                    "timeout": 30,
                }
            },
            "workflows": {
                "w1": {
                    "model_ref": "m1",
                    "temperature": 0.0,
                    "max_tokens": 100,
                    "output": "text",
                }
            },
        }
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        yaml.dump(yml, tmp)
        tmp.close()
        path = Path(tmp.name)
        try:
            config = WorkflowConfig.from_yaml(path)
            assert config.models["m1"].url == "http://test-server:9999"
        finally:
            path.unlink(missing_ok=True)
            del os.environ["_TEST_LLM_URL"]

    def test_unknown_workflow(self, client: WorkflowClient):
        with pytest.raises(KeyError, match="Unknown workflow"):
            client._resolve_workflow("does_not_exist", {})


# ======================================================================
# Message building
# ======================================================================


class TestMessageBuilding:
    def test_user_prompt_only(self, client: WorkflowClient):
        messages = client._build_messages(
            config_system=None,
            messages=None,
            user_prompt="Hello",
            system=None,
        )
        assert messages == [{"role": "user", "content": "Hello"}]

    def test_system_and_user_prompt(self, client: WorkflowClient):
        messages = client._build_messages(
            config_system=None,
            messages=None,
            user_prompt="Hi",
            system="You are a bot.",
        )
        assert messages == [
            {"role": "system", "content": "You are a bot."},
            {"role": "user", "content": "Hi"},
        ]

    def test_config_system_default(self, client: WorkflowClient):
        messages = client._build_messages(
            config_system="Default sys.",
            messages=None,
            user_prompt="Hello",
            system=None,
        )
        assert messages == [
            {"role": "system", "content": "Default sys."},
            {"role": "user", "content": "Hello"},
        ]

    def test_caller_overrides_config_system(self, client: WorkflowClient):
        messages = client._build_messages(
            config_system="Default sys.",
            messages=None,
            user_prompt="Hello",
            system="Override sys.",
        )
        assert messages == [
            {"role": "system", "content": "Override sys."},
            {"role": "user", "content": "Hello"},
        ]

    def test_full_messages_takes_precedence(self, client: WorkflowClient):
        """When messages is provided, user_prompt and system are ignored."""
        messages = client._build_messages(
            config_system="Default sys.",
            messages=[
                {"role": "system", "content": "Explicit sys"},
                {"role": "user", "content": "Explicit user"},
            ],
            user_prompt="Should be ignored",
            system="Should be ignored",
        )
        assert messages == [
            {"role": "system", "content": "Explicit sys"},
            {"role": "user", "content": "Explicit user"},
        ]


# ======================================================================
# Response parsing
# ======================================================================


class TestResponseParsing:
    def test_parse_valid_json_object(self, client: WorkflowClient):
        result = client._try_parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_valid_json_array(self, client: WorkflowClient):
        result = client._try_parse_json('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_parse_json_with_extra_text(self, client: WorkflowClient):
        """Model may add a preamble/explanation before the JSON block."""
        result = client._try_parse_json(
            "Here is the result:\n```json\n{\"category\": \"AI\"}\n```"
        )
        assert result == {"category": "AI"}

    def test_parse_json_with_prefix_text(self, client: WorkflowClient):
        result = client._try_parse_json(
            'Some explanation text before\n{"category": "Tech", "intent": "Try"} and after'
        )
        assert result == {"category": "Tech", "intent": "Try"}

    def test_parse_malformed_json(self, client: WorkflowClient):
        result = client._try_parse_json("This is plain text, not JSON")
        assert result is None

    def test_parse_empty_string(self, client: WorkflowClient):
        result = client._try_parse_json("")
        assert result is None


# ======================================================================
# Fallback resolution
# ======================================================================


class TestFallbackResolution:
    def test_none_fallback(self, client: WorkflowClient):
        assert client._resolve_fallback("none") is None

    def test_import_module_function(self, client: WorkflowClient):
        """json.dumps is a valid import path."""
        fn = client._resolve_fallback("json.dumps")
        assert callable(fn)
        assert fn({"a": 1}) == '{"a": 1}'

    def test_fallback_cached(self, client: WorkflowClient):
        fn1 = client._resolve_fallback("json.dumps")
        fn2 = client._resolve_fallback("json.dumps")
        assert fn1 is fn2  # same cached object

    def test_invalid_path(self, client: WorkflowClient):
        with pytest.raises(ValueError, match="Invalid fallback path"):
            client._resolve_fallback("justafunction")

    def test_nonexistent_module(self, client: WorkflowClient):
        with pytest.raises(ImportError):
            client._resolve_fallback("does_not_exist.func")

    def test_nonexistent_function(self, client: WorkflowClient):
        with pytest.raises(AttributeError):
            client._resolve_fallback("json.nonexistent_function")

    def test_fallback_called_on_error(self, client: WorkflowClient, monkeypatch):
        """When the HTTP call fails and a fallback is configured, it should be invoked."""
        yml = {
            "models": {"m1": {"url": "http://localhost:1", "model": "test", "timeout": 1}},
            "workflows": {
                "w1": {
                    "model_ref": "m1",
                    "temperature": 0.0,
                    "max_tokens": 10,
                    "output": "json",
                    "fallback": "json.dumps",
                }
            },
        }
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        yaml.dump(yml, tmp)
        tmp.close()
        path = Path(tmp.name)
        try:
            c = WorkflowClient(path)
            result = c.complete_text("w1", prompt="test")
            assert result.fallback_used
            assert result.success is True
        finally:
            path.unlink(missing_ok=True)


# ======================================================================
# Workflow resolution with overrides
# ======================================================================


class TestWorkflowResolution:
    def test_override_temperature(self, client: WorkflowClient):
        resolved = client._resolve_workflow("classify_tweet", {"temperature": 0.9})
        assert resolved["temperature"] == 0.9

    def test_override_max_tokens(self, client: WorkflowClient):
        resolved = client._resolve_workflow("classify_tweet", {"max_tokens": 999})
        assert resolved["max_tokens"] == 999

    def test_override_model_ref(self, client: WorkflowClient):
        """Override model_ref at call time."""
        resolved = client._resolve_workflow("classify_tweet", {"model_ref": "quality"})
        assert resolved["model_ref"] == "quality"

    def test_override_preserves_original(self, client: WorkflowClient):
        """Overrides don't mutate the stored config."""
        resolved = client._resolve_workflow("classify_tweet", {"temperature": 0.9})
        assert resolved["temperature"] == 0.9
        # Second call without override should get the original
        resolved2 = client._resolve_workflow("classify_tweet", {})
        assert resolved2["temperature"] == 0.0


# ======================================================================
# Integration tests (require running llm/ server)
# ======================================================================


@pytest.mark.integration
class TestIntegration:
    """These tests require the llm/ inference server to be running on localhost:8012.

    Run with::

        pytest tests/test_workflow_client.py -v -m integration
    """

    @pytest.fixture
    def live_config(self) -> Path:
        yml = {
            "models": {
                "default": {
                    "url": "http://127.0.0.1:8012",
                    "model": "gemma_e2b_q4_local",
                    "timeout": 120,
                }
            },
            "workflows": {
                "echo": {
                    "model_ref": "default",
                    "temperature": 0.0,
                    "max_tokens": 50,
                    "output": "text",
                    "system_prompt": "Repeat the user's message back verbatim.",
                    "fallback": "none",
                },
            },
        }
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        yaml.dump(yml, tmp)
        tmp.close()
        yield Path(tmp.name)
        Path(tmp.name).unlink(missing_ok=True)

    def test_basic_completion(self, live_config: Path):
        client = WorkflowClient(live_config)
        result = client.complete_text("echo", prompt="Hello world")
        assert result.success, f"Completion failed: {result.error}"
        assert result.latency_ms > 0
        assert len(result.text) > 0

    def test_json_output(self, live_config: Path):
        """Test that a workflow with output=json properly returns parsed data."""
        yml = {
            "models": {
                "default": {
                    "url": "http://127.0.0.1:8012",
                    "model": "gemma_e2b_q4_local",
                    "timeout": 120,
                }
            },
            "workflows": {
                "classify": {
                    "model_ref": "default",
                    "temperature": 0.0,
                    "max_tokens": 256,
                    "output": "json",
                    "system_prompt": (
                        "Respond ONLY with a valid JSON object on a single line. "
                        'Example: {"category": "AI"}'
                    ),
                    "fallback": "none",
                },
            },
        }
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        yaml.dump(yml, tmp)
        tmp.close()
        path = Path(tmp.name)
        try:
            client = WorkflowClient(path)
            result = client.complete_text(
                "classify",
                prompt="Classify this: A new open source LLM was released.",
            )
            assert result.success, f"JSON completion failed: {result.error}"
            assert result.data is not None, "Expected parsed JSON data"
            assert isinstance(result.data, dict), "Expected dict from JSON parsing"
        finally:
            path.unlink(missing_ok=True)

    def test_workflow_not_found(self, live_config: Path):
        client = WorkflowClient(live_config)
        with pytest.raises(KeyError, match="Unknown workflow"):
            client.complete_text("nonexistent", prompt="test")


# ======================================================================
# Error types smoke tests
# ======================================================================


class TestErrorTypes:
    def test_layers(self):
        assert issubclass(LLMTimeoutError, LLMClientError)
        assert issubclass(LLMUnavailableError, LLMClientError)
        assert issubclass(LLMBadResponseError, LLMClientError)
        assert issubclass(LLMClientError, RuntimeError)