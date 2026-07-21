from __future__ import annotations

import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "runtime"))

from tests.runtime.common import RuntimeFixture


class EndToEndWorkflowTests(unittest.TestCase):
    def test_every_registered_workflow_reaches_terminal_state(self) -> None:
        fx = RuntimeFixture()
        try:
            for index, workflow in enumerate(fx.engine.registry.workflows.values()):
                work_id = f"E2E_{index}_{workflow.id.upper()}"
                fx.engine.init_work(work_id, workflow.id, f"APP-SNAP-{workflow.id.upper()}", "economy")
                guard = 0
                while fx.engine.status(work_id)["status"] != "COMPLETED":
                    fx.complete_current(work_id)
                    guard += 1
                    self.assertLess(guard, 100, f"Workflow did not terminate: {workflow.id}")
                status = fx.engine.status(work_id)
                self.assertIn(status["current_state"], workflow.terminal_states)
                self.assertEqual(len(workflow.states) - 1, len(list((fx.engine.workspace.work_dir(work_id) / "transitions").glob("TRN-*.yaml"))))
                validation = fx.engine.validate_work(work_id)
                self.assertEqual("PASS", validation["status"], validation)
        finally:
            fx.close()

    def test_loopback_marks_dependent_artifacts_stale_and_restarts_target(self) -> None:
        fx = RuntimeFixture()
        try:
            fx.engine.init_work("LOOPBACK_FLOW", "foundation", "APP-SNAP-LOOP")
            while fx.engine.status("LOOPBACK_FLOW")["current_state"] != "MEMORY_CRITIQUE":
                fx.complete_current("LOOPBACK_FLOW")
            packet = fx.engine.route("LOOPBACK_FLOW")["packet"]
            result = fx.result_from_packet(packet, status="NEEDS_LOOPBACK", loopback_target="SYSTEM_MODELING", blocker="The model omitted a cross-repository dependency.")
            from tu_runtime.core.io import atomic_write_yaml
            path = fx.external / "loopback-result.yaml"
            atomic_write_yaml(path, result)
            state = fx.engine.accept_result("LOOPBACK_FLOW", path)
            self.assertEqual("SYSTEM_MODELING", state["current_state"])
            stale_states = {item["produced_state"] for item in state["artifacts"] if item["status"] == "STALE"}
            self.assertTrue({"SYSTEM_MODELING", "MEMORY_CONSOLIDATION"}.issubset(stale_states))
            self.assertEqual(1, len(list((fx.engine.workspace.work_dir("LOOPBACK_FLOW") / "loopbacks").glob("LBK-*.yaml"))))
        finally:
            fx.close()


if __name__ == "__main__":
    unittest.main()
