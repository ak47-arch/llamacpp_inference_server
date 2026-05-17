import re
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT.parent))

from llm import local_server_runtime, monitoring, service_app  # noqa: E402
from llm.provider_base import CompletionResult, ProviderTimeoutError, ProviderUnavailableError  # noqa: E402


class DummyRuntime:
    def readiness(self):
        return {"ready": True, "models": []}

    def complete_chat(self, payload: dict):
        raise AssertionError("complete_chat should not be called in this test")


class StubProvider:
    def __init__(self, model_id: str, provider_name: str = "stub_provider", text: str = "ok"):
        self.model_id = model_id
        self.provider_name = provider_name
        self.text = text
        self.warmup_calls = 0
        self.complete_calls = 0
        self.block_started = None
        self.block_release = None
        self.raise_exc = None

    def warmup(self):
        self.warmup_calls += 1
        if self.raise_exc is not None:
            raise self.raise_exc

    def complete(self, prompt: str, system: str = "", params: dict | None = None):
        self.complete_calls += 1
        if self.block_started is not None:
            self.block_started.set()
        if self.block_release is not None:
            self.block_release.wait(timeout=5)
        if self.raise_exc is not None:
            raise self.raise_exc
        return CompletionResult(
            text=self.text,
            model_id=self.model_id,
            provider=self.provider_name,
            latency_ms=12,
            tokens_used=3,
        )


class StubRouter:
    def __init__(self, providers: dict[str, StubProvider]):
        self._providers = providers

    def provider_ids(self):
        return list(self._providers.keys())

    def get_provider(self, provider_id: str):
        return self._providers[provider_id]


