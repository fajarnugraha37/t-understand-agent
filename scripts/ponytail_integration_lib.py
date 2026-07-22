from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
LADDER_IDS = [
    "no-change",
    "no-application-code",
    "platform-native",
    "existing-repository-solution",
    "configuration-data-composition",
    "localized-code",
    "existing-abstraction",
    "new-abstraction",
    "new-dependency",
]
AGENTS = {
    "t-understand",
    "tu-discoverer",
    "tu-analyzer",
    "tu-modeler",
    "tu-reviewer",
    "tu-verifier",
    "tu-technical-writer",
    "tu-business-writer",
    "tu-answerer",
    "tu-critic",
    "tu-memory-curator",
}
ADAPTER_FILES = {
    "adapters/opencode/AGENTS.md",
    "adapters/claude-code/CLAUDE.md",
    "adapters/codex/TU-UNDERSTAND.md",
    "adapters/codex/tu-understand/SKILL.md",
    "adapters/cursor/t-understand.mdc",
}
CODEX_ROLE_FILES = {
    f"adapters/codex/tu-understand/references/agents/{agent}.md" for agent in AGENTS
}
PONYTAIL_TEXT_FILES = {
    "orchestrator/ponytail-engineering-policy.yaml",
    "skills/foundation/tu-ponytail-engineering/SKILL.md",
    "docs/ponytail-first-engineering.md",
    "examples/ponytail-context.yaml",
    *ADAPTER_FILES,
    *CODEX_ROLE_FILES,
    *(f"agents/{agent}/AGENT.md" for agent in AGENTS),
}


def load_yaml(path: str) -> Any:
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def example_packet() -> dict[str, Any]:
    return {
        "schema_id": "https://t-understand.dev/schemas/delegation-packet.schema.json",
        "schema_version": "1.2.0",
        "invocation_id": "INV-" + "A" * 32,
        "parent_agent": "t-understand",
        "target_agent": "tu-modeler",
        "delegation_depth": 1,
        "workflow": "foundation",
        "state": "SYSTEM_MODELING",
        "state_version": 1,
        "skill": "tu-system-modeling",
        "objective": "Plan the smallest complete change from bounded revision evidence.",
        "application_id": "example-app",
        "application_snapshot": "SNAP-EXAMPLE",
        "permissions": {
            "source_repository_read": "allow",
            "source_repository_write": "deny",
            "git_mutation": "deny",
            "delegate": "deny",
            "artifact_write_domains": ["models"],
        },
        "inputs": [],
        "outputs": [
            {
                "artifact_type": "system-model",
                "path": "artifacts/system-model/INV-"
                + "A" * 32
                + "-system-model.yaml",
            }
        ],
        "stop_conditions": ["Required evidence is missing or stale."],
        "context_budget": {
            "strategy": "evidence-slices",
            "one_primary_objective": True,
            "max_workers": 1,
        },
        "issued_at": "2026-07-22T00:00:00Z",
    }


