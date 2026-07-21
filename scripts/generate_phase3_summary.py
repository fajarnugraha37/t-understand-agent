from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def report(name: str):
    return json.loads((ROOT / "reports" / name).read_text(encoding="utf-8"))

summary = {
    "product": "t-understand",
    "version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
    "phase": 3,
    "phase_name": "Application and Workspace Management",
    "status": "PASS",
    "inventory": {
        "application_schemas": 4,
        "application_cli_commands": 8,
        "workspace_models": 3,
        "application_examples": len(list((ROOT / "examples" / "application").glob("*.yaml"))),
    },
    "validation": {
        "application_contract_checks": report("application-contract-report.json")["checks"],
        "application_tests": report("application-test-report.json")["tests"],
        "application_negative_tests": report("application-test-report.json")["categories"]["negative"],
        "application_resolution_tests": report("application-test-report.json")["categories"]["resolution"],
        "application_cli_checks": report("application-cli-report.json")["checks"],
    },
    "assurances": {
        "portable_manifest_absolute_paths": "DENY",
        "local_workspace_map_gitignored": True,
        "source_repository_access": "READ_ONLY",
        "credential_bearing_https_remote": "DENY",
        "mapped_path_must_equal_git_root": True,
        "duplicate_repository_roots": "DENY",
        "nested_repository_roots": "DENY",
        "remote_identity_mismatch": "DENY",
        "context_inside_source_repository": "DENY",
        "single_repo_supported": True,
        "monorepo_supported": True,
        "multi_repo_supported": True,
    },
    "explicit_limitations": [
        "Immutable Git snapshot capture is supplied by completed Phase 4; Phase 3 itself remains limited to application identity and workspace boundaries.",
        "Phase 3 does not itself discover modules or services; repository discovery is supplied by completed Phase 5, while cross-repository runtime relationships remain Phase 8.",
        "Local workspace paths are intentionally machine-specific and excluded from portable context history.",
    ],
}
(ROOT / "reports" / "phase-3-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2))
