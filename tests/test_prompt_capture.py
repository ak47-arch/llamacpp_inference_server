import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT.parent))

from llm import monitoring, prompt_capture, service_app  # noqa: E402
from llm.provider_base import CompletionResult  # noqa: E402


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


class StubProvider:
    provider_name = "openai_compatible"

    def __init__(self, text: str = "assistant-secret"):
        self.text = text

    def warmup(self):
        return None

    def supported_input_modalities(self):
        return {"text", "image", "audio"}

    def complete(self, prompt: str = "", system: str = "", params: dict | None = None, messages=None):
        return CompletionResult(
            text=self.text,
            model_id="gemma_e4b_q4_local",
            provider=self.provider_name,
            latency_ms=1,
            tokens_used=11,
        )


class FailingSink:
    def write(self, record: dict) -> None:
        raise RuntimeError("sink boom")


class PromptCaptureTests(unittest.TestCase):
    def setUp(self):
        monitoring.reset_metrics()
        provider = StubProvider()
        runtime = service_app.LLMServiceRuntime(StubRouter({"gemma_e4b_q4_local": provider}))
        self.runtime = runtime

    def _create_app(self, capture_manager=None):
        return service_app.create_app(runtime=self.runtime, capture_manager=capture_manager)

    def _payload(self):
        return {
            "model": "gemma_e4b_q4_local",
            "messages": [{"role": "user", "content": "super-secret-prompt"}],
        }

    def _read_records(self, path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    def test_prompt_capture_is_disabled_by_default(self):
        app = self._create_app()

        response = app.test_client().post("/v1/chat/completions", json=self._payload())

        self.assertEqual(response.status_code, 200)
        manager = app.extensions["prompt_capture_manager"]
        self.assertFalse(manager.enabled)
        metrics = app.test_client().get("/metrics").get_data(as_text=True)
        self.assertNotIn("llm_prompt_capture_records_total{", metrics)

    def test_metadata_mode_persists_sanitized_record_without_prompt_or_completion_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "capture.ndjson"
            manager = prompt_capture.PromptCaptureManager(
                config=prompt_capture.PromptCaptureConfig(mode="metadata"),
                sink=prompt_capture.NDJSONCaptureSink(output_path),
            )
            app = self._create_app(manager)

            response = app.test_client().post("/v1/chat/completions", json=self._payload())
            manager.flush()

            self.assertEqual(response.status_code, 200)
            records = self._read_records(output_path)
            self.assertEqual(len(records), 1)
            record = records[0]
            self.assertTrue(record["request_id"].startswith("req_"))
            self.assertEqual(record["capture_mode"], "metadata")
            self.assertEqual(record["request"]["message_count"], 1)
            self.assertEqual(record["request"]["input_modalities"], ["text"])
            serialized = json.dumps(record)
            self.assertNotIn("super-secret-prompt", serialized)
            self.assertNotIn("assistant-secret", serialized)

    def test_full_mode_persists_messages_and_response_while_excluding_system_prompts_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "capture.ndjson"
            manager = prompt_capture.PromptCaptureManager(
                config=prompt_capture.PromptCaptureConfig(mode="full"),
                sink=prompt_capture.NDJSONCaptureSink(output_path),
            )
            app = self._create_app(manager)
            payload = {
                "model": "gemma_e4b_q4_local",
                "messages": [
                    {"role": "system", "content": "system-secret"},
                    {"role": "user", "content": "super-secret-prompt"},
                ],
            }

            response = app.test_client().post("/v1/chat/completions", json=payload)
            manager.flush()

            self.assertEqual(response.status_code, 200)
            records = self._read_records(output_path)
            record = records[0]
            self.assertEqual(record["capture_mode"], "full")
            self.assertEqual(record["request"]["system_prompt_included"], False)
            self.assertEqual(record["request"]["messages"], [{"role": "user", "content": "super-secret-prompt"}])
            self.assertEqual(record["response"]["assistant_text"], "assistant-secret")
            self.assertNotIn("system-secret", json.dumps(record))

    def test_full_mode_can_include_system_prompts_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "capture.ndjson"
            manager = prompt_capture.PromptCaptureManager(
                config=prompt_capture.PromptCaptureConfig(mode="full", include_system_prompts=True),
                sink=prompt_capture.NDJSONCaptureSink(output_path),
            )
            app = self._create_app(manager)
            payload = {
                "model": "gemma_e4b_q4_local",
                "messages": [
                    {"role": "system", "content": "system-secret"},
                    {"role": "user", "content": "super-secret-prompt"},
                ],
            }

            response = app.test_client().post("/v1/chat/completions", json=payload)
            manager.flush()

            self.assertEqual(response.status_code, 200)
            record = self._read_records(output_path)[0]
            self.assertEqual(record["request"]["system_prompt_included"], True)
            self.assertEqual(
                record["request"]["messages"],
                [
                    {"role": "system", "content": "system-secret"},
                    {"role": "user", "content": "super-secret-prompt"},
                ],
            )

    def test_full_mode_replaces_inline_media_with_metadata_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "capture.ndjson"
            manager = prompt_capture.PromptCaptureManager(
                config=prompt_capture.PromptCaptureConfig(mode="full"),
                sink=prompt_capture.NDJSONCaptureSink(output_path),
            )
            app = self._create_app(manager)
            payload = {
                "model": "gemma_e4b_q4_local",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "describe these"},
                            {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJDRA=="}},
                            {"type": "input_audio", "input_audio": {"data": "VEVTVA==", "format": "wav"}},
                        ],
                    }
                ],
            }

            response = app.test_client().post("/v1/chat/completions", json=payload)
            manager.flush()

            self.assertEqual(response.status_code, 200)
            record = self._read_records(output_path)[0]
            content = record["request"]["messages"][0]["content"]
            self.assertEqual(content[0], {"type": "text", "text": "describe these"})
            self.assertEqual(content[1]["type"], "image_url")
            self.assertEqual(content[1]["image_url"]["stored"], False)
            self.assertEqual(content[1]["image_url"]["source"], "inline")
            self.assertIn("sha256", content[1]["image_url"])
            self.assertEqual(content[2]["type"], "input_audio")
            self.assertEqual(content[2]["input_audio"]["stored"], False)
            self.assertEqual(content[2]["input_audio"]["format"], "wav")
            self.assertIn("sha256", content[2]["input_audio"])
            serialized = json.dumps(record)
            self.assertNotIn("QUJDRA==", serialized)
            self.assertNotIn("VEVTVA==", serialized)

    def test_sink_failure_does_not_fail_inference_and_emits_failed_capture_metric(self):
        manager = prompt_capture.PromptCaptureManager(
            config=prompt_capture.PromptCaptureConfig(mode="full"),
            sink=FailingSink(),
        )
        app = self._create_app(manager)

        response = app.test_client().post("/v1/chat/completions", json=self._payload())
        manager.flush()

        self.assertEqual(response.status_code, 200)
        metrics = app.test_client().get("/metrics").get_data(as_text=True)
        self.assertIn('llm_prompt_capture_records_total{mode="full",result="failed"} 1.0', metrics)

    def test_full_queue_drops_capture_without_failing_inference(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "capture.ndjson"
            manager = prompt_capture.PromptCaptureManager(
                config=prompt_capture.PromptCaptureConfig(mode="metadata", queue_max_records=1),
                sink=prompt_capture.NDJSONCaptureSink(output_path),
                autostart=False,
            )
            app = self._create_app(manager)

            first = app.test_client().post("/v1/chat/completions", json=self._payload())
            second = app.test_client().post("/v1/chat/completions", json=self._payload())

            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 200)
            metrics = app.test_client().get("/metrics").get_data(as_text=True)
            self.assertIn('llm_prompt_capture_records_total{mode="metadata",result="dropped"} 1.0', metrics)


if __name__ == "__main__":
    unittest.main()