def audit() -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    checks = 0

    def check(condition: bool, code: str, message: str, path: str = "") -> None:
        nonlocal checks
        checks += 1
        if not condition:
            errors.append({"code": code, "message": message, "path": path})

    policy = load_yaml("orchestrator/ponytail-engineering-policy.yaml")
    check(policy["contract"]["id"] == "TU-PONYTAIL-ENGINEERING-POLICY", "PONY-POLICY-001", "canonical policy ID missing")
    check(policy.get("strategy") == "smallest-complete-solution", "PONY-POLICY-002", "smallest-complete-solution strategy missing")
    check("correct" in policy.get("invariant", "").lower(), "PONY-POLICY-003", "correctness invariant missing")
    check(policy["external_integration"].get("required") is False, "PONY-OPTIONAL-001", "external Ponytail integration must be optional")
    check(policy["external_integration"].get("automatically_install") is False, "PONY-AUTO-001", "Ponytail auto-install must be false")
    check(policy["external_integration"].get("automatically_upgrade") is False, "PONY-AUTO-002", "Ponytail auto-upgrade must be false")
    check(policy["external_integration"].get("invent_commands_or_files") is False, "PONY-AUTO-003", "Ponytail commands or files must not be invented")
    ladder = policy.get("decision_ladder", [])
    check([item.get("id") for item in ladder] == LADDER_IDS, "PONY-LADDER-001", "decision ladder order differs")
    check(len(policy.get("precedence", [])) >= 10, "PONY-SAFETY-001", "safety precedence is incomplete")
    check("small_task_path" in policy and "structured_path" in policy, "PONY-SMALL-001", "lightweight and structured paths are both required")
    check(len(policy.get("abstraction_admission", {}).get("require_at_least_one", [])) >= 8, "PONY-ABSTRACTION-001", "abstraction admission criteria incomplete")
    check(len(policy.get("dependency_admission", {}).get("record", [])) >= 9, "PONY-DEPENDENCY-001", "dependency admission record incomplete")
    check(policy.get("permissions", {}).get("expand_for_ponytail") is False, "PONY-PERM-001", "Ponytail must not expand permissions")

    registry = load_yaml("orchestrator/skill-registry.yaml")["skills"]
    matches = [item for item in registry if item["id"] == "tu-ponytail-engineering"]
    check(len(matches) == 1, "PONY-SKILL-001", "shared skill must be registered exactly once")
    if matches:
        check(matches[0]["owner"] == "t-understand", "PONY-SKILL-002", "orchestrator must own the initial Ponytail decision")
        check(matches[0]["status"] == "implemented", "PONY-SKILL-003", "shared skill must be implemented")
    skill_text = (ROOT / "skills/foundation/tu-ponytail-engineering/SKILL.md").read_text(encoding="utf-8")
    check("name: tu-ponytail-engineering" in skill_text, "PONY-SKILL-004", "skill frontmatter missing")
    check("external_ponytail_required: false" in skill_text, "PONY-SKILL-005", "skill must not require external Ponytail")

    schema = json.loads((ROOT / "schemas/delegation-packet.schema.json").read_text(encoding="utf-8"))
    check("ponytail_context" in schema["properties"], "PONY-DELEGATION-001", "delegation field missing")
    check("ponytail_context" not in schema["required"], "PONY-DELEGATION-002", "delegation field must remain optional")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    old_packet = example_packet()
    check(not list(validator.iter_errors(old_packet)), "PONY-DELEGATION-003", "legacy packet without Ponytail context must remain valid")
    new_packet = deepcopy(old_packet)
    new_packet["ponytail_context"] = load_yaml("examples/ponytail-context.yaml")
    check(not list(validator.iter_errors(new_packet)), "PONY-DELEGATION-004", "packet with Ponytail context must validate")
    invalid_packet = deepcopy(new_packet)
    invalid_packet["ponytail_context"].pop("selected_solution")
    check(bool(list(validator.iter_errors(invalid_packet))), "PONY-DELEGATION-005", "incomplete Ponytail context must fail")

    permission = load_yaml("orchestrator/tool-permission-policy.yaml")
    denied = set(permission["deny"])
    check({"ponytail-installation", "ponytail-upgrade"} <= denied, "PONY-PERM-002", "Ponytail install and upgrade must be denied")
    check(permission.get("prompt_fallback") == "denied", "PONY-PERM-003", "denied Ponytail action must not become an ask prompt")

    for agent in sorted(AGENTS):
        text = (ROOT / "agents" / agent / "AGENT.md").read_text(encoding="utf-8")
        check("Ponytail-first" in text, "PONY-AGENT-001", "agent lacks Ponytail behavior", agent)
        check("source_repository_write" in text or "application_source_write" in text, "PONY-AGENT-002", "agent authority boundary missing", agent)
    root_text = (ROOT / "agents/t-understand/AGENT.md").read_text(encoding="utf-8")
    for required in (
        "separate it from the implementation assumed",
        "Use a lightweight path",
        "Delegate that context once",
        "review for both over-engineering and unsafe minimalism",
    ):
        check(required in root_text, "PONY-ORCH-001", f"root orchestrator lacks: {required}")

    for path in sorted(ADAPTER_FILES):
        text = (ROOT / path).read_text(encoding="utf-8")
        check("ponytail-engineering-policy.yaml" in text, "PONY-ADAPTER-001", "platform adapter is not aligned", path)
        check("optional" in text.lower(), "PONY-ADAPTER-002", "platform adapter must keep external Ponytail optional", path)

    for path in sorted(CODEX_ROLE_FILES):
        text = (ROOT / path).read_text(encoding="utf-8")
        check("Ponytail-first" in text, "PONY-CODEX-ROLE-001", "Codex role reference is stale", path)

    installation = (ROOT / "runtime/tu_runtime/core/installation.py").read_text(encoding="utf-8")
    check('"orchestrator"' in installation and 'rglob("SKILL.md")' in installation, "PONY-INSTALL-001", "installer must package canonical policy and skill automatically")

    command_pattern = re.compile(r"`/?ponytail(?:-[a-z]+)?(?:\s+[^`]*)?`", re.IGNORECASE)
    for path in sorted(PONYTAIL_TEXT_FILES):
        text = (ROOT / path).read_text(encoding="utf-8")
        for match in command_pattern.finditer(text):
            token = match.group(0)
            check(token in {"`ponytail_context`"}, "PONY-COMMAND-001", f"unsupported Ponytail command or file reference: {token}", path)

    docs = (ROOT / "docs/ponytail-first-engineering.md").read_text(encoding="utf-8")
    for required in (
        "Example: no custom component required",
        "Example: localized code is justified",
        "Bad minimalism",
        "Bad abstraction avoidance",
        "Ponytail + SRP",
        "Ponytail + YAGNI",
    ):
        check(required in docs, "PONY-DOC-001", f"documentation lacks: {required}")

    return {"status": "PASS" if not errors else "FAIL", "checks": checks, "errors": errors}
