from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ROOT))

from tu_runtime.core.contracts import ContractValidator
from tu_runtime.core.registry import Registry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="reports/runtime-contract-report.json")
    args = parser.parse_args()
    registry = Registry(ROOT)
    ContractValidator(ROOT)
    errors = []
    checks = 0
    supported_strategies = {"evidence-slices", "bounded-evidence-packets", "expanded-evidence-packets"}
    for workflow in registry.workflows.values():
        checks += 1
        if workflow.state(workflow.initial_state).terminal:
            errors.append(f"initial state is terminal: {workflow.id}")
        for state in workflow.states:
            checks += 8
            if state.owner not in registry.agents:
                errors.append(f"unknown owner: {workflow.id}:{state.id}:{state.owner}")
            if state.terminal and state.owner != "t-understand":
                errors.append(f"terminal state not owned by root: {workflow.id}:{state.id}")
            if state.terminal and (state.outputs or state.skill or state.next_states):
                errors.append(f"terminal state has executable contract: {workflow.id}:{state.id}")
            if not state.terminal and not state.skill:
                errors.append(f"nonterminal state lacks skill: {workflow.id}:{state.id}")
            if not state.terminal and len(state.next_states) < 1:
                errors.append(f"nonterminal state lacks transition: {workflow.id}:{state.id}")
            if state.owner != "t-understand" and registry.agents[state.owner]["can_delegate"]:
                errors.append(f"worker can delegate: {state.owner}")
            if state.owner != "t-understand" and registry.agents[state.owner]["max_delegation_depth"] != 0:
                errors.append(f"worker depth is not zero: {state.owner}")
            for artifact_id in state.outputs:
                artifact = registry.artifacts[artifact_id]
                if artifact["canonical_writer"] != state.owner:
                    errors.append(f"state output writer mismatch: {workflow.id}:{state.id}:{artifact_id}")
    for profile_id, profile in registry.profiles.items():
        checks += 5
        if profile["maximum_delegation_depth"] != 1:
            errors.append(f"profile delegation depth is not one: {profile_id}")
        if profile["context_strategy"] not in supported_strategies:
            errors.append(f"unsupported context strategy: {profile_id}")
        if not profile["one_primary_objective"]:
            errors.append(f"profile permits multiple objectives: {profile_id}")
        if not profile["structured_output_required"]:
            errors.append(f"profile does not require structured output: {profile_id}")
        if not profile["deterministic_verification_required"]:
            errors.append(f"profile does not require deterministic verification: {profile_id}")
    report = {
        "status": "PASS" if not errors else "FAIL",
        "checks": checks,
        "workflow_families": len(registry.workflows),
        "workflow_states": sum(len(item.states) for item in registry.workflows.values()),
        "model_profiles": len(registry.profiles),
        "errors": errors,
    }
    path = ROOT / args.report
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    import os
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    raise SystemExit(code)
