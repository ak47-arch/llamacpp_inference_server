import io
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT.parent))

from llm import local_server_runtime, service_app  # noqa: E402
from llm.provider_base import ProviderTimeoutError  # noqa: E402


class SuccessRuntime:
    def readiness(self):
        return {"ready": True, "models": []}

    def complete_chat(self, payload: dict):
        return {
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "created": 1,
            "model": payload["model"],
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "ok"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": None, "completion_tokens": None, "total_tokens": 1},
        }


class InvalidRuntime:
    def readiness(self):
        return {"ready": True, "models": []}

    def complete_chat(self, payload: dict):
        raise ValueError("messages must be a non-empty list")


class TimeoutRuntime:
    def readiness(self):
        return {"ready": True, "models": []}

    def complete_chat(self, payload: dict):
        raise ProviderTimeoutError("provider timed out")


class UnavailableRuntime:
    def readiness(self):
        return {"ready": True, "models": []}

    def complete_chat(self, payload: dict):
        raise RuntimeError("provider is unavailable")


class UnhandledRuntime:
    def readiness(self):
        return {"ready": True, "models": []}

    def complete_chat(self, payload: dict):
        raise Exception("boom")


class BlockingStream:
    def __init__(self):
        self._wait_forever = threading.Event()

    def __iter__(self):
        return self

    def __next__(self):
        self._wait_forever.wait()
        raise StopIteration


