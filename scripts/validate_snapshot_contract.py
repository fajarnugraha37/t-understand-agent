from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--report", default=str(ROOT / "reports" / "snapshot-contract-report.json"))
args = parser.parse_args()

checks = 0
errors: list[str] = []


def check(condition: bool, message: str) -> None:
    global checks
    checks += 1
    if not condition:
        errors.append(message)


policy = yaml.safe_load((ROOT / "orchestrator" / "snapshot-policy.yaml").read_text(encoding="utf-8"))
check(policy["source_repository"]["access"] == "READ_ONLY", "snapshot policy must keep source repositories read-only")
check(policy["source_repository"]["git_mutation"] == "deny", "snapshot policy must deny Git mutation")
check(policy["snapshot_ids"]["immutable"] is True, "snapshot IDs must be immutable")
check(policy["snapshot_ids"]["reuse"] == "deny", "snapshot ID reuse must be denied")
check(policy["application_snapshot"]["absolute_paths"] == "deny", "application snapshots must deny absolute paths")
check(policy["worktree_capture"]["ignored_files"] == "exclude", "ignored files must be excluded")
check(policy["worktree_capture"]["protected_paths"] == "deny", "protected paths must be denied")
check(policy["worktree_capture"]["untracked_symlinks"] == "deny", "untracked symlinks must be denied")
check(policy["worktree_capture"]["dirty_submodules"] == "deny", "dirty submodules must be denied")
check(policy["worktree_capture"]["race_detection"] == "required", "snapshot race detection must be required")
check(policy["integrity"]["snapshot_directory_commit"] == "atomic-rename", "snapshot directory commit must be atomic")
check(policy["review_target"]["immutable"] is True, "review targets must be immutable")

contracts = (ROOT / "runtime" / "tu_runtime" / "core" / "contracts.py").read_text(encoding="utf-8")
for name in (
    "repository-snapshot", "application-snapshot", "snapshot-validation-report",
    "snapshot-drift-report", "review-target",
):
    check(f'"{name}"' in contracts, f"Contract validator must register {name}")

cli = (ROOT / "runtime" / "tu_runtime" / "cli.py").read_text(encoding="utf-8")
for command in (
    "snapshot-create", "snapshot-show", "snapshot-list", "snapshot-validate", "snapshot-drift",
    "review-target-create", "review-target-show", "review-target-validate",
):
    check(command in cli, f"CLI command is missing: {command}")

snapshot = (ROOT / "runtime" / "tu_runtime" / "core" / "snapshot.py").read_text(encoding="utf-8")
for invariant in (
    "GIT_OPTIONAL_LOCKS", "SNAP-RACE-001", "SNAP-PROTECTED-001", "SNAP-SYMLINK-001",
    "SNAP-SUBMODULE-001", "MAX_PATCH_BYTES", "MAX_TOTAL_UNTRACKED_BYTES", "atomic-rename",
):
    if invariant == "atomic-rename":
        check("os.replace(temp_dir, final_dir)" in snapshot, "Snapshot directory must be committed with atomic rename")
    else:
        check(invariant in snapshot, f"Snapshot runtime invariant is missing: {invariant}")
for mutation in ("checkout", "commit", "add", "reset", "clean", "merge", "rebase", "tag"):
    invocations = (f'git.text("{mutation}"', f'git.bytes("{mutation}"', f'subprocess.run(["git", "-C", str(source), "{mutation}"')
    check(not any(value in snapshot for value in invocations), f"Snapshot runtime must not invoke Git mutation command {mutation}")

artifact_registry = yaml.safe_load((ROOT / "orchestrator" / "artifact-registry.yaml").read_text(encoding="utf-8"))
artifacts = {item["id"]: item for item in artifact_registry["artifacts"]}
for artifact_id, writer in (
    ("application-snapshot", "tu-discoverer"),
    ("repository-snapshot", "tu-discoverer"),
    ("snapshot-drift-report", "tu-discoverer"),
    ("snapshot-validation-report", "tu-verifier"),
    ("review-target", "tu-discoverer"),
):
    check(artifact_id in artifacts, f"Artifact registry is missing {artifact_id}")
    if artifact_id in artifacts:
        check(artifacts[artifact_id]["canonical_writer"] == writer, f"{artifact_id} has the wrong canonical writer")
        check(artifacts[artifact_id]["source_repository_write_required"] is False, f"{artifact_id} must not require source writes")

report = {"status": "PASS" if not errors else "FAIL", "checks": checks, "errors": errors}
Path(args.report).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
raise SystemExit(0 if not errors else 1)