class MonitoringSpecTests(unittest.TestCase):
    def setUp(self):
        monitoring.reset_metrics()
        local_server_runtime.reset_managed_servers()

    def _create_app(self, runtime=None):
        return service_app.create_app(runtime=runtime or DummyRuntime())

    def _metrics_text(self, app):
        response = app.test_client().get("/metrics")
        self.assertEqual(response.status_code, 200)
        return response.data.decode()

    def _assert_metric_value(self, body: str, metric_name: str, value_pattern: str = r"1(?:\.0)?", **labels):
        label_text = ",".join(f'{key}="{labels[key]}"' for key in sorted(labels))
        pattern = rf"{re.escape(metric_name)}\{{{re.escape(label_text)}\}} {value_pattern}"
        self.assertRegex(body, pattern)

    def test_metrics_endpoint_returns_prometheus_text_and_is_not_self_counted(self):
        app = self._create_app()

        response = app.test_client().get("/metrics")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.content_type)
        body = response.data.decode()
        self.assertIn("# HELP llm_service_requests_total", body)
        self.assertIn("# HELP llm_service_request_duration_seconds", body)
        self.assertNotIn('route="/metrics"', body)

    def test_health_route_emits_request_counter_and_duration_metrics(self):
        app = self._create_app()

        response = app.test_client().get("/health")

        self.assertEqual(response.status_code, 200)
        body = self._metrics_text(app)
        self._assert_metric_value(
            body,
            "llm_service_requests_total",
            route="/health",
            model="none",
            provider="none",
            outcome="success",
        )
        self._assert_metric_value(
            body,
            "llm_service_request_duration_seconds_count",
            route="/health",
            model="none",
            provider="none",
            outcome="success",
        )

    def test_invalid_chat_request_emits_client_error_metrics_with_bounded_labels(self):
        app = self._create_app(service_app.LLMServiceRuntime(StubRouter({})))

        response = app.test_client().post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}]})

        self.assertEqual(response.status_code, 400)
        body = self._metrics_text(app)
        self._assert_metric_value(
            body,
            "llm_service_requests_total",
            route="/v1/chat/completions",
            model="none",
            provider="none",
            outcome="client_error",
        )
        self._assert_metric_value(
            body,
            "llm_service_request_duration_seconds_count",
            route="/v1/chat/completions",
            model="none",
            provider="none",
            outcome="client_error",
        )

    def test_successful_chat_records_requested_model_and_resolved_provider_metrics(self):
        provider = StubProvider(model_id="gemma_e2b_local", provider_name="openai_compatible")
        runtime = service_app.LLMServiceRuntime(StubRouter({"gemma_e2b_local": provider}))
        app = self._create_app(runtime)

        response = app.test_client().post(
            "/v1/chat/completions",
            json={
                "model": "gemma_e2b_local",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

        self.assertEqual(response.status_code, 200)
        body = self._metrics_text(app)
        self._assert_metric_value(
            body,
            "llm_service_requests_total",
            route="/v1/chat/completions",
            model="gemma_e2b_local",
            provider="openai_compatible",
            outcome="success",
        )
        self._assert_metric_value(
            body,
            "llm_service_request_duration_seconds_count",
            route="/v1/chat/completions",
            model="gemma_e2b_local",
            provider="openai_compatible",
            outcome="success",
        )
        self._assert_metric_value(
            body,
            "llm_service_provider_duration_seconds_count",
            route="/v1/chat/completions",
            model="gemma_e2b_local",
            provider="openai_compatible",
            outcome="success",
        )

    def test_chat_in_flight_gauge_rises_during_active_request_and_returns_to_zero(self):
        provider = StubProvider(model_id="gemma_e2b_local", provider_name="openai_compatible")
        provider.block_started = threading.Event()
        provider.block_release = threading.Event()
        runtime = service_app.LLMServiceRuntime(StubRouter({"gemma_e2b_local": provider}))
        app = self._create_app(runtime)
        payload = {
            "model": "gemma_e2b_local",
            "messages": [{"role": "user", "content": "hello"}],
        }
        result = {}

        def send_request():
            client = app.test_client()
            result["response"] = client.post("/v1/chat/completions", json=payload)

        thread = threading.Thread(target=send_request)
        thread.start()
        self.assertTrue(provider.block_started.wait(timeout=5))

        active_metrics = self._metrics_text(app)
        self.assertRegex(
            active_metrics,
            r'llm_service_in_flight_requests\{route="/v1/chat/completions"\} 1(?:\.0)?',
        )

        provider.block_release.set()
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result["response"].status_code, 200)

        settled_metrics = self._metrics_text(app)
        self.assertRegex(
            settled_metrics,
            r'llm_service_in_flight_requests\{route="/v1/chat/completions"\} 0(?:\.0)?',
        )

    def test_provider_timeout_records_timeout_outcome_in_route_and_provider_metrics(self):
        provider = StubProvider(model_id="gemma_e2b_local", provider_name="openai_compatible")
        provider.raise_exc = ProviderTimeoutError("timed out")
        runtime = service_app.LLMServiceRuntime(StubRouter({"gemma_e2b_local": provider}))
        app = self._create_app(runtime)

        response = app.test_client().post(
            "/v1/chat/completions",
            json={
                "model": "gemma_e2b_local",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

        self.assertEqual(response.status_code, 504)
        body = self._metrics_text(app)
        self._assert_metric_value(
            body,
            "llm_service_requests_total",
            route="/v1/chat/completions",
            model="gemma_e2b_local",
            provider="openai_compatible",
            outcome="timeout",
        )
        self._assert_metric_value(
            body,
            "llm_service_provider_duration_seconds_count",
            route="/v1/chat/completions",
            model="gemma_e2b_local",
            provider="openai_compatible",
            outcome="timeout",
        )

    def test_provider_unavailable_records_unavailable_outcome(self):
        provider = StubProvider(model_id="gemma_e2b_local", provider_name="openai_compatible")
        provider.raise_exc = ProviderUnavailableError("down")
        runtime = service_app.LLMServiceRuntime(StubRouter({"gemma_e2b_local": provider}))
        app = self._create_app(runtime)

        response = app.test_client().post(
            "/v1/chat/completions",
            json={
                "model": "gemma_e2b_local",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

        self.assertEqual(response.status_code, 503)
        body = self._metrics_text(app)
        self._assert_metric_value(
            body,
            "llm_service_requests_total",
            route="/v1/chat/completions",
            model="gemma_e2b_local",
            provider="openai_compatible",
            outcome="unavailable",
        )

    def test_ready_emits_aggregate_route_metrics_and_per_provider_readiness_metrics(self):
        first = StubProvider(model_id="gemma_e2b_local", provider_name="openai_compatible")
        second = StubProvider(model_id="gemma_e4b_local", provider_name="llama_cpp")
        runtime = service_app.LLMServiceRuntime(
            StubRouter(
                {
                    "gemma_e2b_local": first,
                    "gemma_e4b_local": second,
                }
            )
        )
        app = self._create_app(runtime)

        response = app.test_client().get("/ready")

        self.assertEqual(response.status_code, 200)
        body = self._metrics_text(app)
        self._assert_metric_value(
            body,
            "llm_service_requests_total",
            route="/ready",
            model="none",
            provider="none",
            outcome="success",
        )
        self._assert_metric_value(
            body,
            "llm_service_readiness_checks_total",
            model="gemma_e2b_local",
            provider="openai_compatible",
            outcome="success",
        )
        self._assert_metric_value(
            body,
            "llm_service_readiness_duration_seconds_count",
            model="gemma_e4b_local",
            provider="llama_cpp",
            outcome="success",
        )

    def test_managed_server_successful_startup_records_startup_metrics(self):
        app = self._create_app()
        process = Mock()
        process.poll.return_value = None

        with patch("llm.local_server_runtime._server_is_ready", return_value=False), patch(
            "llm.local_server_runtime._wait_for_server", return_value=None
        ), patch("llm.local_server_runtime.subprocess.Popen", return_value=process):
            local_server_runtime.ensure_managed_server(
                base_url="http://127.0.0.1:18012",
                binary_path="/opt/llama-cpp/llama-server",
                model_path="/models/model.gguf",
                model_name="gemma_e2b_local",
            )

        body = self._metrics_text(app)
        self._assert_metric_value(
            body,
            "llm_service_managed_server_startups_total",
            model="gemma_e2b_local",
            base_url="http://127.0.0.1:18012",
            outcome="success",
        )
        self._assert_metric_value(
            body,
            "llm_service_managed_server_startup_duration_seconds_count",
            model="gemma_e2b_local",
            base_url="http://127.0.0.1:18012",
            outcome="success",
        )

    def test_managed_server_failed_startup_after_spawn_records_unavailable_metrics(self):
        app = self._create_app()
        process = Mock()
        process.poll.return_value = None

        with patch("llm.local_server_runtime._server_is_ready", return_value=False), patch(
            "llm.local_server_runtime._wait_for_server", side_effect=RuntimeError("not ready")
        ), patch("llm.local_server_runtime.subprocess.Popen", return_value=process):
            with self.assertRaises(RuntimeError):
                local_server_runtime.ensure_managed_server(
                    base_url="http://127.0.0.1:18012",
                    binary_path="/opt/llama-cpp/llama-server",
                    model_path="/models/model.gguf",
                    model_name="gemma_e2b_local",
                )

        body = self._metrics_text(app)
        self._assert_metric_value(
            body,
            "llm_service_managed_server_startups_total",
            model="gemma_e2b_local",
            base_url="http://127.0.0.1:18012",
            outcome="unavailable",
        )
        self._assert_metric_value(
            body,
            "llm_service_managed_server_startup_duration_seconds_count",
            model="gemma_e2b_local",
            base_url="http://127.0.0.1:18012",
            outcome="unavailable",
        )

    def test_managed_server_replacement_launch_increments_restart_counter(self):
        app = self._create_app()
        exited_process = Mock()
        exited_process.poll.return_value = 1
        local_server_runtime._managed_servers["http://127.0.0.1:18012"] = exited_process
        new_process = Mock()
        new_process.poll.return_value = None

        with patch("llm.local_server_runtime._server_is_ready", return_value=False), patch(
            "llm.local_server_runtime._wait_for_server", return_value=None
        ), patch("llm.local_server_runtime.subprocess.Popen", return_value=new_process):
            local_server_runtime.ensure_managed_server(
                base_url="http://127.0.0.1:18012",
                binary_path="/opt/llama-cpp/llama-server",
                model_path="/models/model.gguf",
                model_name="gemma_e2b_local",
            )

        body = self._metrics_text(app)
        self._assert_metric_value(
            body,
            "llm_service_managed_server_restarts_total",
            model="gemma_e2b_local",
            base_url="http://127.0.0.1:18012",
        )


if __name__ == "__main__":
    unittest.main()
