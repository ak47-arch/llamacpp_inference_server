import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT.parent))

from llm import service_app  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
