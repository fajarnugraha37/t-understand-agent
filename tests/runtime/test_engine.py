from __future__ import annotations

import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "runtime"))

from tu_runtime.core.errors import TUnderstandError
from tests.runtime.common import RuntimeFixture


class EngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = RuntimeFixture()

    def tearDown(self) -> None:
        self.fx.close()

    def test_all_workflows_initialize_at_registered_initial_state(self) -> None:
        for index, workflow in enumerate(self.fx.engine.registry.workflows.values()):
            work_id = f"INIT_{index}_{workflow.id.upper()}"
            state = self.fx.engine.init_work(work_id, workflow.id, "APP-SNAP-TEST")
            self.assertEqual(workflow.initial_state, state["current_state"])
            self.assertEqual("ACTIVE", state["status"])

    def test_root_state_routes_to_human_action(self) -> None:
        self.fx.engine.init_work("ROOT_ACTION", "foundation", "APP-SNAP-TEST")
        routed = self.fx.engine.route("ROOT_ACTION")
        self.assertEqual("HUMAN_ORCHESTRATOR_ACTION", routed["action"])
        self.assertEqual("APPLICATION_ALIGNMENT", routed["state"])

    def test_worker_route_is_idempotent_while_waiting(self) -> None:
        self.fx.engine.init_work("ROUTE_IDEMPOTENT", "foundation", "APP-SNAP-TEST")
        self.fx.complete_current("ROUTE_IDEMPOTENT")
        first = self.fx.engine.route("ROUTE_IDEMPOTENT")
        second = self.fx.engine.route("ROUTE_IDEMPOTENT")
        self.assertEqual("DELEGATE", first["action"])
        self.assertEqual("EXISTING_DELEGATION", second["action"])
        self.assertEqual(first["packet"]["invocation_id"], second["invocation_id"])

    def test_delegation_is_depth_one_and_source_read_only(self) -> None:
        self.fx.engine.init_work("DEPTH_ONE", "foundation", "APP-SNAP-TEST")
        self.fx.complete_current("DEPTH_ONE")
        packet = self.fx.engine.route("DEPTH_ONE")["packet"]
        self.assertEqual(1, packet["delegation_depth"])
        self.assertEqual("t-understand", packet["parent_agent"])
        self.assertEqual("deny", packet["permissions"]["delegate"])
        self.assertEqual("deny", packet["permissions"]["source_repository_write"])
        self.assertEqual("deny", packet["permissions"]["git_mutation"])

    def test_blocked_result_can_be_resumed_without_transition(self) -> None:
        self.fx.engine.init_work("BLOCK_RESUME", "foundation", "APP-SNAP-TEST")
        self.fx.complete_current("BLOCK_RESUME")
        packet = self.fx.engine.route("BLOCK_RESUME")["packet"]
        result = self.fx.result_from_packet(packet, status="BLOCKED", boundary_status="PASS", blocker="Required evidence is unavailable.")
        path = self.fx.external / "blocked.yaml"
        from tu_runtime.core.io import atomic_write_yaml
        atomic_write_yaml(path, result)
        blocked = self.fx.engine.accept_result("BLOCK_RESUME", path)
        self.assertEqual("BLOCKED", blocked["status"])
        self.assertEqual("WORKSPACE_RESOLUTION", blocked["current_state"])
        resumed = self.fx.engine.resume("BLOCK_RESUME", "Evidence was supplied by the human.")
        self.assertEqual("ACTIVE", resumed["status"])
        self.assertEqual("WORKSPACE_RESOLUTION", resumed["current_state"])

    def test_runtime_work_validation_detects_artifact_tampering(self) -> None:
        self.fx.engine.init_work("TAMPER_CHECK", "foundation", "APP-SNAP-TEST")
        self.fx.complete_current("TAMPER_CHECK")
        state = self.fx.engine.workspace.load_state("TAMPER_CHECK")
        artifact_path = self.fx.engine.workspace.work_dir("TAMPER_CHECK") / state["artifacts"][0]["path"]
        artifact_path.write_text("tampered\n", encoding="utf-8")
        report = self.fx.engine.validate_work("TAMPER_CHECK")
        self.assertEqual("FAIL", report["status"])
        self.assertTrue(any("digest mismatch" in item for item in report["errors"]))

    def test_invalid_profile_is_rejected(self) -> None:
        with self.assertRaises(TUnderstandError) as raised:
            self.fx.engine.init_work("BAD_PROFILE", "foundation", "APP-SNAP-TEST", "unknown")
        self.assertEqual("RT-PROFILE-001", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
