from __future__ import annotations

import re
import shutil
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .contracts import ContractValidator
from .errors import TUnderstandError
from .io import append_jsonl, atomic_write_yaml, load_yaml, sha256_file, utc_now
from .registry import Registry

WORK_ID_RE = re.compile(r"^[A-Z][A-Z0-9_-]{2,63}$")


class RuntimeWorkspace:
    def __init__(self, project_root: Path, runtime_root: Path, registry: Registry, contracts: ContractValidator):
        self.project_root = project_root
        self.runtime_root = runtime_root
        self.registry = registry
        self.contracts = contracts

    def work_dir(self, work_id: str) -> Path:
        if not WORK_ID_RE.fullmatch(work_id):
            raise TUnderstandError("RT-WORK-001", "work_id must match ^[A-Z][A-Z0-9_-]{2,63}$")
        return self.runtime_root / work_id

    def state_path(self, work_id: str) -> Path:
        return self.work_dir(work_id) / "state.yaml"

    def create(self, work_id: str, workflow_id: str, snapshot: str, profile: str, application_id: str | None = None) -> dict[str, Any]:
        work_dir = self.work_dir(work_id)
        if work_dir.exists():
            raise TUnderstandError("RT-WORK-002", f"Work item already exists: {work_id}")
        workflow = self.registry.workflow(workflow_id)
        self.registry.profile(profile)
        for name in ("artifacts", "delegations", "results", "approvals", "transitions", "loopbacks", "events", "locks"):
            (work_dir / name).mkdir(parents=True, exist_ok=True)
        now = utc_now()
        state = {
            "schema_id": "https://t-understand.dev/schemas/work-state.schema.json",
            "schema_version": "1.1.0",
            "work_id": work_id,
            "workflow": workflow_id,
            "application_id": application_id,
            "current_state": workflow.initial_state,
            "status": "ACTIVE",
            "profile": profile,
            "application_snapshot": snapshot,
            "state_version": 1,
            "active_invocation": None,
            "blocker": None,
            "artifacts": [],
            "created_at": now,
            "updated_at": now,
        }
        self.contracts.validate("work-state", state)
        atomic_write_yaml(self.state_path(work_id), state)
        self.event(work_id, "WORK_CREATED", {"workflow": workflow_id, "state": workflow.initial_state, "profile": profile})
        return state

    def load_state(self, work_id: str) -> dict[str, Any]:
        state = load_yaml(self.state_path(work_id))
        self.contracts.validate("work-state", state)
        return state

    def save_state(self, state: dict[str, Any]) -> None:
        state["updated_at"] = utc_now()
        self.contracts.validate("work-state", state)
        atomic_write_yaml(self.state_path(state["work_id"]), state)

    def event(self, work_id: str, event_type: str, payload: dict[str, Any]) -> None:
        append_jsonl(
            self.work_dir(work_id) / "events" / "events.jsonl",
            {"event_id": f"EVT-{uuid.uuid4().hex.upper()}", "occurred_at": utc_now(), "type": event_type, "payload": payload},
        )

    def import_artifact(self, work_id: str, artifact_type: str, source: Path, produced_state: str, producer: str) -> dict[str, Any]:
        if artifact_type not in self.registry.artifacts:
            raise TUnderstandError("RT-ARTIFACT-001", f"Unknown artifact type: {artifact_type}")
        if not source.is_file():
            raise TUnderstandError("RT-ARTIFACT-002", f"Artifact source is not a file: {source}")
        destination_dir = self.work_dir(work_id) / "artifacts" / artifact_type
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / f"ART-{uuid.uuid4().hex.upper()}{source.suffix or '.yaml'}"
        shutil.copyfile(source, destination)
        relative = destination.relative_to(self.work_dir(work_id)).as_posix()
        return {
            "type": artifact_type,
            "path": relative,
            "sha256": sha256_file(destination),
            "produced_state": produced_state,
            "producer": producer,
            "status": "CURRENT",
        }

    @contextmanager
    def lock(self, work_id: str) -> Iterator[None]:
        lock_path = self.work_dir(work_id) / "locks" / "mutation.lock"
        try:
            lock_path.mkdir()
        except FileExistsError as exc:
            raise TUnderstandError("RT-LOCK-001", f"Work item is already being mutated: {work_id}") from exc
        try:
            yield
        finally:
            lock_path.rmdir()
