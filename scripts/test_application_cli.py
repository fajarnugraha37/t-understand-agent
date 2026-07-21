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
parser.add_argument("--report", default=str(ROOT / "reports" / "application-cli-report.json"))
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


def git(path: Path, *values: str) -> None:
    subprocess.run(["git", "-C", str(path), *values], text=True, capture_output=True, check=True)


with tempfile.TemporaryDirectory() as temp:
    base = Path(temp)
    context = base / "context"
    source = base / "source"
    source.mkdir()
    git(source, "init", "-q")
    git(source, "config", "user.email", "cli@test.local")
    git(source, "config", "user.name", "CLI Test")
    (source / "README.md").write_text("test\n", encoding="utf-8")
    git(source, "add", ".")
    git(source, "commit", "-qm", "initial")
    git(source, "remote", "add", "origin", "git@github.com:acme/cli-source.git")

    prefix = ("--context-root", str(context))
    initialized = run(*prefix, "application-init", "--application-id", "cli-app", "--name", "CLI App", "--workspace-model", "single-repo", "--machine-id", "cli-machine")
    if initialized.get("status") != "INITIALIZED": errors.append("application-init did not initialize")
    repository = run(*prefix, "repository-add", "--repository-id", "source", "--name", "Source", "--role", "backend", "--remote", "https://github.com/acme/cli-source.git")
    if repository.get("source_access") != "READ_ONLY": errors.append("repository-add did not enforce read-only")
    bound = run(*prefix, "workspace-bind", "--repository-id", "source", "--path", str(source))
    if bound.get("status") != "BOUND": errors.append("workspace-bind did not bind")
    resolved = run(*prefix, "workspace-resolve")
    if resolved.get("status") != "RESOLVED": errors.append("workspace-resolve did not resolve")
    validation = run(*prefix, "application-validate", "--inspect-workspace")
    if validation.get("status") != "PASS": errors.append("application-validate did not pass")
    shown = run(*prefix, "application-show")
    if shown.get("application", {}).get("application", {}).get("id") != "cli-app": errors.append("application-show returned wrong application")
    previous_workspace = os.environ.get("T_UNDERSTAND_WORKSPACE")
    os.environ["T_UNDERSTAND_WORKSPACE"] = str(source)
    try:
        bootstrapped = run("agent-bootstrap")
        if bootstrapped.get("managed_state") != str(source / ".t-understand"):
            errors.append("agent bootstrap did not select automatic .t-understand state")
        automatic = run("application-show")
        if automatic.get("application", {}).get("application", {}).get("id") != "source":
            errors.append("application-show did not use automatic workspace context")
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
