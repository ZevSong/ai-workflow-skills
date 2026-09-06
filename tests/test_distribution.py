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


if __name__ == "__main__":
    unittest.main()
