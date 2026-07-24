from __future__ import annotations

import argparse
import json
import os
import platform
import queue
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPT = "generate comprehensive, complete, detailed and deep documentation"


def run_checked(command: list[str], *, cwd: Path, env: dict[str, str], timeout: float = 120.0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {' '.join(command)}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def initialize_fixture(repository: Path, env: dict[str, str]) -> None:
    repository.mkdir(parents=True)
    run_checked(["git", "init"], cwd=repository, env=env)
    run_checked(["git", "config", "user.email", "ci@example.test"], cwd=repository, env=env)
    run_checked(["git", "config", "user.name", "t-understand CI"], cwd=repository, env=env)

    (repository / "README.md").write_text(
        "# Order API\n\nA small repository used to exercise the complete documentation pipeline.\n",
        encoding="utf-8",
    )
    (repository / "pom.xml").write_text(
        """<project xmlns=\"http://maven.apache.org/POM/4.0.0\">
  <modelVersion>4.0.0</modelVersion>
  <groupId>example</groupId><artifactId>order-api</artifactId><version>1.0.0</version>
</project>
""",
        encoding="utf-8",
    )
    (repository / "openapi.yaml").write_text(
        """openapi: 3.0.3
info:
  title: Order API
  version: 1.0.0
servers:
  - url: https://api.example.test/v1
    description: production
paths:
  /orders:
    post:
      operationId: createOrder
      responses:
        '202':
          description: accepted
components:
  schemas:
    Order:
      type: object
      properties:
        id:
          type: string
""",
        encoding="utf-8",
    )

    source = repository / "src" / "main" / "java" / "example" / "orders"
    source.mkdir(parents=True)
    for index in range(120):
        (source / f"OrderComponent{index:03d}.java").write_text(
            f"""package example.orders;

public final class OrderComponent{index:03d} {{
    public String componentName() {{ return \"order-component-{index:03d}\"; }}
}}
""",
            encoding="utf-8",
        )

    run_checked(["git", "add", "."], cwd=repository, env=env)
    run_checked(["git", "commit", "-m", "fixture"], cwd=repository, env=env)


def read_stream(stream, output: list[str], first_line: queue.Queue[str]) -> None:
    try:
        for line in iter(stream.readline, ""):
            output.append(line)
            if not first_line.full():
                try:
                    first_line.put_nowait(line)
                except queue.Full:
                    pass
    finally:
        stream.close()


def execute_documentation(engine: Path, repository: Path, env: dict[str, str], timeout: float) -> tuple[dict, str, float]:
    command = [sys.executable, str(engine), "agent-document", "--prompt", PROMPT]
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    first_stderr: queue.Queue[str] = queue.Queue(maxsize=1)
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=repository,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
    )
    assert process.stdout is not None and process.stderr is not None
    stdout_thread = threading.Thread(target=read_stream, args=(process.stdout, stdout_lines, queue.Queue(maxsize=1)), daemon=True)
    stderr_thread = threading.Thread(target=read_stream, args=(process.stderr, stderr_lines, first_stderr), daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    try:
        first = first_stderr.get(timeout=10.0)
        if "Documentation workflow started" not in first:
            raise AssertionError(f"unexpected first stderr line: {first!r}")
        process.wait(timeout=timeout)
    except Exception:
        process.kill()
        process.wait(timeout=10.0)
        raise
    finally:
        stdout_thread.join(timeout=5.0)
        stderr_thread.join(timeout=5.0)

    elapsed = time.monotonic() - started
    stdout = "".join(stdout_lines).strip()
    stderr = "".join(stderr_lines)
    if process.returncode != 0:
        raise AssertionError(
            f"agent-document failed ({process.returncode}) after {elapsed:.2f}s\nstdout:\n{stdout}\nstderr:\n{stderr}"
        )
    if not stdout:
        raise AssertionError("agent-document completed without final JSON output")
    result = json.loads(stdout)
    return result, stderr, elapsed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=str(ROOT / "reports" / "agent-document-e2e-report.json"))
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    base_env = {**os.environ, "PYTHONUNBUFFERED": "1", "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"}

    with tempfile.TemporaryDirectory(prefix="t-understand-e2e-") as raw:
        temp = Path(raw)
        repository = temp / "fixture-repository"
        install_root = temp / "opencode"
        installer_context = temp / "installer-context"
        initialize_fixture(repository, base_env)

        install_env = {**base_env, "T_UNDERSTAND_CONTEXT_ROOT": str(installer_context)}
        run_checked(
            [str(ROOT / "bin" / "install.sh"), "opencode", "--install-root", str(install_root)],
            cwd=ROOT,
            env=install_env,
            timeout=120.0,
        )
        engine = install_root / "t-understand-engine" / "agent_runtime.py"
        if not engine.is_file():
            raise AssertionError(f"installed engine is missing: {engine}")

        execution_env = dict(base_env)
        execution_env.pop("T_UNDERSTAND_CONTEXT_ROOT", None)
        execution_env.pop("T_UNDERSTAND_WORKSPACE", None)
        result, stderr, elapsed = execute_documentation(engine, repository, execution_env, args.timeout)

        output = repository / ".t-understand" / "output" / "documentation" / "latest"
        required = [
            output / "index.md",
            output / "_meta" / "manifest.yaml",
            output / "_meta" / "document-plan.yaml",
            output / "_meta" / "coverage-ledger.yaml",
            output / "_meta" / "validation.yaml",
        ]
        missing = [str(path.relative_to(repository)) for path in required if not path.is_file()]
        if missing:
            raise AssertionError(f"documentation output is incomplete: {missing}")
        if result.get("status") != "PASS":
            raise AssertionError(f"agent completion status is not PASS: {result}")
        if result.get("documents", 0) < 41:
            raise AssertionError(f"mandatory documentation catalog was not generated: {result.get('documents')}")

        report = {
            "status": "PASS",
            "platform": platform.platform(),
            "python": sys.version,
            "elapsed_seconds": round(elapsed, 3),
            "timeout_seconds": args.timeout,
            "fixture_files": 123,
            "documents": result["documents"],
            "heartbeat_lines": len([line for line in stderr.splitlines() if line.startswith("[t-understand]")]),
            "required_artifacts": [str(path.relative_to(repository)) for path in required],
        }
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
