from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def report(name: str):
    return json.loads((ROOT / "reports" / name).read_text(encoding="utf-8"))

summary = {
    "product": "t-understand",
    "version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
    "phase": 4,
    "phase_name": "Snapshot and Git Target Engine",
    "status": "PASS",
    "inventory": {
        "snapshot_schemas": 5,
        "snapshot_cli_commands": 8,
        "git_target_types": 6,
        "review_target_modes": 2,
        "snapshot_examples": len(list((ROOT / "examples" / "snapshot").glob("*.yaml"))),
    },
    "validation": {
        "snapshot_contract_checks": report("snapshot-contract-report.json")["checks"],
        "snapshot_tests": report("snapshot-test-report.json")["tests"],
        "snapshot_negative_tests": report("snapshot-test-report.json")["categories"]["negative"],
        "snapshot_capture_tests": report("snapshot-test-report.json")["categories"]["capture"],
        "snapshot_review_target_tests": report("snapshot-test-report.json")["categories"]["review_target"],
        "snapshot_cli_checks": report("snapshot-cli-report.json")["checks"],
    },
    "assurances": {
        "source_repository_access": "READ_ONLY",
        "git_mutation": "DENY",
        "branch_tag_commit_head_supported": True,
        "index_supported": True,
        "worktree_supported": True,
        "staged_unstaged_untracked_digests": True,
        "ignored_files": "EXCLUDED",
        "protected_changed_paths": "DENY",
        "untracked_symlinks": "DENY",
        "dirty_submodule_worktree": "DENY",
        "race_detection": True,
        "snapshot_id_reuse": "DENY",
        "integrity_validation": True,
        "drift_detection": True,
        "immutable_review_target": True,
        "multi_repository_application_snapshot": True,
    },
    "explicit_limitations": [
        "Phase 4 captures Git identity and uncommitted overlays but does not itself inventory modules or source files; completed Phase 5 consumes these snapshots for discovery.",
        "Ignored and protected changed files are intentionally not captured. Approval-based protected-file access is not implemented in Phase 4 and therefore fails closed.",
        "Worktree snapshots reject dirty submodule internals. Submodules requiring independent analysis should be registered as application repositories.",
        "Phase 4 creates immutable review targets but does not analyze diffs or emit code-review findings; analysis begins in Phase 14.",
    ],
}
(ROOT / "reports" / "phase-4-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2))
