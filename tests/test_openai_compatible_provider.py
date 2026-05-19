import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT.parent))

from llm import local_server_runtime  # noqa: E402
from llm.llama_cpp_provider import LlamaCppProvider  # noqa: E402
from llm.openai_compatible_provider import OpenAICompatibleProvider  # noqa: E402
from llm.provider_base import ProviderUnavailableError  # noqa: E402


class OpenAICompatibleProviderSpecTests(unittest.TestCase):
    def test_bundled_openai_example_providers_do_not_define_temperature_or_max_tokens_defaults(self):
        config = yaml.safe_load((REPO_ROOT / "service_models.yaml").read_text())
        bundled_ids = {"gemma_e4b_q4_local"}
        for provider in config["providers"]:
            if provider["id"] not in bundled_ids:
                continue
            with self.subTest(provider=provider["id"]):
                default_params = provider.get("default_params", {})
                self.assertTrue(set(default_params.keys()).issubset({"timeout_seconds"}))
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
        self.assertEqual(post.call_args.args[0], "http://example.test/v1/chat/completions")
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
        self.assertNotIn("timeout_seconds", post.call_args.kwargs["json"])

    def test_timeout_seconds_is_used_only_as_local_http_timeout(self):
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
            provider.complete("hello", params={"timeout_seconds": 321})

        self.assertEqual(post.call_args.kwargs["timeout"], 321)
        self.assertNotIn("timeout_seconds", post.call_args.kwargs["json"])

    def test_provider_configured_timeout_is_used_when_caller_omits_it(self):
        provider = OpenAICompatibleProvider(
            model_id="test_provider",
            base_url="http://example.test",
            model_name="test-model",
            default_params={"timeout_seconds": 111},
        )

        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"total_tokens": 3},
        }

        with patch("llm.openai_compatible_provider.requests.post", return_value=response) as post:
            provider.complete("hello")

        self.assertEqual(post.call_args.kwargs["timeout"], 111)
        self.assertNotIn("timeout_seconds", post.call_args.kwargs["json"])

    def test_request_timeout_overrides_provider_configured_timeout(self):
        provider = OpenAICompatibleProvider(
            model_id="test_provider",
            base_url="http://example.test",
            model_name="test-model",
            default_params={"timeout_seconds": 111},
        )

        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"total_tokens": 3},
        }

        with patch("llm.openai_compatible_provider.requests.post", return_value=response) as post:
            provider.complete("hello", params={"timeout_seconds": 222})

        self.assertEqual(post.call_args.kwargs["timeout"], 222)
        self.assertNotIn("timeout_seconds", post.call_args.kwargs["json"])

    def test_complete_forwards_structured_messages_without_rebuilding_them(self):
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
        messages = [
            {"role": "system", "content": "You are concise."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What is in this image?"},
                    {"type": "image_url", "image_url": {"url": "https://example.test/cat.png"}},
                ],
            },
        ]

        with patch("llm.openai_compatible_provider.requests.post", return_value=response) as post:
            provider.complete(messages=messages)

        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["messages"], messages)
        self.assertNotIn("prompt", json.dumps(payload))

    def test_complete_forwards_valid_audio_messages_when_audio_support_is_active(self):
        provider = OpenAICompatibleProvider(
            model_id="test_provider",
            base_url="http://example.test",
            model_name="test-model",
            input_modalities={"text", "audio"},
        )

        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"total_tokens": 3},
        }
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Transcribe this."},
                    {"type": "input_audio", "input_audio": {"data": "AAAA", "format": "wav"}},
                ],
            }
        ]

        with patch("llm.openai_compatible_provider.requests.post", return_value=response) as post:
            provider.complete(messages=messages)

        self.assertEqual(post.call_args.kwargs["json"]["messages"], messages)

    def test_supported_input_modalities_default_to_text_only_when_unset(self):
        provider = OpenAICompatibleProvider(
            model_id="test_provider",
            base_url="http://example.test",
            model_name="test-model",
        )
        self.assertEqual(provider.supported_input_modalities(), {"text"})

    def test_invalid_input_modalities_are_rejected(self):
        with self.assertRaises(ValueError):
            OpenAICompatibleProvider(
                model_id="test_provider",
                base_url="http://example.test",
                model_name="test-model",
                input_modalities={"text", "video"},
            )

    def test_supported_input_modalities_require_resolved_mmproj_for_image_support(self):
        provider = OpenAICompatibleProvider(
            model_id="test_provider",
            base_url="http://example.test",
            model_name="test-model",
            managed_server={"mmproj_path_env": "TEST_MMPROJ_PATH"},
            input_modalities={"text", "image"},
        )

        with patch.dict("os.environ", {}, clear=False):
            self.assertEqual(provider.supported_input_modalities(), {"text"})

        with patch.dict("os.environ", {"TEST_MMPROJ_PATH": "/models/mmproj.gguf"}, clear=False):
            self.assertEqual(provider.supported_input_modalities(), {"text", "image"})

    def test_mmproj_resolution_prefers_environment_and_falls_back_to_configured_path(self):
        provider = OpenAICompatibleProvider(
            model_id="test_provider",
            base_url="http://example.test",
            model_name="test-model",
            managed_server={
                "mmproj_path_env": "TEST_MMPROJ_PATH",
                "mmproj_path": "/models/fallback-mmproj.gguf",
            },
            input_modalities={"text", "image"},
        )

        with patch.dict("os.environ", {}, clear=False):
            self.assertEqual(provider.resolved_mmproj_path(), "/models/fallback-mmproj.gguf")

        with patch.dict("os.environ", {"TEST_MMPROJ_PATH": "/models/env-mmproj.gguf"}, clear=False):
            self.assertEqual(provider.resolved_mmproj_path(), "/models/env-mmproj.gguf")
            self.assertEqual(provider.supported_input_modalities(), {"text", "image"})

        with patch.dict("os.environ", {"TEST_MMPROJ_PATH": ""}, clear=False):
            self.assertEqual(provider.resolved_mmproj_path(), "/models/fallback-mmproj.gguf")

    def test_build_server_command_adds_mmproj_only_when_resolved_and_never_uses_network_download_flags(self):
        with patch.dict("os.environ", {"TEST_MMPROJ_PATH": "/models/mmproj.gguf"}, clear=False):
            command = local_server_runtime._build_server_command(
                binary_path="/opt/llama-cpp/llama-server",
                model_path="/models/model.gguf",
                model_name="gemma_e2b_local",
                base_url="http://127.0.0.1:18012",
                server_config={"mmproj_path_env": "TEST_MMPROJ_PATH"},
                default_params={},
            )

        self.assertIn("--mmproj", command)
        self.assertIn("/models/mmproj.gguf", command)
        self.assertNotIn("--mmproj-url", command)
        self.assertNotIn("--hf-repo", command)
        self.assertNotIn("-hf", command)

        command_with_fallback = local_server_runtime._build_server_command(
            binary_path="/opt/llama-cpp/llama-server",
            model_path="/models/model.gguf",
            model_name="gemma_e2b_local",
            base_url="http://127.0.0.1:18012",
            server_config={"mmproj_path": "/models/fallback-mmproj.gguf"},
            default_params={},
        )
        self.assertIn("--mmproj", command_with_fallback)
        self.assertIn("/models/fallback-mmproj.gguf", command_with_fallback)

        command_without_mmproj = local_server_runtime._build_server_command(
            binary_path="/opt/llama-cpp/llama-server",
            model_path="/models/model.gguf",
            model_name="gemma_e2b_local",
            base_url="http://127.0.0.1:18012",
            server_config={},
            default_params={},
        )
        self.assertNotIn("--mmproj", command_without_mmproj)

    def test_upstream_non_200_response_surfaces_provider_unavailable(self):
        provider = OpenAICompatibleProvider(
            model_id="test_provider",
            base_url="http://example.test",
            model_name="test-model",
        )

        response = Mock()
        response.status_code = 400
        response.text = '{"error":"bad request"}'

        with patch("llm.openai_compatible_provider.requests.post", return_value=response):
            with self.assertRaises(ProviderUnavailableError):
                provider.complete("hello")

    def test_connection_error_resets_managed_runtime_ready_and_surfaces_unavailable(self):
        provider = OpenAICompatibleProvider(
            model_id="test_provider",
            base_url="http://example.test",
            model_name="test-model",
            managed_server={"mmproj_path_env": "TEST_MMPROJ_PATH"},
            input_modalities={"text", "image"},
        )
        provider._managed_runtime_ready = True

        with patch(
            "llm.openai_compatible_provider.requests.post",
            side_effect=__import__("requests").exceptions.ConnectionError("nope"),
        ):
            with self.assertRaises(ProviderUnavailableError):
                provider.complete("hello")

        self.assertFalse(provider._managed_runtime_ready)

    def test_repository_does_not_attempt_multimodal_auto_downloads_when_resolving_projector_support(self):
        provider = OpenAICompatibleProvider(
            model_id="test_provider",
            base_url="http://example.test",
            model_name="test-model",
            managed_server={"mmproj_path_env": "TEST_MMPROJ_PATH"},
            input_modalities={"text", "image"},
        )

        with patch("requests.get", side_effect=AssertionError("network fetch should not occur"), create=True), patch(
            "urllib.request.urlretrieve", side_effect=AssertionError("download should not occur"), create=True
        ):
            with patch.dict("os.environ", {}, clear=False):
                self.assertIsNone(provider.resolved_mmproj_path())
                command = local_server_runtime._build_server_command(
                    binary_path="/opt/llama-cpp/llama-server",
                    model_path="/models/model.gguf",
                    model_name="gemma_e2b_local",
                    base_url="http://127.0.0.1:18012",
                    server_config={"mmproj_path_env": "TEST_MMPROJ_PATH"},
                    default_params={},
                )

        self.assertNotIn("--mmproj", command)

        scanned_paths = list(REPO_ROOT.glob("*.py")) + [
            REPO_ROOT / "service_models.yaml",
            REPO_ROOT / "Dockerfile",
            REPO_ROOT / "README.md",
        ]
        forbidden_tokens = [
            "snapshot_download",
            "huggingface_hub",
            "--mmproj-url",
            "--hf-repo",
            "urlretrieve(",
            "requests.get(",
            "https://huggingface.co",
        ]
        for path in scanned_paths:
            content = path.read_text()
            for token in forbidden_tokens:
                with self.subTest(path=path.name, token=token):
                    self.assertNotIn(token, content)

    def test_direct_llama_cpp_provider_remains_text_only(self):
        provider = LlamaCppProvider(
            model_id="test_provider",
            binary_path="/tmp/llama-cli",
            model_path="/tmp/model.gguf",
        )
        self.assertEqual(provider.supported_input_modalities(), {"text"})


if __name__ == "__main__":
    unittest.main()
