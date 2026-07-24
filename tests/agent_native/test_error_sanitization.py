from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class AgentErrorSanitizationTests(unittest.TestCase):
    def test_host_instructions_require_named_prompt_option(self):
        root_agent = (ROOT / "agents/t-understand/AGENT.md").read_text(encoding="utf-8")
        opencode = (ROOT / "adapters/opencode/AGENTS.md").read_text(encoding="utf-8")
        for content in (root_agent, opencode):
            self.assertIn("--prompt", content)
            self.assertIn("never pass", content.lower())
        self.assertIn("agent-plan --prompt", opencode)
        self.assertIn("agent-document --prompt", opencode)

    def test_host_instructions_forbid_traceback_and_progress_leakage(self):
        root_agent = (ROOT / "agents/t-understand/AGENT.md").read_text(encoding="utf-8")
        opencode = (ROOT / "adapters/opencode/AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Python tracebacks", root_agent)
        self.assertIn("progress narration", opencode)
        self.assertIn("Run private engine operations silently", root_agent)


if __name__ == "__main__":
    unittest.main()
