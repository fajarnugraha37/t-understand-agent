from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from graphify_integration_lib import STATUSES, audit, example_packet, load_yaml


class GraphifyIntegrationTests(unittest.TestCase):
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

    def test_repository_intelligence_packet_is_valid(self) -> None:
        packet = example_packet()
        packet["repository_intelligence"] = load_yaml(
            "examples/repository-intelligence.yaml"
        )
        errors = list(self.validator.iter_errors(packet))
        self.assertEqual(errors, [])

    def test_invalid_availability_status_fails(self) -> None:
        packet = example_packet()
        packet["repository_intelligence"] = load_yaml(
            "examples/repository-intelligence.yaml"
        )
        packet["repository_intelligence"]["graphify_status"] = "mandatory"
        self.assertTrue(list(self.validator.iter_errors(packet)))

    def test_policy_is_optional_fail_open_and_non_mutating(self) -> None:
        policy = load_yaml("orchestrator/repository-intelligence-policy.yaml")
        self.assertEqual(set(policy["availability"]["statuses"]), STATUSES)
        self.assertIn("Do not stop the task.", policy["failure_behavior"])
        for field in (
            "automatically_install",
            "automatically_upgrade",
            "automatically_initialize",
            "automatically_generate_graph",
            "automatically_rebuild_graph",
            "automatically_update_graph",
        ):
            self.assertIs(policy["query_policy"][field], False)

    def test_delegation_field_is_optional(self) -> None:
        self.assertNotIn("repository_intelligence", self.schema["required"])
        statuses = set(
            self.schema["properties"]["repository_intelligence"]["properties"][
                "graphify_status"
            ]["enum"]
        )
        self.assertEqual(statuses, STATUSES)


if __name__ == "__main__":
    unittest.main()
