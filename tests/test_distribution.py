"""Check observable failures and standalone archive behavior using temp files."""

from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from package_skill import package_skill
from validate_skills import validate_skill


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="workflow-skills-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.skill = self.root / "sample-skill"
        self.skill.mkdir()
        (self.skill / "SKILL.md").write_text(
            "---\nname: sample-skill\ndescription: A small test skill.\n---\n\nSee [usage](README.md).\n",
            encoding="utf-8",
        )
        (self.skill / "README.md").write_text("# Usage\n\nRead the skill.\n", encoding="utf-8")
        (self.skill / "LICENSE").write_text("Fixture license\n", encoding="utf-8")
        (self.skill / "examples").mkdir()
        (self.skill / "examples" / "case.md").write_text("# Input and expected behavior\n", encoding="utf-8")

    def test_complete_skill_survives_zip_and_relocation(self):
        archive = package_skill(self.skill, self.root / "dist")
        relocated = self.root / "另一个目录 with spaces"
        with zipfile.ZipFile(archive) as bundle:
            self.assertIn("sample-skill/LICENSE", bundle.namelist())
            bundle.extractall(relocated)
        self.assertEqual(validate_skill(relocated / "sample-skill"), [])

    def test_actual_skill_archive_contains_panel_instructions_and_complete_bundle(self):
        skill = Path(__file__).resolve().parents[1] / "skills" / "plan-agent-tasks"
        archive = package_skill(skill, self.root / "dist")
        with zipfile.ZipFile(archive) as bundle:
            names = set(bundle.namelist())
            self.assertIn("plan-agent-tasks/references/progress-panel.md", names)
            self.assertIn("plan-agent-tasks/references/progress-state-contract.md", names)
            dashboard = skill / "assets" / "dashboard"
            expected = {"plan-agent-tasks/" + path.relative_to(skill).as_posix()
                        for path in dashboard.rglob("*") if path.is_file()
                        and "__pycache__" not in path.parts}
            self.assertTrue(expected.issubset(names), expected - names)
            self.assertFalse(any("__pycache__" in name or name.endswith(".pyc") for name in names))

    def test_missing_referenced_file_is_rejected(self):
        (self.skill / "README.md").write_text("[missing](absent.md)\n", encoding="utf-8")
        self.assertTrue(any("missing link target" in error for error in validate_skill(self.skill)))

    def test_existing_repo_file_cannot_be_runtime_dependency(self):
        (self.root / "shared.md").write_text("Shared\n", encoding="utf-8")
        (self.skill / "README.md").write_text("[shared](../shared.md)\n", encoding="utf-8")
        self.assertTrue(any("escapes standalone" in error for error in validate_skill(self.skill)))

    def test_name_must_match_install_directory(self):
        entry = self.skill / "SKILL.md"
        entry.write_text(entry.read_text(encoding="utf-8").replace("name: sample-skill", "name: different"), encoding="utf-8")
        self.assertTrue(any("name must match" in error for error in validate_skill(self.skill)))

    def test_code_example_links_are_not_dependencies(self):
        (self.skill / "README.md").write_text("```md\n[illustration](future.md)\n```\n", encoding="utf-8")
        self.assertEqual(validate_skill(self.skill), [])

    def test_machine_path_in_prompt_is_rejected(self):
        machine_path = "C:" + "/" + "Example/private/spec.md"
        (self.skill / "examples" / "case.md").write_text(f"```text\nRead {machine_path}\n```\n", encoding="utf-8")
        self.assertTrue(any("machine-specific" in error for error in validate_skill(self.skill)))

    def test_unfinished_output_and_unclosed_fence_are_rejected(self):
        (self.skill / "examples" / "case.md").write_text("{{task_id}}\n```text\nunfinished\n", encoding="utf-8")
        errors = validate_skill(self.skill)
        self.assertTrue(any("unresolved template" in error for error in errors))
        self.assertTrue(any("unclosed code fence" in error for error in errors))

    def test_template_variable_inside_mermaid_fence_is_rejected(self):
        assets = self.skill / "assets"
        assets.mkdir()
        (assets / "packet.md").write_text(
            "# Packet\n\n```mermaid\nflowchart TD\n{{session_graph}}\n```\n",
            encoding="utf-8",
        )
        self.assertTrue(
            any(
                "unresolved template variable inside Mermaid fence" in error
                for error in validate_skill(self.skill)
            )
        )

    def test_existing_zip_is_not_overwritten(self):
        archive = package_skill(self.skill, self.root / "dist")
        content = archive.read_bytes()
        with self.assertRaises(FileExistsError):
            package_skill(self.skill, self.root / "dist")
        self.assertEqual(archive.read_bytes(), content)

    def test_output_cannot_be_inside_packaged_skill(self):
        with self.assertRaises(ValueError):
            package_skill(self.skill, self.skill / "dist")

    def test_string_invocation_policy_is_rejected(self):
        (self.skill / "agents").mkdir()
        (self.skill / "agents" / "openai.yaml").write_text(
            'policy:\n  allow_implicit_invocation: "false"\n', encoding="utf-8"
        )
        self.assertTrue(any("must be a boolean" in error for error in validate_skill(self.skill)))


class PlanAgentResourcePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = Path(__file__).resolve().parents[1] / "skills" / "plan-agent-tasks"

    def test_skill_links_model_and_speed_policy(self):
        entry = (self.skill / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("references/model-and-speed-policies.md", entry)
        self.assertIn("resource_profile", entry)
        self.assertIn("speed_policy", entry)

    def test_policy_defines_independent_axes_and_profiles(self):
        policy = (self.skill / "references" / "model-and-speed-policies.md").read_text(encoding="utf-8")
        for value in (
            "execution_mode",
            "resource_profile",
            "speed_policy",
            "fixed-main",
            "economy",
            "balanced",
            "assured",
            "maximum",
            "standard",
            "critical-path",
            "fast-all",
        ):
            self.assertIn(value, policy)
        self.assertIn("不得通过省略模型参数", policy)
        self.assertIn("Fast 不可用", policy)

    def test_templates_require_explicit_session_bindings(self):
        packet = (self.skill / "assets" / "packet.md").read_text(encoding="utf-8")
        main = (self.skill / "assets" / "main.md").read_text(encoding="utf-8")
        prompts = (self.skill / "assets" / "prompts.md").read_text(encoding="utf-8")
        combined = "\n".join((packet, main, prompts))
        for value in (
            "provider",
            "model",
            "reasoning_effort",
            "service_tier",
            "catalog",
            "fallback",
            "escalation",
        ):
            self.assertIn(value, combined)

    def test_fast_fallback_cannot_change_model(self):
        policy = (self.skill / "references" / "model-and-speed-policies.md").read_text(encoding="utf-8")
        self.assertIn("回退到 `standard`", policy)
        self.assertIn("不得因此更换模型", policy)
        self.assertIn("提高推理强度或切换提供方", policy)

    def test_fixed_main_is_explicit_and_maximum_keeps_standard_valid(self):
        policy = (self.skill / "references" / "model-and-speed-policies.md").read_text(encoding="utf-8")
        self.assertIn("所有新会话显式填写与 Main 相同", policy)
        self.assertIn("这是有意绑定，不是省略参数后的继承", policy)
        self.assertIn("`maximum + standard` 完全有效", policy)
        self.assertIn("每个叶子任务安排两个 Reviewer", policy)
        self.assertIn("对抗性边界/安全审查", policy)

    def test_fast_all_requires_user_and_hidden_catalog_blocks_dispatch(self):
        policy = (self.skill / "references" / "model-and-speed-policies.md").read_text(encoding="utf-8")
        self.assertIn("`fast-all` 只能由用户明确选择", policy)
        self.assertIn("将任务包标为 `MODEL_BINDING_BLOCKED`", policy)
        self.assertIn("在此之前不得创建 Worker 或 Reviewer", policy)
        self.assertIn("无需调用第二个 Skill", policy)

    def test_service_tier_control_has_canonical_representation(self):
        policy = (self.skill / "references" / "model-and-speed-policies.md").read_text(encoding="utf-8")
        self.assertIn("service_tier_control: per-session | host-global | unavailable", policy)
        self.assertIn("service_tier_parameter: <exact key/value passed, or none>", policy)
        self.assertIn("`service_tier_control: unavailable`", policy)
        self.assertIn("`service_tier_parameter: none`", policy)


if __name__ == "__main__":
    unittest.main()
