from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from ponytail_integration_lib import LADDER_IDS, audit, example_packet, load_yaml


class PonytailIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = json.loads(
            (ROOT / "schemas/delegation-packet.schema.json").read_text(encoding="utf-8")
        )
        self.validator = Draft202012Validator(
            self.schema, format_checker=FormatChecker()
        )

    def test_complete_integration_audit_passes(self) -> None:
        report = audit()
        self.assertEqual(report["status"], "PASS", report["errors"])

    def test_legacy_delegation_packet_remains_valid(self) -> None:
        errors = list(self.validator.iter_errors(example_packet()))
        self.assertEqual(errors, [])

    def test_ponytail_context_packet_is_valid(self) -> None:
        packet = example_packet()
        packet["ponytail_context"] = load_yaml("examples/ponytail-context.yaml")
        errors = list(self.validator.iter_errors(packet))
        self.assertEqual(errors, [])

    def test_incomplete_ponytail_context_fails(self) -> None:
        packet = example_packet()
        packet["ponytail_context"] = load_yaml("examples/ponytail-context.yaml")
        del packet["ponytail_context"]["selected_solution"]
        self.assertTrue(list(self.validator.iter_errors(packet)))

    def test_decision_ladder_order_is_exact(self) -> None:
        policy = load_yaml("orchestrator/ponytail-engineering-policy.yaml")
        self.assertEqual(
            [item["id"] for item in policy["decision_ladder"]], LADDER_IDS
        )

    def test_external_integration_is_optional_and_non_installing(self) -> None:
        policy = load_yaml("orchestrator/ponytail-engineering-policy.yaml")
        integration = policy["external_integration"]
        self.assertIs(integration["required"], False)
        self.assertIs(integration["automatically_install"], False)
        self.assertIs(integration["automatically_upgrade"], False)
        self.assertIs(integration["invent_commands_or_files"], False)

    def test_delegation_field_is_optional(self) -> None:
        self.assertNotIn("ponytail_context", self.schema["required"])

    def test_correctness_precedes_local_brevity(self) -> None:
        policy = load_yaml("orchestrator/ponytail-engineering-policy.yaml")
        precedence = policy["precedence"]
        self.assertLess(
            precedence.index("correctness and required behavior"),
            precedence.index("local code brevity"),
        )


if __name__ == "__main__":
    unittest.main()
