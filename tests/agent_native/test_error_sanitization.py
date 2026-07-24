from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from tu_runtime.core import conversation
from tu_runtime.core.errors import TUnderstandError

ROOT = Path(__file__).resolve().parents[2]


class AgentErrorSanitizationTests(unittest.TestCase):
    def test_unexpected_documentation_error_becomes_structured_error(self):
        manager_type = conversation.AgentConversationManager
        original_type = manager_type.__mro__[1]
        manager = manager_type.__new__(manager_type)
        with patch.object(
            original_type,
            "generate_documentation",
            side_effect=KeyError("slice"),
        ):
            with self.assertRaises(TUnderstandError) as captured:
                manager.generate_documentation("generate comprehensive documentation")
        self.assertEqual(captured.exception.code, "AGENT-DOC-INTERNAL-001")
        self.assertIn("KeyError", captured.exception.message)
        self.assertIsNone(captured.exception.__cause__)

    def test_host_instructions_require_named_prompt_option(self):
        root_agent = (ROOT / "agents/t-understand/AGENT.md").read_text(encoding="utf-8")
        opencode = (ROOT / "adapters/opencode/AGENTS.md").read_text(encoding="utf-8")
        for content in (root_agent, opencode):
            self.assertIn("--prompt", content)
            self.assertIn("never pass", content.lower())
        self.assertIn("agent-plan --prompt", opencode)
        self.assertIn("agent-document --prompt", opencode)


if __name__ == "__main__":
    unittest.main()
