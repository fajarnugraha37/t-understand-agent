from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ROOT))

from tu_runtime.cli import main

parser = argparse.ArgumentParser()
parser.add_argument("--report", default=str(ROOT / "reports" / "snapshot-cli-report.json"))
args = parser.parse_args()

checks = 0
errors: list[str] = []


def run(*values: str, expect: int = 0) -> dict:
    global checks
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(list(values))
    checks += 1
    if code != expect:
        errors.append(f"command {' '.join(values)} returned {code}, expected {expect}: {stderr.getvalue()}")
    text = stdout.getvalue().strip() or stderr.getvalue().strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        errors.append(f"command {' '.join(values)} did not return JSON: {text}")
        return {}


def git(path: Path, *values: str) -> str:
    return subprocess.run(["git", "-C", str(path), *values], text=True, capture_output=True, check=True).stdout.strip()


with tempfile.TemporaryDirectory() as temp:
    base = Path(temp)
    context = base / "context"
    source = base / "source"
    source.mkdir()
    git(source, "init", "-q")
    git(source, "config", "user.email", "snapshot-cli@test.local")
    git(source, "config", "user.name", "Snapshot CLI Test")
    (source / "README.md").write_text("initial\n", encoding="utf-8")
    git(source, "add", ".")
    git(source, "commit", "-qm", "initial")
    git(source, "remote", "add", "origin", "git@github.com:acme/snapshot-cli.git")

    prefix = ("--context-root", str(context))
    run(*prefix, "application-init", "--application-id", "snapshot-cli", "--name", "Snapshot CLI", "--workspace-model", "single-repo", "--machine-id", "cli-machine")
    run(*prefix, "repository-add", "--repository-id", "source", "--name", "Source", "--role", "backend", "--remote", "https://github.com/acme/snapshot-cli.git")
    run(*prefix, "workspace-bind", "--repository-id", "source", "--path", str(source))

    head = run(*prefix, "snapshot-create", "--snapshot-id", "SNAP_HEAD", "--purpose", "review", "--target", "source=head")
    if head.get("status") != "CAPTURED": errors.append("snapshot-create HEAD did not capture")
    (source / "README.md").write_text("staged\n", encoding="utf-8")
    git(source, "add", "README.md")
    (source / "new.txt").write_text("untracked\n", encoding="utf-8")
    worktree = run(*prefix, "snapshot-create", "--snapshot-id", "SNAP_WORKTREE", "--purpose", "review", "--target", "source=worktree")
    if worktree.get("repositories", [{}])[0].get("target_type") != "worktree": errors.append("worktree target was not captured")
    validation = run(*prefix, "snapshot-validate", "--snapshot-id", "SNAP_WORKTREE")
    if validation.get("status") != "PASS": errors.append("snapshot validation did not pass")
    unchanged = run(*prefix, "snapshot-drift", "--snapshot-id", "SNAP_WORKTREE")
    if unchanged.get("status") != "UNCHANGED": errors.append("new worktree snapshot should be unchanged")
    target = run(*prefix, "review-target-create", "--review-id", "REVIEW_DIFF", "--mode", "diff", "--baseline", "SNAP_HEAD", "--candidate", "SNAP_WORKTREE")
    if target.get("mode") != "DIFF": errors.append("review target was not created")
    target_validation = run(*prefix, "review-target-validate", "--review-id", "REVIEW_DIFF")
    if target_validation.get("status") != "PASS": errors.append("review target validation did not pass")
    listed = run(*prefix, "snapshot-list")
    if len(listed.get("snapshots", [])) != 2: errors.append("snapshot-list did not return two snapshots")
    shown = run(*prefix, "snapshot-show", "--snapshot-id", "SNAP_HEAD")
    if shown.get("snapshot_id") != "SNAP_HEAD": errors.append("snapshot-show returned the wrong snapshot")
    (source / "new.txt").write_text("changed\n", encoding="utf-8")
    drifted = run(*prefix, "snapshot-drift", "--snapshot-id", "SNAP_WORKTREE", expect=3)
    if drifted.get("status") != "DRIFTED": errors.append("snapshot drift was not detected")
    previous_workspace = os.environ.get("T_UNDERSTAND_WORKSPACE")
    os.environ["T_UNDERSTAND_WORKSPACE"] = str(source)
    try:
        bootstrapped = run("agent-bootstrap")
        if bootstrapped.get("managed_state") != str(source / ".t-understand"):
            errors.append("agent bootstrap did not select automatic snapshot context")
        automatic = run("snapshot-list")
        if automatic.get("snapshots") != []:
            errors.append("automatic snapshot context should begin empty")
    finally:
        if previous_workspace is None:
            os.environ.pop("T_UNDERSTAND_WORKSPACE", None)
        else:
            os.environ["T_UNDERSTAND_WORKSPACE"] = previous_workspace

report = {
    "status": "PASS" if not errors else "FAIL",
    "checks": checks,
    "mode": "in-process CLI parser and command integration; launcher syntax is checked separately",
    "errors": errors,
}
Path(args.report).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
raise SystemExit(0 if not errors else 1)
