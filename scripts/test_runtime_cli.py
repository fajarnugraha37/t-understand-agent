from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ROOT))

from tu_runtime.cli import main as cli_main


def run(runtime_root: Path, *args: str, expect: int = 0) -> dict:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = cli_main(["--runtime-root", str(runtime_root), *args])
    if code != expect:
        raise RuntimeError(
            f"CLI invocation failed {args}: rc={code}\nstdout={stdout.getvalue()}\nstderr={stderr.getvalue()}"
        )
    stream = stdout.getvalue() if expect == 0 else stderr.getvalue()
    return json.loads(stream)


def execute(report_path: str) -> int:
    checks = []
    with tempfile.TemporaryDirectory() as temp:
        runtime_root = Path(temp) / "runtime"
        workflows = run(runtime_root, "workflows")
        checks.append({"id": "list-workflows", "pass": len(workflows["workflows"]) == 5})
        created = run(runtime_root, "init", "--work-id", "CLI_FLOW", "--workflow", "foundation", "--snapshot", "APP-SNAP-CLI")
        checks.append({"id": "init", "pass": created["current_state"] == "APPLICATION_ALIGNMENT"})
        bad = run(runtime_root, "init", "--work-id", "bad", "--workflow", "foundation", "--snapshot", "APP-SNAP-CLI", expect=2)
        checks.append({"id": "invalid-work-id", "pass": bad["code"] == "RT-WORK-001"})
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            missing_root_code = cli_main(["status", "--work-id", "CLI_FLOW"])
        missing_root = json.loads(stderr.getvalue())
        checks.append({"id": "explicit-runtime-root", "pass": missing_root_code == 2 and missing_root["code"] == "CLI-RUNTIME-001"})
    report = {
        "status": "PASS" if all(item["pass"] for item in checks) else "FAIL",
        "checks": len(checks),
        "mode": "in-process CLI parser and command smoke; launcher syntax is checked separately",
        "results": checks,
    }
    path = ROOT / report_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="reports/runtime-cli-report.json")
    args = parser.parse_args()
    return execute(args.report)


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    raise SystemExit(code)
