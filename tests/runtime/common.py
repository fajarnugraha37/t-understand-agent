from __future__ import annotations

import tempfile
import sys
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "runtime"))

from tu_runtime.core.engine import LifecycleEngine
from tu_runtime.core.io import atomic_write_yaml, load_yaml, sha256_file, utc_now


class RuntimeFixture:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runtime_root = self.root / "runtime"
        self.external = self.root / "external"
        self.external.mkdir(parents=True)
        self.engine = LifecycleEngine(PROJECT_ROOT, self.runtime_root)

    def close(self) -> None:
        self.temp.cleanup()

    def write_root_artifact(self, artifact_type: str, content: dict[str, Any] | None = None) -> Path:
        path = self.external / f"{artifact_type}.yaml"
        atomic_write_yaml(path, content or {"artifact_type": artifact_type, "status": "test"})
        return path

    def complete_current(self, work_id: str) -> dict[str, Any]:
        status = self.engine.status(work_id)
        if status["terminal"]:
            return status
        if status["owner"] == "t-understand":
            if status["current_state"] == "HUMAN_APPROVAL":
                self.engine.record_approval(work_id, "APPROVE", "Documentation publication is approved by the human.")
                return self.engine.complete_root_state(work_id, {})
            artifacts = {artifact_type: self.write_root_artifact(artifact_type) for artifact_type in status["expected_outputs"]}
            return self.engine.complete_root_state(work_id, artifacts)
        routed = self.engine.route(work_id)
        packet = routed["packet"]
        work_dir = self.engine.workspace.work_dir(work_id)
        result_artifacts = []
        for output in packet["outputs"]:
            path = work_dir / output["path"]
            atomic_write_yaml(path, {"artifact_type": output["artifact_type"], "invocation_id": packet["invocation_id"], "status": "test"})
            result_artifacts.append({"type": output["artifact_type"], "path": output["path"], "sha256": sha256_file(path)})
        result = self.result_from_packet(packet, artifacts=result_artifacts)
        result_path = self.external / f"{packet['invocation_id']}-result.yaml"
        atomic_write_yaml(result_path, result)
        return self.engine.accept_result(work_id, result_path)

    def result_from_packet(
        self,
        packet: dict[str, Any],
        *,
        status: str = "COMPLETED",
        artifacts: list[dict[str, str]] | None = None,
        boundary_status: str = "PASS",
        loopback_target: str | None = None,
        blocker: str | None = None,
    ) -> dict[str, Any]:
        return {
            "schema_id": "https://t-understand.dev/schemas/result-envelope.schema.json",
            "schema_version": "1.1.0",
            "invocation_id": packet["invocation_id"],
            "parent_agent": "t-understand",
            "worker": packet["target_agent"],
            "delegation_depth": 1,
            "workflow": packet["workflow"],
            "state": packet["state"],
            "state_version": packet["state_version"],
            "status": status,
            "artifacts": artifacts or [],
            "claims": [],
            "limitations": [],
            "boundary_status": boundary_status,
            "loopback_target": loopback_target,
            "blocker": blocker,
            "completed_at": utc_now(),
        }


def read_packet(path: str) -> dict[str, Any]:
    return load_yaml(Path(path))
