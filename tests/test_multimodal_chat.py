import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT.parent))

from llm.llama_cpp_provider import LlamaCppProvider  # noqa: E402
from llm.openai_compatible_provider import OpenAICompatibleProvider  # noqa: E402
from llm.provider_base import CompletionResult  # noqa: E402
from llm import service_app  # noqa: E402


class StubRouter:
    def __init__(self, providers: dict[str, object]):
        self._providers = providers

    def provider_ids(self):
        return list(self._providers.keys())

    def get_provider(self, provider_id: str):
        provider = self._providers.get(provider_id)
        if provider is None:
            raise KeyError(provider_id)
        return provider


class RecordingOpenAIProvider:
    provider_name = "openai_compatible"

    def __init__(self, input_modalities=None):
        self.calls = []
        self.warmup_calls = 0
        self._input_modalities = set(input_modalities or {"text"})

    def warmup(self):
        self.warmup_calls += 1

    def supported_input_modalities(self):
        return set(self._input_modalities)

    def complete(self, prompt: str = "", system: str = "", params: dict | None = None, messages=None):
        self.calls.append(
            {
                "prompt": prompt,
                "system": system,
                "params": dict(params or {}),
                "messages": messages,
            }
        )
        return CompletionResult(
            text="ok",
            model_id="gemma_e2b_local",
            provider=self.provider_name,
            latency_ms=5,
            tokens_used=7,
        )


class RecordingNonOpenAIProvider(RecordingOpenAIProvider):
    provider_name = "llama_cpp"


