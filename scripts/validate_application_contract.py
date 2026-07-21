from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--report", default=str(ROOT / "reports" / "application-contract-report.json"))
args = parser.parse_args()

checks = 0
errors: list[str] = []

def check(condition: bool, message: str) -> None:
    global checks
    checks += 1
    if not condition:
        errors.append(message)

policy = yaml.safe_load((ROOT / "orchestrator" / "application-management-policy.yaml").read_text(encoding="utf-8"))
check(policy["portable_manifest"]["absolute_paths"] == "deny", "portable manifest must deny absolute paths")
check(policy["portable_manifest"]["source_access"] == "READ_ONLY", "portable manifest must lock source access")
check(policy["local_workspace_map"]["gitignored"] == "required", "workspace.local.yaml must be ignored")
check(policy["resolution"]["mapped_path_must_be_git_root"] == "required", "mapped paths must be git roots")
check(policy["resolution"]["duplicate_git_roots"] == "deny", "duplicate roots must be denied")
check(policy["resolution"]["nested_git_roots"] == "deny", "nested roots must be denied")
check(policy["resolution"]["remote_identity_mismatch"] == "deny", "identity mismatch must be denied")
check(policy["security"]["credential_bearing_remote_urls"] == "deny", "credential-bearing remotes must be denied")
check(policy["security"]["source_repository_mutation"] == "deny", "source mutation must be denied")

contracts = (ROOT / "runtime" / "tu_runtime" / "core" / "contracts.py").read_text(encoding="utf-8")
for name in ("application-manifest", "workspace-map", "workspace-resolution", "application-validation-report"):
    check(f'"{name}"' in contracts, f"Contract validator must register {name}")

cli = (ROOT / "runtime" / "tu_runtime" / "cli.py").read_text(encoding="utf-8")
for command in (
    "application-init", "application-show", "application-validate", "repository-add",
    "repository-remove", "workspace-bind", "workspace-unbind", "workspace-resolve",
):
    check(command in cli, f"CLI command is missing: {command}")

application = (ROOT / "runtime" / "tu_runtime" / "core" / "application.py").read_text(encoding="utf-8")
for invariant in (
    "GIT_OPTIONAL_LOCKS", "READ_ONLY", "APP-BOUNDARY-001", "APP-BOUNDARY-002",
    "APP-BOUNDARY-003", "APP-BOUNDARY-004", "APP-IDENTITY-004", "workspace-resolution.yaml",
):
    check(invariant in application, f"Application runtime invariant is missing: {invariant}")
check("git commit" not in application and "git add" not in application and "git checkout" not in application, "Application runtime must not contain Git mutation commands")

manifest_schema = json.loads((ROOT / "schemas" / "application-manifest.schema.json").read_text(encoding="utf-8"))
repo_properties = manifest_schema["properties"]["repositories"]["items"]["properties"]
check(repo_properties["source_access"].get("const") == "READ_ONLY", "Manifest schema must enforce READ_ONLY")
check("path" not in repo_properties, "Portable repository entries must not contain local path")

workspace_schema = json.loads((ROOT / "schemas" / "workspace-map.schema.json").read_text(encoding="utf-8"))
check("path" in workspace_schema["properties"]["repositories"]["additionalProperties"]["properties"], "Workspace map must contain local paths")

report = {"status": "PASS" if not errors else "FAIL", "checks": checks, "errors": errors}
Path(args.report).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
raise SystemExit(0 if not errors else 1)
