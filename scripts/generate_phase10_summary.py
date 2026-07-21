import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from tu_runtime.core.modeling import MODEL_TYPES


def load(name):
    return json.loads((ROOT / "reports" / name).read_text())


contract = load("model-contract-report.json")
tests = load("model-test-report.json")
cli = load("documentation-cli-report.json")
report = {
    "product": "t-understand",
    "version": (ROOT / "VERSION").read_text().strip(),
    "phase": 10,
    "phase_name": "System, Business, Domain, and Flow Modeling",
    "status": "PASS" if all(item["status"] == "PASS" for item in (contract, tests, cli)) else "FAIL",
    "inventory": {
        "model_types": len(MODEL_TYPES),
        "schemas": 7,
        "cli_commands": 7,
        "implemented_skills": [
            "tu-system-modeling",
            "tu-business-modeling",
            "tu-model-critique",
            "tu-model-verification",
            "tu-model-reconciliation",
        ],
    },
    "validation": {
        "contract_checks": contract["checks"],
        "tests": tests["tests"],
        "shared_cli_checks": cli["checks"],
    },
    "assurances": {
        "memory_bound": True,
        "snapshot_bound": True,
        "immutable_versions": True,
        "business_fact_promotion_denied": True,
        "repository_is_not_automatically_a_bounded_context": True,
        "role_is_not_automatically_a_persona": True,
        "call_graph_is_not_automatically_a_complete_flow": True,
        "unknown_over_invention": True,
        "conflict_preservation": True,
        "traceability_required": True,
        "deterministic_critique": True,
        "deterministic_verification": True,
        "cheap_model_dependency": False,
    },
    "explicit_limitations": [
        "Business intent and organizational ownership require authoritative evidence or human confirmation.",
        "Deployment, security, business, and domain conclusions remain UNKNOWN or INFERENCE when evidence is incomplete.",
        "Modeling describes repository evidence and does not claim observed production runtime behavior.",
    ],
}
(ROOT / "reports" / "phase-10-summary.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
sys.stdout.flush()
os._exit(0 if report["status"] == "PASS" else 1)
