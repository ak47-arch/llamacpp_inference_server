import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT.parent))

from llm import local_server_runtime, service_app  # noqa: E402


class GenericInferenceServerTests(unittest.TestCase):
    def test_build_runtime_prefers_generic_env_var_names(self):
        config_path = "/tmp/generic-service-models.yaml"
        with patch.dict(os.environ, {"LLM_SERVER_CONFIG_FILE": config_path}, clear=False):
            with patch.object(service_app, "ProviderRouter") as router_cls:
                service_app.build_runtime(config_path=None)
        router_cls.assert_called_once_with(config_path)

    def test_legacy_application_files_are_removed(self):
        legacy_paths = [
            "pipeline.py",
            "validator.py",
            "job_queue.py",
            "worker.py",
            "eval.py",
            "benchmarks",
        ]
        for relative_path in legacy_paths:
            with self.subTest(path=relative_path):
                self.assertFalse((REPO_ROOT / relative_path).exists(), f"legacy path still present: {relative_path}")

    def test_docker_compose_uses_generic_environment_names(self):
        content = (REPO_ROOT / "docker-compose.yml").read_text()
        self.assertIn("LLM_SERVER_HOST", content)
        self.assertIn("LLM_SERVER_PORT", content)
        self.assertIn("LLM_SERVER_CONFIG_FILE", content)
        self.assertIn("LLAMA_CPP_DIR", content)
        self.assertNotIn("SURVIVAL_", content)

    def test_dockerfile_matches_standalone_repo_layout(self):
        content = (REPO_ROOT / "Dockerfile").read_text()
        self.assertIn("COPY requirements.txt ./", content)
        self.assertIn("COPY . /app/llm", content)
        self.assertNotIn("COPY llm/ ./llm/", content)
        self.assertNotIn("COPY config/ ./config/", content)

    def test_service_models_declare_only_q4_e4b_bundled_provider(self):
        config = yaml.safe_load((REPO_ROOT / "service_models.yaml").read_text())
        providers = config["providers"]
        self.assertEqual(len(providers), 1)

        provider = providers[0]
        self.assertEqual(provider["id"], "gemma_e4b_q4_local")
        self.assertEqual(provider["connection"]["base_url"], "http://127.0.0.1:18014")
        self.assertEqual(provider["connection"]["managed_server"]["port"], 18014)
        self.assertEqual(provider["connection"]["managed_server"]["model_path"], "/models/google_gemma-4-E4B-it-Q4_K_M.gguf")
        self.assertNotIn("ctx_size", provider["connection"]["managed_server"])

    def test_service_models_comments_out_disabled_provider_examples_and_reasoning_arguments(self):
        content = (REPO_ROOT / "service_models.yaml").read_text()
        self.assertIn("#  - id: gemma_e2b_local", content)
        self.assertIn("#  - id: gemma_e4b_local", content)

        block = content.split("- id: gemma_e4b_q4_local", 1)[1]
        self.assertIn("#          - --reasoning", block)
        self.assertIn('#          - "off"', block)
        self.assertIn("#          - --reasoning-budget", block)
        self.assertIn('#          - "0"', block)
        self.assertIn("#          - --reasoning-format", block)
        self.assertIn("#          - none", block)

    def test_commented_reasoning_lines_do_not_become_active_runtime_arguments(self):
        config = yaml.safe_load((REPO_ROOT / "service_models.yaml").read_text())
        provider = next(provider for provider in config["providers"] if provider["id"] == "gemma_e4b_q4_local")
        command = local_server_runtime._build_server_command(
            binary_path=provider["connection"]["managed_server"]["binary_path"],
            model_path=provider["connection"]["managed_server"]["model_path"],
            model_name=provider["model_name"],
            base_url=provider["connection"]["base_url"],
            server_config=provider["connection"]["managed_server"],
            default_params=provider.get("default_params", {}),
        )

        self.assertNotIn("--reasoning", command)
        self.assertNotIn("--reasoning-budget", command)
        self.assertNotIn("--reasoning-format", command)
        self.assertNotIn("off", command)
        self.assertNotIn("0", command)
        self.assertNotIn("none", command)
        self.assertNotIn("-c", command)


if __name__ == "__main__":
    unittest.main()
