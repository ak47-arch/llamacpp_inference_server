import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT.parent))

from llm.openai_compatible_provider import OpenAICompatibleProvider  # noqa: E402


class OpenAICompatibleProviderSpecTests(unittest.TestCase):
    def test_service_models_do_not_define_temperature_or_max_tokens_defaults(self):
        config = yaml.safe_load((REPO_ROOT / "service_models.yaml").read_text())
        for provider in config["providers"]:
            with self.subTest(provider=provider["id"]):
                default_params = provider.get("default_params", {})
                self.assertNotIn("temperature", default_params)
                self.assertNotIn("max_tokens", default_params)

    def test_complete_omits_temperature_and_max_tokens_when_unspecified(self):
        provider = OpenAICompatibleProvider(
            model_id="test_provider",
            base_url="http://example.test",
            model_name="test-model",
        )

        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"total_tokens": 3},
        }

        with patch("llm.openai_compatible_provider.requests.post", return_value=response) as post:
            provider.complete("hello")

        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(payload["messages"], [{"role": "user", "content": "hello"}])
        self.assertNotIn("temperature", payload)
        self.assertNotIn("max_tokens", payload)

    def test_complete_includes_temperature_and_max_tokens_when_configured(self):
        provider = OpenAICompatibleProvider(
            model_id="test_provider",
            base_url="http://example.test",
            model_name="test-model",
            default_params={"temperature": 0.6, "max_tokens": 321},
        )

        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"total_tokens": 3},
        }

        with patch("llm.openai_compatible_provider.requests.post", return_value=response) as post:
            provider.complete("hello")

        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["temperature"], 0.6)
        self.assertEqual(payload["max_tokens"], 321)

    def test_complete_allows_request_params_to_override_configured_values(self):
        provider = OpenAICompatibleProvider(
            model_id="test_provider",
            base_url="http://example.test",
            model_name="test-model",
            default_params={"temperature": 0.6, "max_tokens": 321},
        )

        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"total_tokens": 3},
        }

        with patch("llm.openai_compatible_provider.requests.post", return_value=response) as post:
            provider.complete("hello", params={"temperature": 0.2, "max_tokens": 12})

        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["temperature"], 0.2)
        self.assertEqual(payload["max_tokens"], 12)

    def test_complete_uses_local_timeout_fallback_when_unspecified(self):
        provider = OpenAICompatibleProvider(
            model_id="test_provider",
            base_url="http://example.test",
            model_name="test-model",
        )

        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"total_tokens": 3},
        }

        with patch("llm.openai_compatible_provider.requests.post", return_value=response) as post:
            provider.complete("hello")

        self.assertIn("timeout", post.call_args.kwargs)
        self.assertGreater(post.call_args.kwargs["timeout"], 0)


if __name__ == "__main__":
    unittest.main()
