from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tu_runtime.core.installation import InstallationManager
from tu_runtime.core.managed_installation import merge_managed_block


ROOT = Path(__file__).resolve().parents[2]


class OpenCodeCustomAgentOnlyTests(unittest.TestCase):
    def test_package_excludes_global_agents_and_upgrade_removes_legacy_block(self):
        with tempfile.TemporaryDirectory(prefix="tu-opencode-custom-agent-") as raw:
            temp = Path(raw)
            context = temp / "context"
            target = temp / "opencode"
            context.mkdir(parents=True)
            target.mkdir(parents=True)

            manager = InstallationManager(ROOT, context)
            package_id, install_id = manager._managed_ids("opencode")
            package = manager.package(package_id, "opencode", force=True)

            packaged_paths = {entry["path"] for entry in package["files"]}
            self.assertNotIn("AGENTS.md", packaged_paths)
            self.assertIn("agents/t-understand.md", packaged_paths)

            payload_agent = (
                context
                / "platform-packages"
                / package_id
                / "payload"
                / "agents"
                / "t-understand.md"
            ).read_text(encoding="utf-8")
            self.assertIn("This agent is opt-in", payload_agent)
            self.assertIn("1800000", payload_agent)
            self.assertIn("120000", payload_agent)

            user_content = "# My OpenCode instructions\n\nKeep this user-owned content.\n"
            legacy_body = "Use t-understand for every human prompt.\n"
            legacy_agents, _ = merge_managed_block(
                user_content,
                "t-understand-opencode",
                legacy_body,
            )
            (target / "AGENTS.md").write_text(legacy_agents, encoding="utf-8")

            manager.install(install_id, package_id, target, force=True)

            remaining = (target / "AGENTS.md").read_text(encoding="utf-8")
            self.assertEqual(user_content, remaining)
            self.assertNotIn("T-UNDERSTAND MANAGED BLOCK", remaining)
            self.assertTrue((target / "agents" / "t-understand.md").is_file())
            self.assertTrue((target / "t-understand-engine" / "agent_runtime.py").is_file())

    def test_orphan_legacy_global_block_is_removed_without_deleting_user_content(self):
        with tempfile.TemporaryDirectory(prefix="tu-opencode-orphan-") as raw:
            temp = Path(raw)
            context = temp / "context"
            target = temp / "opencode"
            context.mkdir(parents=True)
            target.mkdir(parents=True)

            manager = InstallationManager(ROOT, context)
            package_id, install_id = manager._managed_ids("opencode")
            manager.package(package_id, "opencode", force=True)

            user_content = "# Personal rules\n"
            legacy_agents, _ = merge_managed_block(
                user_content,
                "t-understand-opencode",
                "Automatically invoke t-understand.\n",
            )
            (target / "AGENTS.md").write_text(legacy_agents, encoding="utf-8")

            manager.install(install_id, package_id, target, force=False)

            self.assertEqual(
                user_content,
                (target / "AGENTS.md").read_text(encoding="utf-8"),
            )
            self.assertTrue((target / "agents" / "t-understand.md").is_file())


if __name__ == "__main__":
    unittest.main()