class OperationalLoggingTests(unittest.TestCase):
    def setUp(self):
        local_server_runtime.reset_managed_servers()

    def tearDown(self):
        local_server_runtime.reset_managed_servers()

    def _chat_payload(self):
        return {
            "model": "gemma_e2b_local",
            "messages": [{"role": "user", "content": "super-secret-prompt"}],
        }

    def test_successful_request_emits_access_log_without_prompt_content(self):
        app = service_app.create_app(SuccessRuntime())

        with self.assertLogs("llm.service", level="INFO") as captured:
            response = app.test_client().post("/v1/chat/completions", json=self._chat_payload())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["choices"][0]["message"]["content"], "ok")
        combined = "\n".join(captured.output)
        self.assertIn("method=POST", combined)
        self.assertIn("path=/v1/chat/completions", combined)
        self.assertIn("status=200", combined)
        self.assertIn("duration_seconds=", combined)
        self.assertNotIn("super-secret-prompt", combined)

    def test_invalid_request_emits_access_and_client_error_summary_without_body_leakage(self):
        app = service_app.create_app(InvalidRuntime())
        payload = {
            "model": "gemma_e2b_local",
            "messages": [{"role": "user", "content": "should-not-be-logged"}],
            "api_key": "sk-secret",
            "authorization": "Bearer secret",
            "image_url": "https://example.test/cat.png",
            "audio_url": "https://example.test/audio.wav",
            "inline_media": "data:image/png;base64,AAAA",
        }

        with self.assertLogs("llm.service", level="INFO") as captured:
            response = app.test_client().post("/v1/chat/completions", json=payload)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"]["type"], "invalid_request")
        combined = "\n".join(captured.output)
        self.assertIn("path=/v1/chat/completions", combined)
        self.assertIn("status=400", combined)
        self.assertIn("error_class=client_error", combined)
        self.assertNotIn("should-not-be-logged", combined)
        self.assertNotIn("messages", combined)
        self.assertNotIn("Bearer secret", combined)
        self.assertNotIn("sk-secret", combined)
        self.assertNotIn("https://example.test/cat.png", combined)
        self.assertNotIn("https://example.test/audio.wav", combined)
        self.assertNotIn("data:image/png;base64,AAAA", combined)

    def test_timeout_emits_access_and_timeout_summary(self):
        app = service_app.create_app(TimeoutRuntime())

        with self.assertLogs("llm.service", level="INFO") as captured:
            response = app.test_client().post("/v1/chat/completions", json=self._chat_payload())

        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.get_json()["error"]["type"], "timeout")
        combined = "\n".join(captured.output)
        self.assertIn("path=/v1/chat/completions", combined)
        self.assertIn("status=504", combined)
        self.assertIn("error_class=timeout", combined)
        self.assertNotIn("super-secret-prompt", combined)

    def test_unavailable_emits_access_and_unavailable_summary(self):
        app = service_app.create_app(UnavailableRuntime())

        with self.assertLogs("llm.service", level="INFO") as captured:
            response = app.test_client().post("/v1/chat/completions", json=self._chat_payload())

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"]["type"], "runtime_unavailable")
        combined = "\n".join(captured.output)
        self.assertIn("path=/v1/chat/completions", combined)
        self.assertIn("status=503", combined)
        self.assertIn("error_class=unavailable", combined)
        self.assertNotIn("super-secret-prompt", combined)

    def test_unhandled_exception_emits_access_and_server_error_summary(self):
        app = service_app.create_app(UnhandledRuntime())

        with self.assertLogs("llm.service", level="INFO") as captured:
            response = app.test_client().post("/v1/chat/completions", json=self._chat_payload())

        self.assertEqual(response.status_code, 500)
        combined = "\n".join(captured.output)
        self.assertIn("path=/v1/chat/completions", combined)
        self.assertIn("status=500", combined)
        self.assertIn("error_class=server_error", combined)
        self.assertNotIn("super-secret-prompt", combined)

    def test_container_runtime_defaults_enable_stdout_stderr_logging_without_external_shipping(self):
        dockerfile = (REPO_ROOT / "Dockerfile").read_text()
        compose = (REPO_ROOT / "docker-compose.yml").read_text()

        self.assertIn("--access-logfile -", dockerfile)
        self.assertIn("--error-logfile -", dockerfile)
        self.assertNotIn("logging:", compose)
        self.assertNotIn("fluentd", compose)
        self.assertNotIn("gelf", compose)
        self.assertNotIn("awslogs", compose)
        self.assertNotIn("loki", compose)

        for path in (REPO_ROOT / "service_app.py", REPO_ROOT / "local_server_runtime.py"):
            content = path.read_text()
            self.assertNotIn("FileHandler(", content)
            self.assertNotIn("RotatingFileHandler(", content)
            self.assertNotIn("TimedRotatingFileHandler(", content)
            self.assertNotIn("logging.basicConfig(filename=", content)

    def test_local_app_logging_works_without_docker_or_external_sink(self):
        app = service_app.create_app(SuccessRuntime())

        with self.assertLogs("llm.service", level="INFO") as captured:
            app.test_client().get("/health")

        self.assertTrue(captured.output)
        self.assertIn("path=/health", "\n".join(captured.output))

    def test_sanitize_child_log_line_drops_sensitive_payloads(self):
        self.assertIsNone(local_server_runtime._sanitize_child_log_line('Authorization: Bearer secret'))
        self.assertIsNone(local_server_runtime._sanitize_child_log_line('data:image/png;base64,AAAA'))
        self.assertIsNone(local_server_runtime._sanitize_child_log_line('https://example.test/cat.png'))
        self.assertIsNone(local_server_runtime._sanitize_child_log_line('https://example.test/audio.wav'))
        self.assertIsNone(local_server_runtime._sanitize_child_log_line('{"messages": [{"role": "user", "content": "hello"}]}'))
        self.assertIsNone(local_server_runtime._sanitize_child_log_line('api_key=sk-secret'))

    def test_sanitize_child_log_line_allows_safe_lifecycle_text(self):
        sanitized = local_server_runtime._sanitize_child_log_line('HTTP server listening on 127.0.0.1:18012')
        self.assertEqual(sanitized, 'HTTP server listening on 127.0.0.1:18012')

    def test_ensure_managed_server_logs_launch_ready_and_forwarded_safe_child_line(self):
        process = Mock()
        process.poll.return_value = None
        process.stdout = io.StringIO('HTTP server listening on 127.0.0.1:18012\n')
        process.stderr = io.StringIO('')

        with self.assertLogs("llm.runtime", level="INFO") as captured:
            with patch.object(local_server_runtime, "_server_is_ready", return_value=False), patch.object(
                local_server_runtime, "_wait_for_server", return_value=None
            ), patch.object(local_server_runtime.subprocess, "Popen", return_value=process):
                local_server_runtime.ensure_managed_server(
                    base_url="http://127.0.0.1:18012",
                    binary_path="/opt/llama-cpp/llama-server",
                    model_path="/models/model.gguf",
                    model_name="gemma_e2b_local",
                    model_id="gemma_e2b_local",
                    server_config={},
                    default_params={},
                )

        combined = "\n".join(captured.output)
        self.assertIn("event=launch", combined)
        self.assertIn("event=ready", combined)
        self.assertTrue(
            any(
                "model=gemma_e2b_local" in line
                and "base_url=http://127.0.0.1:18012" in line
                and "stream=stdout" in line
                and "HTTP server listening on 127.0.0.1:18012" in line
                for line in captured.output
            )
        )

    def test_ensure_managed_server_sets_ld_library_path_for_binary_directory(self):
        process = Mock()
        process.poll.return_value = None
        process.stdout = io.StringIO('')
        process.stderr = io.StringIO('')

        with patch.object(local_server_runtime, "_server_is_ready", return_value=False), patch.object(
            local_server_runtime, "_wait_for_server", return_value=None
        ), patch.object(local_server_runtime.subprocess, "Popen", return_value=process) as popen:
            local_server_runtime.ensure_managed_server(
                base_url="http://127.0.0.1:18012",
                binary_path="/opt/llama-cpp/llama-server",
                model_path="/models/model.gguf",
                model_name="gemma_e2b_local",
                model_id="gemma_e2b_local",
                server_config={},
                default_params={},
            )

        env = popen.call_args.kwargs["env"]
        self.assertIn("LD_LIBRARY_PATH", env)
        self.assertIn("/opt/llama-cpp", env["LD_LIBRARY_PATH"].split(":"))

    def test_ensure_managed_server_returns_without_waiting_for_child_log_eof(self):
        process = Mock()
        process.poll.return_value = None
        process.stdout = BlockingStream()
        process.stderr = BlockingStream()
        done = threading.Event()
        errors = []

        def target():
            try:
                with patch.object(local_server_runtime, "_server_is_ready", return_value=False), patch.object(
                    local_server_runtime, "_wait_for_server", return_value=None
                ), patch.object(local_server_runtime.subprocess, "Popen", return_value=process):
                    local_server_runtime.ensure_managed_server(
                        base_url="http://127.0.0.1:18012",
                        binary_path="/opt/llama-cpp/llama-server",
                        model_path="/models/model.gguf",
                        model_name="gemma_e2b_local",
                        model_id="gemma_e2b_local",
                        server_config={},
                        default_params={},
                    )
            except Exception as exc:  # pragma: no cover - assertion path only
                errors.append(exc)
            finally:
                done.set()

        worker = threading.Thread(target=target, daemon=True)
        worker.start()
        self.assertTrue(done.wait(0.5), "ensure_managed_server should not wait for child log EOF")
        self.assertEqual(errors, [])

    def test_sensitive_child_lines_are_dropped_during_forwarding(self):
        process = Mock()
        process.poll.return_value = None
        process.stdout = io.StringIO('data:image/png;base64,AAAA\n')
        process.stderr = io.StringIO('ready to serve requests\n')

        with self.assertLogs("llm.runtime", level="INFO") as captured:
            with patch.object(local_server_runtime, "_server_is_ready", return_value=False), patch.object(
                local_server_runtime, "_wait_for_server", return_value=None
            ), patch.object(local_server_runtime.subprocess, "Popen", return_value=process):
                local_server_runtime.ensure_managed_server(
                    base_url="http://127.0.0.1:18012",
                    binary_path="/opt/llama-cpp/llama-server",
                    model_path="/models/model.gguf",
                    model_name="gemma_e2b_local",
                    model_id="gemma_e2b_local",
                    server_config={},
                    default_params={},
                )

        combined = "\n".join(captured.output)
        self.assertTrue(
            any(
                "model=gemma_e2b_local" in line
                and "base_url=http://127.0.0.1:18012" in line
                and "stream=stderr" in line
                and "ready to serve requests" in line
                for line in captured.output
            )
        )
        self.assertNotIn("data:image/png;base64,AAAA", combined)

    def test_ensure_managed_server_logs_restart_before_relaunch(self):
        old_process = Mock()
        old_process.poll.return_value = 1
        new_process = Mock()
        new_process.poll.return_value = None
        new_process.stdout = io.StringIO('')
        new_process.stderr = io.StringIO('')
        local_server_runtime._managed_servers["http://127.0.0.1:18012"] = old_process

        with self.assertLogs("llm.runtime", level="INFO") as captured:
            with patch.object(local_server_runtime, "_server_is_ready", return_value=False), patch.object(
                local_server_runtime, "_wait_for_server", return_value=None
            ), patch.object(local_server_runtime.subprocess, "Popen", return_value=new_process):
                local_server_runtime.ensure_managed_server(
                    base_url="http://127.0.0.1:18012",
                    binary_path="/opt/llama-cpp/llama-server",
                    model_path="/models/model.gguf",
                    model_name="gemma_e2b_local",
                    model_id="gemma_e2b_local",
                    server_config={},
                    default_params={},
                )

        combined = "\n".join(captured.output)
        self.assertIn("event=restart", combined)
        self.assertIn("event=launch", combined)

    def test_ensure_managed_server_logs_failure_when_readiness_wait_fails(self):
        process = Mock()
        process.poll.return_value = None
        process.stdout = io.StringIO('')
        process.stderr = io.StringIO('')

        with self.assertRaises(RuntimeError):
            with self.assertLogs("llm.runtime", level="INFO") as captured:
                with patch.object(local_server_runtime, "_server_is_ready", return_value=False), patch.object(
                    local_server_runtime, "_wait_for_server", side_effect=RuntimeError("did not become ready")
                ), patch.object(local_server_runtime.subprocess, "Popen", return_value=process):
                    local_server_runtime.ensure_managed_server(
                        base_url="http://127.0.0.1:18012",
                        binary_path="/opt/llama-cpp/llama-server",
                        model_path="/models/model.gguf",
                        model_name="gemma_e2b_local",
                        model_id="gemma_e2b_local",
                        server_config={},
                        default_params={},
                    )

        combined = "\n".join(captured.output)
        self.assertIn("event=failure", combined)
        self.assertIn("base_url=http://127.0.0.1:18012", combined)

    def test_reset_managed_servers_logs_termination(self):
        process = Mock()
        process.poll.return_value = None
        local_server_runtime._managed_servers["http://127.0.0.1:18012"] = process

        with self.assertLogs("llm.runtime", level="INFO") as captured:
            local_server_runtime.reset_managed_servers()

        combined = "\n".join(captured.output)
        self.assertIn("event=terminate", combined)
        self.assertIn("base_url=http://127.0.0.1:18012", combined)


if __name__ == "__main__":
    unittest.main()
