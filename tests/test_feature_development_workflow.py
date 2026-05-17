import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT.parent))


class FeatureDevelopmentWorkflowDocsTests(unittest.TestCase):
    def test_workflow_docs_require_feature_development_skill_for_all_feature_work(self):
        content = (REPO_ROOT / "docs" / "FEATURE_DEVELOPMENT_WORKFLOW.md").read_text()
        self.assertIn("All feature work must use the `feature-development` skill", content)
        self.assertIn("hard requirement", content)

    def test_workflow_docs_define_multi_requirement_decomposition_and_dependency_planning(self):
        content = (REPO_ROOT / "docs" / "FEATURE_DEVELOPMENT_WORKFLOW.md").read_text()
        self.assertIn("multiple requirements", content)
        self.assertIn("different canonical specs", content)
        self.assertIn("parallel", content)
        self.assertIn("sequential", content)
        self.assertIn("separate approval", content)

    def test_feature_development_skill_enforces_multi_feature_planning(self):
        content = (REPO_ROOT / ".agents" / "skills" / "feature-development" / "SKILL.md").read_text()
        self.assertIn("All feature implementations must use this skill", content)
        self.assertIn("decompose", content)
        self.assertIn("dependency", content)
        self.assertIn("parallel", content)
        self.assertIn("sequential", content)

    def test_readme_points_feature_work_to_the_feature_development_skill(self):
        content = (REPO_ROOT / "README.md").read_text()
        self.assertIn("feature-development", content)
        self.assertIn("all feature work", content)


if __name__ == "__main__":
    unittest.main()
