from __future__ import annotations

import copy
import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "runtime"))

from tu_runtime.core.errors import TUnderstandError
from tu_runtime.core.io import atomic_write_yaml, sha256_file
from tests.runtime.common import RuntimeFixture


class NegativeRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = RuntimeFixture()
        self.fx.engine.init_work("NEGATIVE_WORK", "foundation", "APP-SNAP-TEST")
        self.fx.complete_current("NEGATIVE_WORK")

    def tearDown(self) -> None:
        self.fx.close()

    def packet(self):
        return self.fx.engine.route("NEGATIVE_WORK")["packet"]

    def valid_result(self, packet):
        output = packet["outputs"][0]
        path = self.fx.engine.workspace.work_dir("NEGATIVE_WORK") / output["path"]
        atomic_write_yaml(path, {"status": "test"})
        return self.fx.result_from_packet(packet, artifacts=[{"type": output["artifact_type"], "path": output["path"], "sha256": sha256_file(path)}])

    def write_result(self, name, result):
        path = self.fx.external / name
        atomic_write_yaml(path, result)
        return path

    def test_nested_delegation_packet_is_rejected(self) -> None:
        packet = self.packet()
        packet["delegation_depth"] = 2
        with self.assertRaises(TUnderstandError) as raised:
            self.fx.engine.contracts.validate("delegation-packet", packet)
        self.assertEqual("RT-SCHEMA-002", raised.exception.code)

    def test_result_from_wrong_worker_is_rejected(self) -> None:
        packet = self.packet()
        result = self.valid_result(packet)
        result["worker"] = "tu-reviewer"
        with self.assertRaises(TUnderstandError) as raised:
            self.fx.engine.accept_result("NEGATIVE_WORK", self.write_result("wrong-worker.yaml", result))
        self.assertEqual("RT-RESULT-004", raised.exception.code)

    def test_result_digest_mismatch_is_rejected_without_committing_result(self) -> None:
        packet = self.packet()
        result = self.valid_result(packet)
        result["artifacts"][0]["sha256"] = "0" * 64
        with self.assertRaises(TUnderstandError) as raised:
            self.fx.engine.accept_result("NEGATIVE_WORK", self.write_result("bad-digest.yaml", result))
        self.assertEqual("RT-RESULT-009", raised.exception.code)
        committed = self.fx.engine.workspace.work_dir("NEGATIVE_WORK") / "results" / f"{packet['invocation_id']}.yaml"
        self.assertFalse(committed.exists())

    def test_result_path_traversal_is_rejected_by_schema(self) -> None:
        packet = self.packet()
        result = self.valid_result(packet)
        result["artifacts"][0]["path"] = "../../source/repo.txt"
        with self.assertRaises(TUnderstandError) as raised:
            self.fx.engine.accept_result("NEGATIVE_WORK", self.write_result("traversal.yaml", result))
        self.assertEqual("RT-SCHEMA-002", raised.exception.code)

    def test_result_replay_is_rejected(self) -> None:
        packet = self.packet()
        path = self.write_result("valid.yaml", self.valid_result(packet))
        self.fx.engine.accept_result("NEGATIVE_WORK", path)
        with self.assertRaises(TUnderstandError) as raised:
            self.fx.engine.accept_result("NEGATIVE_WORK", path)
        self.assertEqual("RT-RESULT-001", raised.exception.code)

    def test_forward_loopback_is_rejected(self) -> None:
        packet = self.packet()
        result = self.fx.result_from_packet(packet, status="NEEDS_LOOPBACK", loopback_target="BEHAVIOR_ANALYSIS")
        with self.assertRaises(TUnderstandError) as raised:
            self.fx.engine.accept_result("NEGATIVE_WORK", self.write_result("forward-loop.yaml", result))
        self.assertEqual("RT-LOOPBACK-002", raised.exception.code)

    def test_root_cannot_skip_to_unregistered_state(self) -> None:
        other = RuntimeFixture()
        try:
            other.engine.init_work("ROOT_SKIP", "foundation", "APP-SNAP-TEST")
            artifact = other.write_root_artifact("application-alignment")
            with self.assertRaises(TUnderstandError) as raised:
                other.engine.complete_root_state("ROOT_SKIP", {"application-alignment": artifact}, "SYSTEM_MODELING")
            self.assertEqual("RT-TRANSITION-003", raised.exception.code)
            state = other.engine.status("ROOT_SKIP")
            self.assertEqual("APPLICATION_ALIGNMENT", state["current_state"])
            self.assertEqual(0, len(state["artifacts"]))
        finally:
            other.close()

    def test_documentation_publication_requires_human_approval(self) -> None:
        other = RuntimeFixture()
        try:
            other.engine.init_work("DOC_APPROVAL", "documentation", "APP-SNAP-TEST")
            workflow = other.engine.registry.workflow("documentation")
            while other.engine.status("DOC_APPROVAL")["current_state"] != "HUMAN_APPROVAL":
                other.complete_current("DOC_APPROVAL")
            with self.assertRaises(TUnderstandError) as raised:
                other.engine.complete_root_state("DOC_APPROVAL", {})
            self.assertEqual("RT-APPROVAL-001", raised.exception.code)
        finally:
            other.close()

    def test_stale_result_identity_is_rejected(self) -> None:
        packet = self.packet()
        result = self.valid_result(packet)
        result["state_version"] -= 1
        with self.assertRaises(TUnderstandError) as raised:
            self.fx.engine.accept_result("NEGATIVE_WORK", self.write_result("stale.yaml", result))
        self.assertEqual("RT-RESULT-004", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
