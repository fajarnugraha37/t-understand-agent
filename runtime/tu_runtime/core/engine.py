from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from .contracts import ContractValidator
from .errors import TUnderstandError
from .io import atomic_write_yaml, load_yaml, resolve_within, sha256_file, utc_now
from .registry import Registry, StateSpec, WorkflowSpec
from .workspace import RuntimeWorkspace


class LifecycleEngine:
    def __init__(self, project_root: Path, runtime_root: Path):
        self.project_root = project_root.resolve()
        self.registry = Registry(self.project_root)
        self.contracts = ContractValidator(self.project_root)
        self.workspace = RuntimeWorkspace(self.project_root, runtime_root.resolve(), self.registry, self.contracts)

    def init_work(self, work_id: str, workflow: str, snapshot: str, profile: str = "economy", application_id: str | None = None) -> dict[str, Any]:
        return self.workspace.create(work_id, workflow, snapshot, profile, application_id)

    def status(self, work_id: str) -> dict[str, Any]:
        state = self.workspace.load_state(work_id)
        spec = self.registry.workflow(state["workflow"]).state(state["current_state"])
        return {**state, "owner": spec.owner, "skill": spec.skill, "expected_outputs": list(spec.outputs), "terminal": spec.terminal}

    def route(self, work_id: str, objective: str | None = None) -> dict[str, Any]:
        with self.workspace.lock(work_id):
            state = self.workspace.load_state(work_id)
            workflow = self.registry.workflow(state["workflow"])
            current = workflow.state(state["current_state"])
            if state["status"] == "WAITING_RESULT" and state["active_invocation"]:
                packet_path = self.workspace.work_dir(work_id) / "delegations" / f"{state['active_invocation']}.yaml"
                if not packet_path.is_file():
                    raise TUnderstandError("RT-DELEGATION-001", f"Active delegation file is missing: {state['active_invocation']}")
                packet = load_yaml(packet_path)
                self.contracts.validate("delegation-packet", packet)
                if packet["workflow"] != state["workflow"] or packet["state"] != state["current_state"]:
                    raise TUnderstandError("RT-DELEGATION-002", "Active delegation is not bound to the current workflow state")
                return {"action": "EXISTING_DELEGATION", "path": str(packet_path), "invocation_id": state["active_invocation"]}
            self._require_active(state)
            if current.terminal:
                raise TUnderstandError("RT-ROUTE-001", "Terminal state cannot be routed")
            if current.owner == "t-understand":
                return {
                    "action": "HUMAN_ORCHESTRATOR_ACTION",
                    "work_id": work_id,
                    "workflow": workflow.id,
                    "state": current.id,
                    "skill": current.skill,
                    "expected_outputs": list(current.outputs),
                }
            packet = self._build_packet(state, workflow, current, objective)
            self.contracts.validate("delegation-packet", packet)
            packet_path = self.workspace.work_dir(work_id) / "delegations" / f"{packet['invocation_id']}.yaml"
            atomic_write_yaml(packet_path, packet)
            state["status"] = "WAITING_RESULT"
            state["active_invocation"] = packet["invocation_id"]
            state["state_version"] += 1
            self.workspace.save_state(state)
            self.workspace.event(work_id, "DELEGATION_CREATED", {"invocation_id": packet["invocation_id"], "state": current.id, "worker": current.owner})
            return {"action": "DELEGATE", "path": str(packet_path), "packet": packet}

    def complete_root_state(self, work_id: str, artifact_args: dict[str, Path], next_state: str | None = None) -> dict[str, Any]:
        with self.workspace.lock(work_id):
            state = self.workspace.load_state(work_id)
            self._require_active(state)
            workflow = self.registry.workflow(state["workflow"])
            current = workflow.state(state["current_state"])
            if current.owner != "t-understand" or current.terminal:
                raise TUnderstandError("RT-ROOT-001", f"State is not a completable orchestrator state: {current.id}")
            if current.id == "HUMAN_APPROVAL":
                approval = self._latest_approval(work_id, current.id)
                if approval is None or approval["decision"] != "APPROVE":
                    raise TUnderstandError("RT-APPROVAL-001", "HUMAN_APPROVAL requires a recorded APPROVE decision")
                if "human-publication-approval" not in artifact_args:
                    artifact_args = {**artifact_args, "human-publication-approval": self.workspace.work_dir(work_id) / approval["publication_artifact"]}
            self._validate_expected_artifact_args(current, artifact_args)
            self._select_next(current, next_state)
            imported = [
                self.workspace.import_artifact(work_id, artifact_type, artifact_args[artifact_type], current.id, "t-understand")
                for artifact_type in current.outputs
            ]
            state["artifacts"].extend(imported)
            return self._transition(state, workflow, current, next_state, "ROOT_COMPLETION", [item["path"] for item in imported])

    def accept_result(self, work_id: str, result_path: Path, next_state: str | None = None) -> dict[str, Any]:
        result = load_yaml(result_path)
        self.contracts.validate("result-envelope", result)
        with self.workspace.lock(work_id):
            state = self.workspace.load_state(work_id)
            if state["status"] != "WAITING_RESULT" or not state["active_invocation"]:
                raise TUnderstandError("RT-RESULT-001", "Work item is not waiting for a result")
            invocation_id = state["active_invocation"]
            packet_path = self.workspace.work_dir(work_id) / "delegations" / f"{invocation_id}.yaml"
            packet = load_yaml(packet_path)
            self.contracts.validate("delegation-packet", packet)
            self._validate_result_identity(state, packet, result)
            destination = self.workspace.work_dir(work_id) / "results" / f"{invocation_id}.yaml"
            if destination.exists():
                raise TUnderstandError("RT-RESULT-002", f"Result replay detected: {invocation_id}")
            workflow = self.registry.workflow(state["workflow"])
            current = workflow.state(state["current_state"])
            if result["status"] == "NEEDS_LOOPBACK":
                self._validate_loopback_target(workflow, current, result["loopback_target"])
                atomic_write_yaml(destination, result)
                return self._apply_loopback(state, workflow, current, result["loopback_target"], result.get("blocker") or "; ".join(result["limitations"]) or "Worker requested loopback", invocation_id)
            if result["status"] in {"BLOCKED", "FAILED"}:
                atomic_write_yaml(destination, result)
                state["status"] = "BLOCKED"
                state["blocker"] = result.get("blocker") or f"Worker returned {result['status']}"
                state["active_invocation"] = None
                state["state_version"] += 1
                self.workspace.save_state(state)
                self.workspace.event(work_id, "WORK_BLOCKED", {"state": current.id, "invocation_id": invocation_id, "reason": state["blocker"]})
                return state
            if result["boundary_status"] != "PASS":
                raise TUnderstandError("RT-RESULT-003", "COMPLETED result requires boundary_status PASS")
            self._select_next(current, next_state)
            artifacts = self._validate_result_artifacts(work_id, packet, result, current)
            atomic_write_yaml(destination, result)
            state["artifacts"].extend(artifacts)
            state["active_invocation"] = None
            return self._transition(state, workflow, current, next_state, "WORKER_RESULT", [item["path"] for item in artifacts], invocation_id)

    def record_approval(self, work_id: str, decision: str, rationale: str, loopback_target: str | None = None, subject_sha256: str | None = None) -> dict[str, Any]:
        decision = decision.upper()
        with self.workspace.lock(work_id):
            state = self.workspace.load_state(work_id)
            workflow = self.registry.workflow(state["workflow"])
            current = workflow.state(state["current_state"])
            if current.owner != "t-understand":
                raise TUnderstandError("RT-APPROVAL-002", "Human decisions may only be recorded at orchestrator-owned states")
            if decision == "REJECT":
                if not loopback_target:
                    raise TUnderstandError("RT-APPROVAL-003", "REJECT requires loopback_target")
                self._validate_loopback_target(workflow, current, loopback_target)
            approval_id = f"APP-{uuid.uuid4().hex.upper()}"
            record = {
                "schema_id": "https://t-understand.dev/schemas/approval-record.schema.json",
                "schema_version": "1.0.0",
                "approval_id": approval_id,
                "work_id": work_id,
                "workflow": workflow.id,
                "state": current.id,
                "decision": decision,
                "recorded_by": "HUMAN",
                "rationale": rationale,
                "subject_sha256": subject_sha256,
                "loopback_target": loopback_target,
                "recorded_at": utc_now(),
            }
            publication_artifact = self.workspace.work_dir(work_id) / "artifacts" / "human-publication-approval" / f"{approval_id}.yaml"
            publication_artifact.parent.mkdir(parents=True, exist_ok=True)
            record["publication_artifact"] = publication_artifact.relative_to(self.workspace.work_dir(work_id)).as_posix()
            self.contracts.validate("approval-record", record)
            approval_path = self.workspace.work_dir(work_id) / "approvals" / f"{approval_id}.yaml"
            atomic_write_yaml(approval_path, record)
            atomic_write_yaml(publication_artifact, record)
            self.workspace.event(work_id, "HUMAN_DECISION_RECORDED", {"approval_id": approval_id, "decision": decision, "state": current.id})
            if decision == "REJECT":
                return self._apply_loopback(state, workflow, current, loopback_target or "", rationale, approval_id)
            return record

    def resume(self, work_id: str, reason: str) -> dict[str, Any]:
        with self.workspace.lock(work_id):
            state = self.workspace.load_state(work_id)
            if state["status"] != "BLOCKED":
                raise TUnderstandError("RT-RESUME-001", "Only a BLOCKED work item can be resumed")
            previous = state["blocker"]
            state["status"] = "ACTIVE"
            state["blocker"] = None
            state["active_invocation"] = None
            state["state_version"] += 1
            self.workspace.save_state(state)
            self.workspace.event(work_id, "WORK_RESUMED", {"reason": reason, "previous_blocker": previous})
            return state

    def validate_work(self, work_id: str) -> dict[str, Any]:
        state = self.workspace.load_state(work_id)
        workflow = self.registry.workflow(state["workflow"])
        current = workflow.state(state["current_state"])
        errors: list[str] = []
        if current.terminal and state["status"] != "COMPLETED":
            errors.append("terminal state is not marked COMPLETED")
        if not current.terminal and state["status"] == "COMPLETED":
            errors.append("nonterminal state is marked COMPLETED")
        for artifact in state["artifacts"]:
            path = resolve_within(self.workspace.work_dir(work_id), artifact["path"])
            if not path.is_file():
                errors.append(f"missing artifact: {artifact['path']}")
            elif sha256_file(path) != artifact["sha256"]:
                errors.append(f"digest mismatch: {artifact['path']}")
        active_packet = None
        if state["active_invocation"]:
            packet_path = self.workspace.work_dir(work_id) / "delegations" / f"{state['active_invocation']}.yaml"
            if not packet_path.is_file():
                errors.append(f"missing active delegation: {state['active_invocation']}")
            else:
                try:
                    active_packet = load_yaml(packet_path)
                    self.contracts.validate("delegation-packet", active_packet)
                    if active_packet["workflow"] != state["workflow"] or active_packet["state"] != state["current_state"]:
                        errors.append("active delegation identity does not match current state")
                except TUnderstandError as exc:
                    errors.append(str(exc))
        contract_directories = {
            "delegations": "delegation-packet",
            "results": "result-envelope",
            "approvals": "approval-record",
            "transitions": "transition-record",
            "loopbacks": "loopback-record",
        }
        validated_records = 0
        for directory, contract in contract_directories.items():
            for path in sorted((self.workspace.work_dir(work_id) / directory).glob("*.yaml")):
                try:
                    self.contracts.validate(contract, load_yaml(path))
                    validated_records += 1
                except TUnderstandError as exc:
                    errors.append(f"{path.relative_to(self.workspace.work_dir(work_id))}: {exc}")
        event_path = self.workspace.work_dir(work_id) / "events" / "events.jsonl"
        event_count = 0
        if event_path.is_file():
            import json
            for line_number, line in enumerate(event_path.read_text(encoding="utf-8").splitlines(), 1):
                try:
                    event = json.loads(line)
                    if not {"event_id", "occurred_at", "type", "payload"}.issubset(event):
                        errors.append(f"event line {line_number} lacks required fields")
                    event_count += 1
                except json.JSONDecodeError:
                    errors.append(f"event line {line_number} is invalid JSON")
        else:
            errors.append("missing event log")
        return {
            "status": "PASS" if not errors else "FAIL",
            "work_id": work_id,
            "errors": errors,
            "artifact_count": len(state["artifacts"]),
            "validated_runtime_records": validated_records,
            "event_count": event_count,
        }

    def _build_packet(self, state: dict[str, Any], workflow: WorkflowSpec, current: StateSpec, objective: str | None) -> dict[str, Any]:
        profile = self.registry.profile(state["profile"])
        invocation_id = f"INV-{uuid.uuid4().hex.upper()}"
        outputs = []
        for artifact_type in current.outputs:
            outputs.append(
                {
                    "artifact_type": artifact_type,
                    "path": f"artifacts/{artifact_type}/{invocation_id}-{artifact_type}.yaml",
                }
            )
        evidence_inputs = [
            {"artifact_type": item["type"], "path": item["path"], "sha256": item["sha256"]}
            for item in state["artifacts"]
            if item["status"] == "CURRENT"
        ]
        generated_objective = objective or (
            f"Execute {current.skill} for {workflow.id}:{current.id}; use only supplied revision-bound inputs, "
            f"respect all denied permissions, and produce the declared structured output artifacts."
        )
        return {
            "schema_id": "https://t-understand.dev/schemas/delegation-packet.schema.json",
            "schema_version": "1.2.0",
            "invocation_id": invocation_id,
            "parent_agent": "t-understand",
            "target_agent": current.owner,
            "delegation_depth": 1,
            "workflow": workflow.id,
            "state": current.id,
            "state_version": state["state_version"],
            "skill": current.skill,
            "objective": generated_objective,
            "application_id": state.get("application_id"),
            "application_snapshot": state["application_snapshot"],
            "permissions": {
                "source_repository_read": "allow",
                "source_repository_write": "deny",
                "git_mutation": "deny",
                "delegate": "deny",
                "artifact_write_domains": self.registry.artifact_domains(current.outputs),
            },
            "inputs": evidence_inputs,
            "outputs": outputs,
            "stop_conditions": [
                "Required evidence is missing or stale.",
                "A requested action exceeds declared permissions.",
                "The output cannot satisfy its schema without assumption.",
            ],
            "context_budget": {
                "strategy": profile["context_strategy"],
                "one_primary_objective": bool(profile["one_primary_objective"]),
                "max_workers": int(profile["max_workers"]),
            },
            "issued_at": utc_now(),
        }

    def _require_active(self, state: dict[str, Any]) -> None:
        if state["status"] != "ACTIVE":
            raise TUnderstandError("RT-WORK-003", f"Work item must be ACTIVE, found {state['status']}")

    def _select_next(self, current: StateSpec, next_state: str | None) -> str:
        if not current.next_states:
            raise TUnderstandError("RT-TRANSITION-001", f"State has no next transition: {current.id}")
        if next_state is None:
            if len(current.next_states) != 1:
                raise TUnderstandError("RT-TRANSITION-002", f"State requires explicit next_state: {current.id}")
            return current.next_states[0]
        if next_state not in current.next_states:
            raise TUnderstandError("RT-TRANSITION-003", f"Invalid transition {current.id} -> {next_state}")
        return next_state

    def _transition(self, state: dict[str, Any], workflow: WorkflowSpec, current: StateSpec, next_state: str | None, trigger: str, artifacts: list[str], source_id: str | None = None) -> dict[str, Any]:
        target_id = self._select_next(current, next_state)
        target = workflow.state(target_id)
        transition_id = f"TRN-{uuid.uuid4().hex.upper()}"
        record = {
            "schema_id": "https://t-understand.dev/schemas/transition-record.schema.json",
            "schema_version": "1.0.0",
            "transition_id": transition_id,
            "work_id": state["work_id"],
            "workflow": workflow.id,
            "from_state": current.id,
            "to_state": target.id,
            "trigger": trigger,
            "actor": "t-understand",
            "source_id": source_id,
            "artifact_paths": artifacts,
            "state_version_before": state["state_version"],
            "state_version_after": state["state_version"] + 1,
            "transitioned_at": utc_now(),
        }
        self.contracts.validate("transition-record", record)
        path = self.workspace.work_dir(state["work_id"]) / "transitions" / f"{transition_id}.yaml"
        atomic_write_yaml(path, record)
        state["current_state"] = target.id
        state["active_invocation"] = None
        state["blocker"] = None
        state["state_version"] += 1
        state["status"] = "COMPLETED" if target.terminal else "ACTIVE"
        self.workspace.save_state(state)
        self.workspace.event(state["work_id"], "STATE_TRANSITIONED", {"transition_id": transition_id, "from": current.id, "to": target.id, "trigger": trigger})
        return state

    def _validate_result_identity(self, state: dict[str, Any], packet: dict[str, Any], result: dict[str, Any]) -> None:
        expected = {
            "invocation_id": packet["invocation_id"],
            "parent_agent": "t-understand",
            "worker": packet["target_agent"],
            "delegation_depth": 1,
            "workflow": state["workflow"],
            "state": state["current_state"],
            "state_version": packet["state_version"],
        }
        for key, value in expected.items():
            if result.get(key) != value:
                raise TUnderstandError("RT-RESULT-004", f"Result {key} mismatch: expected {value!r}, found {result.get(key)!r}")
        if state["state_version"] != packet["state_version"] + 1:
            raise TUnderstandError("RT-RESULT-005", "Delegation packet is stale relative to work state")

    def _validate_result_artifacts(self, work_id: str, packet: dict[str, Any], result: dict[str, Any], current: StateSpec) -> list[dict[str, Any]]:
        expected = {item["artifact_type"]: item["path"] for item in packet["outputs"]}
        observed = {item["type"]: item for item in result["artifacts"]}
        if set(expected) != set(observed):
            raise TUnderstandError("RT-RESULT-006", f"Result artifacts must exactly match expected types: {sorted(expected)}")
        validated = []
        for artifact_type, expected_path in expected.items():
            item = observed[artifact_type]
            if item["path"] != expected_path:
                raise TUnderstandError("RT-RESULT-007", f"Artifact path mismatch for {artifact_type}")
            path = resolve_within(self.workspace.work_dir(work_id), item["path"])
            if not path.is_file():
                raise TUnderstandError("RT-RESULT-008", f"Declared artifact file is missing: {item['path']}")
            digest = sha256_file(path)
            if digest != item["sha256"]:
                raise TUnderstandError("RT-RESULT-009", f"Artifact digest mismatch: {item['path']}")
            validated.append({**item, "produced_state": current.id, "producer": packet["target_agent"], "status": "CURRENT"})
        return validated

    def _validate_expected_artifact_args(self, current: StateSpec, artifact_args: dict[str, Path]) -> None:
        expected = set(current.outputs)
        observed = set(artifact_args)
        if expected != observed:
            raise TUnderstandError("RT-ROOT-002", f"Root artifacts must exactly match expected types: {sorted(expected)}")

    def _validate_loopback_target(self, workflow: WorkflowSpec, current: StateSpec, target_id: str) -> None:
        target = workflow.state(target_id)
        if target.terminal:
            raise TUnderstandError("RT-LOOPBACK-001", "Loopback target cannot be terminal")
        if workflow.index(target_id) > workflow.index(current.id):
            raise TUnderstandError("RT-LOOPBACK-002", f"Loopback target must not be later than current state: {target_id}")

    def _apply_loopback(self, state: dict[str, Any], workflow: WorkflowSpec, current: StateSpec, target_id: str, reason: str, source_id: str) -> dict[str, Any]:
        self._validate_loopback_target(workflow, current, target_id)
        target_index = workflow.index(target_id)
        for artifact in state["artifacts"]:
            if workflow.index(artifact["produced_state"]) >= target_index:
                artifact["status"] = "STALE"
        loopback_id = f"LBK-{uuid.uuid4().hex.upper()}"
        record = {
            "schema_id": "https://t-understand.dev/schemas/loopback-record.schema.json",
            "schema_version": "1.0.0",
            "loopback_id": loopback_id,
            "work_id": state["work_id"],
            "workflow": workflow.id,
            "from_state": current.id,
            "to_state": target_id,
            "reason": reason,
            "source_id": source_id,
            "invalidated_artifacts": [item["path"] for item in state["artifacts"] if item["status"] == "STALE"],
            "recorded_at": utc_now(),
        }
        self.contracts.validate("loopback-record", record)
        atomic_write_yaml(self.workspace.work_dir(state["work_id"]) / "loopbacks" / f"{loopback_id}.yaml", record)
        state["current_state"] = target_id
        state["status"] = "ACTIVE"
        state["active_invocation"] = None
        state["blocker"] = None
        state["state_version"] += 1
        self.workspace.save_state(state)
        self.workspace.event(state["work_id"], "LOOPBACK_APPLIED", {"loopback_id": loopback_id, "from": current.id, "to": target_id, "reason": reason})
        return state

    def _latest_approval(self, work_id: str, state_id: str) -> dict[str, Any] | None:
        approval_dir = self.workspace.work_dir(work_id) / "approvals"
        records = []
        for path in approval_dir.glob("APP-*.yaml"):
            record = load_yaml(path)
            self.contracts.validate("approval-record", record)
            if record["state"] == state_id:
                records.append(record)
        if not records:
            return None
        return sorted(records, key=lambda item: item["recorded_at"])[-1]