class MultimodalChatTests(unittest.TestCase):
    def _create_app(self, provider):
        return service_app.create_app(service_app.LLMServiceRuntime(StubRouter({"gemma_e2b_local": provider})))

    def test_complete_chat_preserves_structured_messages_for_openai_provider(self):
        provider = RecordingOpenAIProvider(input_modalities={"text", "image"})
        runtime = service_app.LLMServiceRuntime(StubRouter({"gemma_e2b_local": provider}))
        payload = {
            "model": "gemma_e2b_local",
            "messages": [
                {"role": "system", "content": "You are concise."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What is in this image?"},
                        {"type": "image_url", "image_url": {"url": "https://example.test/cat.png"}},
                    ],
                },
            ],
            "temperature": 0.0,
            "max_tokens": 32,
        }

        response = runtime.complete_chat(payload)

        self.assertEqual(response["choices"][0]["message"]["content"], "ok")
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(provider.calls[0]["messages"], payload["messages"])
        self.assertEqual(provider.calls[0]["params"], {"temperature": 0.0, "max_tokens": 32})

    def test_string_content_requests_continue_to_work(self):
        provider = RecordingOpenAIProvider(input_modalities={"text"})
        runtime = service_app.LLMServiceRuntime(StubRouter({"gemma_e2b_local": provider}))
        payload = {
            "model": "gemma_e2b_local",
            "messages": [{"role": "user", "content": "Say hello."}],
        }

        response = runtime.complete_chat(payload)

        self.assertEqual(response["choices"][0]["message"]["content"], "ok")
        self.assertEqual(provider.calls[0]["messages"], payload["messages"])

    def test_complete_chat_preserves_audio_messages_for_openai_provider_with_active_audio_support(self):
        provider = RecordingOpenAIProvider(input_modalities={"text", "audio"})
        runtime = service_app.LLMServiceRuntime(StubRouter({"gemma_e2b_local": provider}))
        payload = {
            "model": "gemma_e2b_local",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Transcribe this."},
                        {"type": "input_audio", "input_audio": {"data": "AAAA", "format": "wav"}},
                    ],
                }
            ],
        }

        response = runtime.complete_chat(payload)

        self.assertEqual(response["choices"][0]["message"]["content"], "ok")
        self.assertEqual(provider.calls[0]["messages"], payload["messages"])

    def test_image_requests_fail_fast_when_provider_lacks_active_image_support(self):
        provider = RecordingOpenAIProvider(input_modalities={"text"})
        app = self._create_app(provider)

        response = app.test_client().post(
            "/v1/chat/completions",
            json={
                "model": "gemma_e2b_local",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "What is in this image?"},
                            {"type": "image_url", "image_url": {"url": "https://example.test/cat.png"}},
                        ],
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertEqual(body["error"]["type"], "invalid_request")
        self.assertIn("does not support image input", body["error"]["message"])
        self.assertEqual(provider.warmup_calls, 0)
        self.assertEqual(provider.calls, [])

    def test_audio_requests_fail_fast_when_provider_lacks_active_audio_support(self):
        provider = RecordingOpenAIProvider(input_modalities={"text", "image"})
        app = self._create_app(provider)

        response = app.test_client().post(
            "/v1/chat/completions",
            json={
                "model": "gemma_e2b_local",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Transcribe this."},
                            {"type": "input_audio", "input_audio": {"data": "AAAA", "format": "wav"}},
                        ],
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertEqual(body["error"]["type"], "invalid_request")
        self.assertIn("does not support audio input", body["error"]["message"])
        self.assertEqual(provider.warmup_calls, 0)
        self.assertEqual(provider.calls, [])

    def test_invalid_image_url_part_is_rejected(self):
        provider = RecordingOpenAIProvider(input_modalities={"text", "image"})
        app = self._create_app(provider)

        response = app.test_client().post(
            "/v1/chat/completions",
            json={
                "model": "gemma_e2b_local",
                "messages": [{"role": "user", "content": [{"type": "image_url"}]}],
            },
        )

        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertEqual(body["error"]["type"], "invalid_request")
        self.assertIn("image_url content parts require image_url.url", body["error"]["message"])
        self.assertEqual(provider.calls, [])

    def test_unknown_structured_content_type_is_rejected(self):
        provider = RecordingOpenAIProvider(input_modalities={"text", "image"})
        app = self._create_app(provider)

        response = app.test_client().post(
            "/v1/chat/completions",
            json={
                "model": "gemma_e2b_local",
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "video_url", "video_url": {"url": "https://example.test/video.mp4"}}],
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertEqual(body["error"]["type"], "invalid_request")
        self.assertIn("unsupported content part type", body["error"]["message"])
        self.assertEqual(provider.calls, [])

    def test_content_must_be_string_or_list(self):
        provider = RecordingOpenAIProvider(input_modalities={"text"})
        app = self._create_app(provider)

        response = app.test_client().post(
            "/v1/chat/completions",
            json={
                "model": "gemma_e2b_local",
                "messages": [{"role": "user", "content": 123}],
            },
        )

        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertEqual(body["error"]["type"], "invalid_request")
        self.assertIn("message content must be a string or list of content parts", body["error"]["message"])
        self.assertEqual(provider.calls, [])

    def test_content_parts_must_be_objects(self):
        provider = RecordingOpenAIProvider(input_modalities={"text"})
        app = self._create_app(provider)

        response = app.test_client().post(
            "/v1/chat/completions",
            json={
                "model": "gemma_e2b_local",
                "messages": [{"role": "user", "content": ["not-an-object"]}],
            },
        )

        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertEqual(body["error"]["type"], "invalid_request")
        self.assertIn("content parts must contain objects", body["error"]["message"])
        self.assertEqual(provider.calls, [])

    def test_missing_model_is_rejected(self):
        provider = RecordingOpenAIProvider(input_modalities={"text"})
        app = self._create_app(provider)

        response = app.test_client().post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )

        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertEqual(body["error"]["type"], "invalid_request")
        self.assertIn("model is required", body["error"]["message"])
        self.assertEqual(provider.calls, [])

    def test_missing_messages_are_rejected(self):
        provider = RecordingOpenAIProvider(input_modalities={"text"})
        app = self._create_app(provider)

        response = app.test_client().post("/v1/chat/completions", json={"model": "gemma_e2b_local"})

        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertEqual(body["error"]["type"], "invalid_request")
        self.assertIn("messages must be a non-empty list", body["error"]["message"])
        self.assertEqual(provider.calls, [])

    def test_empty_messages_are_rejected(self):
        provider = RecordingOpenAIProvider(input_modalities={"text"})
        app = self._create_app(provider)

        response = app.test_client().post(
            "/v1/chat/completions",
            json={"model": "gemma_e2b_local", "messages": []},
        )

        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertEqual(body["error"]["type"], "invalid_request")
        self.assertIn("messages must be a non-empty list", body["error"]["message"])
        self.assertEqual(provider.calls, [])

    def test_non_object_message_items_are_rejected(self):
        provider = RecordingOpenAIProvider(input_modalities={"text"})
        app = self._create_app(provider)

        response = app.test_client().post(
            "/v1/chat/completions",
            json={"model": "gemma_e2b_local", "messages": ["not-an-object"]},
        )

        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertEqual(body["error"]["type"], "invalid_request")
        self.assertIn("messages must contain objects", body["error"]["message"])
        self.assertEqual(provider.calls, [])

    def test_missing_role_is_rejected(self):
        provider = RecordingOpenAIProvider(input_modalities={"text"})
        app = self._create_app(provider)

        response = app.test_client().post(
            "/v1/chat/completions",
            json={"model": "gemma_e2b_local", "messages": [{"content": "hello"}]},
        )

        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertEqual(body["error"]["type"], "invalid_request")
        self.assertIn("messages must include role", body["error"]["message"])

    def test_missing_content_is_rejected(self):
        provider = RecordingOpenAIProvider(input_modalities={"text"})
        app = self._create_app(provider)

        response = app.test_client().post(
            "/v1/chat/completions",
            json={"model": "gemma_e2b_local", "messages": [{"role": "user"}]},
        )

        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertEqual(body["error"]["type"], "invalid_request")
        self.assertIn("messages must include content", body["error"]["message"])

    def test_text_content_parts_require_text_field(self):
        provider = RecordingOpenAIProvider(input_modalities={"text"})
        app = self._create_app(provider)

        response = app.test_client().post(
            "/v1/chat/completions",
            json={
                "model": "gemma_e2b_local",
                "messages": [{"role": "user", "content": [{"type": "text"}]}],
            },
        )

        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertEqual(body["error"]["type"], "invalid_request")
        self.assertIn("text content parts require text", body["error"]["message"])

    def test_input_audio_parts_require_audio_fields(self):
        provider = RecordingOpenAIProvider(input_modalities={"text", "audio"})
        app = self._create_app(provider)

        response = app.test_client().post(
            "/v1/chat/completions",
            json={
                "model": "gemma_e2b_local",
                "messages": [
                    {"role": "user", "content": [{"type": "input_audio", "input_audio": {"data": "AAAA"}}]}
                ],
            },
        )

        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertEqual(body["error"]["type"], "invalid_request")
        self.assertIn("input_audio content parts require input_audio.data and input_audio.format", body["error"]["message"])

    def test_timeout_seconds_is_passed_through_at_service_boundary(self):
        provider = RecordingOpenAIProvider(input_modalities={"text"})
        runtime = service_app.LLMServiceRuntime(StubRouter({"gemma_e2b_local": provider}))

        runtime.complete_chat(
            {
                "model": "gemma_e2b_local",
                "messages": [{"role": "user", "content": "hello"}],
                "timeout_seconds": 123,
            }
        )

        self.assertEqual(provider.calls[0]["params"], {"timeout_seconds": 123})

    def test_managed_openai_provider_with_image_capability_but_no_mmproj_rejects_image_requests(self):
        provider = OpenAICompatibleProvider(
            model_id="gemma_e2b_local",
            base_url="http://example.test",
            model_name="gemma_e2b_local",
            managed_server={"mmproj_path_env": "UNSET_MMPROJ_PATH"},
            input_modalities={"text", "image"},
        )
        app = self._create_app(provider)

        response = app.test_client().post(
            "/v1/chat/completions",
            json={
                "model": "gemma_e2b_local",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "describe this"},
                            {"type": "image_url", "image_url": {"url": "https://example.test/cat.png"}},
                        ],
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertEqual(body["error"]["type"], "invalid_request")
        self.assertIn("does not support image input", body["error"]["message"])

    def test_text_part_arrays_do_not_require_mmproj(self):
        provider = OpenAICompatibleProvider(
            model_id="gemma_e2b_local",
            base_url="http://example.test",
            model_name="gemma_e2b_local",
            managed_server={"mmproj_path_env": "UNSET_MMPROJ_PATH"},
            input_modalities={"text", "image"},
        )
        provider._managed_runtime_ready = True
        with unittest.mock.patch("llm.openai_compatible_provider.requests.post") as post:
            response = unittest.mock.Mock()
            response.status_code = 200
            response.json.return_value = {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"total_tokens": 1},
            }
            post.return_value = response
            runtime = service_app.LLMServiceRuntime(StubRouter({"gemma_e2b_local": provider}))
            result = runtime.complete_chat(
                {
                    "model": "gemma_e2b_local",
                    "messages": [{"role": "user", "content": [{"type": "text", "text": "hello"}]}],
                }
            )

        self.assertEqual(result["choices"][0]["message"]["content"], "ok")

    def test_structured_multimodal_requests_are_rejected_for_non_openai_providers(self):
        provider = RecordingNonOpenAIProvider(input_modalities={"text", "image"})
        app = self._create_app(provider)

        response = app.test_client().post(
            "/v1/chat/completions",
            json={
                "model": "gemma_e2b_local",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "describe this"},
                            {"type": "image_url", "image_url": {"url": "https://example.test/cat.png"}},
                        ],
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertEqual(body["error"]["type"], "invalid_request")
        self.assertIn("only supported for openai_compatible providers", body["error"]["message"])
        self.assertEqual(provider.calls, [])

    def test_actual_llama_cpp_provider_rejects_structured_multimodal_requests_at_service_boundary(self):
        provider = LlamaCppProvider(
            model_id="gemma_e2b_local",
            binary_path="/tmp/llama-cli",
            model_path="/tmp/model.gguf",
        )
        provider.complete = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("complete should not be called"))
        app = self._create_app(provider)

        response = app.test_client().post(
            "/v1/chat/completions",
            json={
                "model": "gemma_e2b_local",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "describe this"},
                            {"type": "image_url", "image_url": {"url": "https://example.test/cat.png"}},
                        ],
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"]["type"], "invalid_request")


if __name__ == "__main__":
    unittest.main()
