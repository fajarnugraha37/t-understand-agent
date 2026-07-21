from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tu_runtime.core.conversation import AgentConversationManager

ROOT = Path(__file__).resolve().parents[2]
LITERAL_PROMPT = "Understand this repository deeply, precisely and write comprehensive, detailed, deep, sensible documentation"


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class AgentConversationTests(unittest.TestCase):
    def test_greeting_lists_capabilities_without_bootstrap(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            manager = AgentConversationManager(ROOT, workspace, workspace / ".t-understand")
            result = manager.plan("hi")
            self.assertEqual(result["intent"], "GREETING")
            self.assertIn("Capabilities:", result["direct_response"])
            self.assertFalse((workspace / ".t-understand").exists())

    def test_substantive_task_overrides_greeting(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"; repo.mkdir()
            git(repo, "init", "-q"); git(repo, "config", "user.email", "test@example.com"); git(repo, "config", "user.name", "Test")
            (repo / "README.md").write_text("# Repo\n")
            git(repo, "add", "."); git(repo, "commit", "-qm", "init")
            manager = AgentConversationManager(ROOT, repo, repo / ".t-understand")
            result = manager.plan("hi, review my current changes")
            self.assertEqual(result["intent"], "CODE_REVIEW")

    def test_literal_prompt_routes_to_artifact_documentation(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"; repo.mkdir()
            git(repo, "init", "-q"); git(repo, "config", "user.email", "test@example.com"); git(repo, "config", "user.name", "Test")
            (repo / "src").mkdir(); (repo / "src/index.ts").write_text("export const answer = 42;\n")
            (repo / "package.json").write_text('{"name":"fixture","type":"module"}\n')
            git(repo, "add", "."); git(repo, "commit", "-qm", "init")
            manager = AgentConversationManager(ROOT, repo, repo / ".t-understand")
            result = manager.plan(LITERAL_PROMPT)
            self.assertEqual(result["intent"], "DOCUMENTATION_GENERATION")
            self.assertTrue(result["artifact_required"])
            self.assertEqual(result["response_mode"], "SUMMARY_ONLY")
            self.assertEqual(result["completion_contract"]["chat_only_completion"], "forbidden")

    def test_documentation_pipeline_creates_files_and_concise_response(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"; repo.mkdir()
            git(repo, "init", "-q"); git(repo, "config", "user.email", "test@example.com"); git(repo, "config", "user.name", "Test")
            (repo / "src").mkdir(); (repo / "src/index.ts").write_text("export function greet(name: string) { return `Hello ${name}`; }\n")
            (repo / "README.md").write_text("# Fixture\n")
            (repo / "package.json").write_text('{"name":"fixture","type":"module"}\n')
            git(repo, "add", "."); git(repo, "commit", "-qm", "init")
            manager = AgentConversationManager(ROOT, repo, repo / ".t-understand")
            completion = manager.generate_documentation(LITERAL_PROMPT)
            self.assertEqual(completion["status"], "PASS")
            self.assertGreaterEqual(completion["documents"], 5)
            latest = repo / ".t-understand/output/documentation/latest"
            self.assertTrue((latest / "index.md").is_file())
            self.assertTrue((latest / "_meta/manifest.yaml").is_file())
            self.assertTrue((latest / "_meta/traceability.jsonl").is_file())
            self.assertLess(len(completion["chat_response"]), 4000)
            self.assertNotIn("# Project Overview", completion["chat_response"])
            self.assertEqual(manager.validate_response(LITERAL_PROMPT, completion["chat_response"])["status"], "PASS")

    def test_chat_dump_and_private_reasoning_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            manager = AgentConversationManager(ROOT, workspace, workspace / ".t-understand")
            response = "# Todos\nThought: done\n" + "documentation\n" * 100
            report = manager.validate_response(LITERAL_PROMPT, response)
            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(report["errors"])


if __name__ == "__main__":
    unittest.main()
