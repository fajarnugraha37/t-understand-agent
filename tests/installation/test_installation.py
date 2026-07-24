from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from tu_runtime.core.managed_installation import InstallationManager, PLATFORMS
from tu_runtime.core.errors import TUnderstandError

ROOT = Path(__file__).resolve().parents[2]
BEGIN = "<!-- BEGIN T-UNDERSTAND MANAGED BLOCK: opencode -->"
END = "<!-- END T-UNDERSTAND MANAGED BLOCK: opencode -->"


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.context = self.base / "context"
        self.context.mkdir()
        self.m = InstallationManager(ROOT, self.context)

    def tearDown(self):
        self.tmp.cleanup()

    def test_all_platform_packages_validate(self):
        for i, platform in enumerate(PLATFORMS):
            package_id = f"INST-PKG-{i}"
            document = self.m.package(package_id, platform)
            self.assertEqual(document["platform"], platform)
            self.assertEqual(self.m.validate_package(package_id)["status"], "PASS")

    def test_install_doctor_idempotency_and_uninstall(self):
        self.m.package("INST-PKG-A", "opencode")
        target = self.base / "tool-config"
        result = self.m.install("INST-A", "INST-PKG-A", target)
        self.assertEqual(result["status"], "INSTALLED")
        self.assertEqual(self.m.doctor(target)["status"], "PASS")
        self.assertEqual(
            self.m.install("INST-A", "INST-PKG-A", target)["install_id"],
            "INST-A",
        )
        agents = (target / "AGENTS.md").read_text()
        self.assertEqual(agents.count(BEGIN), 1)
        self.assertEqual(agents.count(END), 1)
        self.assertEqual(self.m.uninstall(target)["status"], "UNINSTALLED")
        self.assertFalse((target / ".t-understand-install").exists())
        self.assertFalse((target / "AGENTS.md").exists())

    def test_unmanaged_conflict_requires_force_and_is_restored(self):
        self.m.package("INST-PKG-B", "cursor")
        target = self.base / "cursor"
        (target / "rules").mkdir(parents=True)
        existing = target / "rules/t-understand.mdc"
        existing.write_text("original")
        with self.assertRaises(Exception):
            self.m.install("INST-B", "INST-PKG-B", target)
        self.m.install("INST-B", "INST-PKG-B", target, True)
        self.m.uninstall(target)
        self.assertEqual(existing.read_text(), "original")

    def test_registered_source_target_is_rejected(self):
        source = self.base / "source"
        source.mkdir()
        (self.context / "workspace.local.yaml").write_text(
            yaml.safe_dump({"repositories": {"repo": {"path": str(source)}}})
        )
        self.m.package("INST-PKG-C", "codex")
        with self.assertRaises(Exception):
            self.m.install("INST-C", "INST-PKG-C", source / "config")

    def test_modified_managed_file_blocks_uninstall(self):
        self.m.package("INST-PKG-D", "claude-code")
        target = self.base / "claude"
        self.m.install("INST-D", "INST-PKG-D", target)
        manifest = yaml.safe_load(
            (target / ".t-understand-install/install-manifest.yaml").read_text()
        )
        entry = next(
            item for item in manifest["files"]
            if item.get("management_mode") == "owned_file"
        )
        path = target / entry["path"]
        path.write_text(path.read_text() + "changed")
        self.assertEqual(self.m.doctor(target)["status"], "FAIL")
        with self.assertRaises(Exception):
            self.m.uninstall(target)
        self.assertEqual(self.m.uninstall(target, True)["status"], "UNINSTALLED")

    def test_all_skill_names_are_tu_namespaced(self):
        for skill in ROOT.joinpath("skills").rglob("SKILL.md"):
            front = yaml.safe_load(skill.read_text().split("---", 2)[1])
            self.assertTrue(skill.parent.name.startswith("tu-"))
            self.assertEqual(front["name"], skill.parent.name)
        aggregate = ROOT / "adapters/codex/tu-understand/SKILL.md"
        front = yaml.safe_load(aggregate.read_text().split("---", 2)[1])
        self.assertEqual(front["name"], "tu-understand")
        self.assertFalse((ROOT / "adapters/codex/t-understand").exists())

    def test_platform_permission_profiles_have_no_ask_fallback(self):
        generated = {}
        for i, platform in enumerate(PLATFORMS):
            package_id = f"INST-PERM-{i}"
            self.m.package(package_id, platform)
            payload = self.context / "platform-packages" / package_id / "payload"
            generated[platform] = payload
            for file in payload.rglob("*"):
                if file.is_file() and "t-understand-engine" not in file.relative_to(payload).parts:
                    text = file.read_text(errors="ignore")
                    self.assertNotIn("bash: ask", text)
                    self.assertNotIn('"ask"', text)

        open_agent = (generated["opencode"] / "agents/t-understand.md").read_text()
        self.assertIn("external_directory: deny", open_agent)
        self.assertIn("git status*: allow", open_agent)
        self.assertIn("gh *: deny", open_agent)

        claude = json.loads((generated["claude-code"] / "settings.json").read_text())
        self.assertEqual(claude["permissions"]["defaultMode"], "acceptEdits")
        self.assertIn("Bash(*)", claude["permissions"]["allow"])
        self.assertIn("Bash(git commit:*)", claude["permissions"]["deny"])

        cursor = json.loads((generated["cursor"] / "cli-config.json").read_text())
        self.assertIn("Shell(*)", cursor["permissions"]["allow"])
        self.assertIn("Shell(git commit)", cursor["permissions"]["deny"])
        self.assertIn("Shell(gh)", cursor["permissions"]["deny"])

        codex = generated["codex"]
        self.assertTrue((codex / "skills/tu-understand/SKILL.md").exists())
        self.assertFalse((codex / "skills/t-understand/SKILL.md").exists())
        profile = (codex / "tu-understand.config.toml").read_text()
        self.assertIn('approval_policy = "never"', profile)
        self.assertIn('sandbox_mode = "workspace-write"', profile)
        rules = (codex / "rules/tu-understand.rules").read_text()
        self.assertIn('pattern = ["gh"]', rules)
        self.assertIn('pattern = ["git", "commit"]', rules)

    def test_json_permission_config_merges_without_force_and_restores(self):
        self.m.package("INST-PKG-MERGE", "claude-code")
        target = self.base / "claude-merge"
        target.mkdir()
        original = {"theme": "dark", "permissions": {"allow": ["CustomTool"]}}
        (target / "settings.json").write_text(json.dumps(original, indent=2) + "\n")
        self.m.install("INST-MERGE", "INST-PKG-MERGE", target)
        merged = json.loads((target / "settings.json").read_text())
        self.assertEqual(merged["theme"], "dark")
        self.assertIn("CustomTool", merged["permissions"]["allow"])
        self.assertIn("Bash(*)", merged["permissions"]["allow"])
        self.assertEqual(self.m.doctor(target)["status"], "PASS")
        self.m.uninstall(target)
        self.assertEqual(json.loads((target / "settings.json").read_text()), original)

    def test_force_replaces_existing_owned_install_content(self):
        self.m.package("INST-PKG-OLD", "opencode")
        target = self.base / "replace"
        self.m.install("INST-OLD", "INST-PKG-OLD", target)
        managed = target / "agents/t-understand.md"
        managed.write_text(managed.read_text() + " locally modified")
        self.m.package("INST-PKG-NEW", "opencode")
        with self.assertRaises(Exception):
            self.m.install("INST-NEW", "INST-PKG-NEW", target)
        replaced = self.m.install("INST-NEW", "INST-PKG-NEW", target, True)
        self.assertEqual(replaced["install_id"], "INST-NEW")
        self.assertEqual(self.m.doctor(target)["status"], "PASS")
        self.assertNotIn("locally modified", managed.read_text())

    def test_agent_native_platform_install_generates_ids_and_packages_engine(self):
        target = self.base / "opencode-global"
        result = self.m.install_platform("opencode", target)
        self.assertEqual(result["platform"], "opencode")
        self.assertTrue(result["install_id"].startswith("INST-OPENCODE"))
        self.assertTrue((target / "t-understand-engine/agent_runtime.py").is_file())
        self.assertTrue((target / "t-understand-engine/runtime/tu_runtime/cli.py").is_file())
        self.assertTrue(
            (target / "t-understand-engine/runtime/tu_runtime/core/conversation.py").is_file()
        )
        self.assertTrue(
            (target / "t-understand-engine/orchestrator/capabilities.yaml").is_file()
        )
        self.assertEqual(self.m.doctor_platform("opencode", target)["status"], "PASS")

        owned = target / "agents/t-understand.md"
        owned.write_text(owned.read_text() + " tampered")
        replaced = self.m.install_platform("opencode", target, True)
        self.assertEqual(replaced["status"], "INSTALLED")
        self.assertEqual(self.m.doctor_platform("opencode", target)["status"], "PASS")
        self.assertNotIn("tampered", owned.read_text())

    def test_install_wrappers_are_simple_and_force_capable(self):
        ps = (ROOT / "bin/install.ps1").read_text()
        sh = (ROOT / "bin/install.sh").read_text()
        self.assertIn("[string]$Target", ps)
        self.assertIn("[switch]$Force", ps)
        self.assertNotIn("ContextRoot", ps)
        self.assertIn("platform-install','--platform',$Target", ps)
        self.assertIn("[--force]", sh)
        self.assertNotIn("CONTEXT_ROOT", sh)
        self.assertIn("platform-install --platform", sh)

    def test_root_agent_hides_internal_context_and_cli_from_humans(self):
        root = (ROOT / "agents/t-understand/AGENT.md").read_text()
        self.assertIn("Human interaction contract", root)
        self.assertIn("Never require the human", root)
        self.assertIn("<workspace>/.t-understand/", root)
        self.assertIn("Generate stable operation IDs automatically", root)
        self.assertIn("Conversation routing contract", root)
        self.assertIn("agent-document", root)
        self.assertIn("chat-only answer", root)

    def test_existing_agents_file_is_preserved_and_managed_once(self):
        target = self.base / "opencode-existing"
        target.mkdir()
        agents = target / "AGENTS.md"
        agents.write_text("# User instructions\n\n- Keep this rule.\n")
        self.m.install_platform("opencode", target)
        content = agents.read_text()
        self.assertIn("# User instructions", content)
        self.assertIn("- Keep this rule.", content)
        self.assertEqual(content.count(BEGIN), 1)
        self.assertEqual(content.count(END), 1)
        self.assertEqual(self.m.doctor(target)["status"], "PASS")

    def test_reinstall_and_force_reinstall_never_duplicate_managed_block(self):
        target = self.base / "opencode-reinstall"
        target.mkdir()
        agents = target / "AGENTS.md"
        agents.write_text("# User instructions\n")
        self.m.install_platform("opencode", target)
        self.m.install_platform("opencode", target)
        agents.write_text(agents.read_text() + "\n# Later user instruction\n")
        self.assertEqual(self.m.doctor(target)["status"], "PASS")
        self.m.install_platform("opencode", target, True)
        content = agents.read_text()
        self.assertIn("# User instructions", content)
        self.assertIn("# Later user instruction", content)
        self.assertEqual(content.count(BEGIN), 1)
        self.assertEqual(content.count(END), 1)
        self.assertEqual(self.m.doctor(target)["status"], "PASS")

    def test_uninstall_removes_only_managed_block(self):
        target = self.base / "opencode-uninstall"
        target.mkdir()
        agents = target / "AGENTS.md"
        agents.write_text("# Before install\n")
        self.m.install_platform("opencode", target)
        agents.write_text(agents.read_text() + "\n# Added after install\n")
        self.m.uninstall_platform("opencode", target)
        content = agents.read_text()
        self.assertIn("# Before install", content)
        self.assertIn("# Added after install", content)
        self.assertNotIn(BEGIN, content)
        self.assertNotIn(END, content)

    def test_doctor_rejects_modified_managed_block_but_ignores_outside_edits(self):
        target = self.base / "opencode-doctor"
        target.mkdir()
        agents = target / "AGENTS.md"
        agents.write_text("# User instructions\n")
        self.m.install_platform("opencode", target)
        agents.write_text(agents.read_text() + "\n# Outside edit\n")
        self.assertEqual(self.m.doctor(target)["status"], "PASS")
        agents.write_text(
            agents.read_text().replace(
                "# t-understand OpenCode Instructions",
                "# Modified t-understand Instructions",
                1,
            )
        )
        self.assertEqual(self.m.doctor(target)["status"], "FAIL")

    def test_malformed_managed_markers_fail_without_overwriting_user_file(self):
        target = self.base / "opencode-malformed"
        target.mkdir()
        agents = target / "AGENTS.md"
        original = "# User instructions\n\n" + BEGIN + "\nunfinished\n"
        agents.write_text(original)
        with self.assertRaises(TUnderstandError):
            self.m.install_platform("opencode", target)
        self.assertEqual(agents.read_text(), original)
        self.assertFalse((target / ".t-understand-install").exists())

    def test_existing_crlf_agents_file_keeps_crlf(self):
        target = self.base / "opencode-crlf"
        target.mkdir()
        agents = target / "AGENTS.md"
        agents.write_bytes(b"# User instructions\r\n\r\n- Keep this rule.\r\n")
        self.m.install_platform("opencode", target)
        content = agents.read_bytes()
        self.assertIn(BEGIN.encode(), content)
        self.assertNotIn(b"\n", content.replace(b"\r\n", b""))
        self.assertEqual(content.count(BEGIN.encode()), 1)

    def test_installer_created_agents_file_is_removed_on_uninstall(self):
        target = self.base / "opencode-created"
        self.m.install_platform("opencode", target)
        self.assertTrue((target / "AGENTS.md").exists())
        self.m.uninstall_platform("opencode", target)
        self.assertFalse((target / "AGENTS.md").exists())


if __name__ == "__main__":
    unittest.main()
