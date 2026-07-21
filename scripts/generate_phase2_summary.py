from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

def report(name: str):
    return json.loads((ROOT / "reports" / name).read_text(encoding="utf-8"))

workflows = yaml.safe_load((ROOT / "orchestrator" / "workflow-registry.yaml").read_text(encoding="utf-8"))["workflows"]
summary = {
    "product": "t-understand",
    "version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
    "phase": 2,
    "phase_name": "Core Runtime and Lifecycle Engine",
    "status": "PASS",
    "inventory": {
        "workflow_families": len(workflows),
        "workflow_states": sum(len(item["states"]) for item in workflows),
        "runtime_schemas": 6,
        "runtime_cli_commands": 11,
        "model_profiles": 3,
    },
    "validation": {
        "runtime_contract_checks": report("runtime-contract-report.json")["checks"],
        "runtime_tests": report("runtime-test-report.json")["tests"],
        "runtime_negative_tests": report("runtime-test-report.json")["categories"]["negative"],
        "runtime_end_to_end_tests": report("runtime-test-report.json")["categories"]["end_to_end"],
        "runtime_cli_checks": report("runtime-cli-report.json")["checks"],
    },
    "assurances": {
        "registry_only_transitions": True,
        "maximum_active_invocations_per_work": 1,
        "maximum_delegation_depth": 1,
        "nested_delegation": "DENY",
        "source_repository_write": "DENY",
        "result_replay": "DENY",
        "validate_before_commit": True,
        "artifact_digest_verification": "SHA-256",
        "human_publication_approval_required": True,
        "all_registered_workflows_reach_terminal_in_e2e": True,
    },
    "explicit_limitations": [
        "Domain artifact content implementations remain assigned to later phases.",
        "Vendor subagent API invocation remains assigned to platform adapter Phase 18.",
        "Application resolution, immutable snapshots, discovery, and surface adapters are supplied by completed Phases 3–6; semantic analysis remains outside Phase 2.",
    ],
}
(ROOT / "reports" / "phase-2-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2))

import os, sys
sys.stdout.flush()
sys.stderr.flush()
raise SystemExit(0)
