from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .errors import TUnderstandError


@dataclass(frozen=True)
class StateSpec:
    workflow: str
    id: str
    owner: str
    terminal: bool
    outputs: tuple[str, ...]
    skill: str | None
    next_states: tuple[str, ...]


@dataclass(frozen=True)
class WorkflowSpec:
    id: str
    initial_state: str
    terminal_states: tuple[str, ...]
    states: tuple[StateSpec, ...]

    def state(self, state_id: str) -> StateSpec:
        for state in self.states:
            if state.id == state_id:
                return state
        raise TUnderstandError("RT-STATE-001", f"Unknown state {self.id}:{state_id}")

    def index(self, state_id: str) -> int:
        for index, state in enumerate(self.states):
            if state.id == state_id:
                return index
        raise TUnderstandError("RT-STATE-001", f"Unknown state {self.id}:{state_id}")


class Registry:
    def __init__(self, root: Path):
        self.root = root
        self._workflow_doc = self._load("orchestrator/workflow-registry.yaml")
        self._agent_doc = self._load("orchestrator/agent-registry.yaml")
        self._artifact_doc = self._load("orchestrator/artifact-registry.yaml")
        self._authority_doc = self._load("orchestrator/authority-matrix.yaml")
        self._model_doc = self._load("orchestrator/model-profiles.yaml")
        self.workflows = self._parse_workflows()
        self.agents = {item["id"]: item for item in self._agent_doc["agents"]}
        self.artifacts = {item["id"]: item for item in self._artifact_doc["artifacts"]}
        self.authorities = self._authority_doc["roles"]
        self.profiles = self._model_doc["profiles"]

    def _load(self, relative: str) -> dict[str, Any]:
        path = self.root / relative
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise TUnderstandError("RT-REGISTRY-001", f"Missing canonical registry: {relative}") from exc
        if not isinstance(data, dict):
            raise TUnderstandError("RT-REGISTRY-002", f"Registry must contain an object: {relative}")
        return data

    def _parse_workflows(self) -> dict[str, WorkflowSpec]:
        workflows: dict[str, WorkflowSpec] = {}
        for workflow in self._workflow_doc["workflows"]:
            states = tuple(
                StateSpec(
                    workflow=workflow["id"],
                    id=state["id"],
                    owner=state["owner"],
                    terminal=bool(state.get("terminal", False)),
                    outputs=tuple(state.get("outputs", [])),
                    skill=state.get("skill"),
                    next_states=tuple(state.get("next_states", [])),
                )
                for state in workflow["states"]
            )
            workflows[workflow["id"]] = WorkflowSpec(
                id=workflow["id"],
                initial_state=workflow["initial_state"],
                terminal_states=tuple(workflow["terminal_states"]),
                states=states,
            )
        return workflows

    def workflow(self, workflow_id: str) -> WorkflowSpec:
        try:
            return self.workflows[workflow_id]
        except KeyError as exc:
            raise TUnderstandError("RT-WORKFLOW-001", f"Unknown workflow: {workflow_id}") from exc

    def profile(self, profile_id: str) -> dict[str, Any]:
        try:
            return self.profiles[profile_id]
        except KeyError as exc:
            raise TUnderstandError("RT-PROFILE-001", f"Unknown model profile: {profile_id}") from exc

    def artifact_domains(self, artifact_ids: tuple[str, ...]) -> list[str]:
        domains: list[str] = []
        for artifact_id in artifact_ids:
            artifact = self.artifacts.get(artifact_id)
            if artifact is None:
                raise TUnderstandError("RT-ARTIFACT-001", f"Unknown artifact type: {artifact_id}")
            if artifact["domain"] not in domains:
                domains.append(artifact["domain"])
        return domains
