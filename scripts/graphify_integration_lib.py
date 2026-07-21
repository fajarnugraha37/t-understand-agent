from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
STATUSES = {"available", "unavailable", "not_needed", "failed", "possibly_stale"}
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
GRAPHIFY_TEXT_FILES = {
    "orchestrator/repository-intelligence-policy.yaml",
    "skills/discovery/tu-repository-intelligence/SKILL.md",
    "docs/graphify-first-repository-intelligence.md",
    "examples/repository-intelligence.yaml",
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
        "target_agent": "tu-discoverer",
        "delegation_depth": 1,
        "workflow": "foundation",
        "state": "REPOSITORY_DISCOVERY",
        "state_version": 1,
        "skill": "tu-repository-discovery",
        "objective": "Discover repository structure from bounded revision evidence.",
        "application_id": "example-app",
        "application_snapshot": "SNAP-EXAMPLE",
        "permissions": {
            "source_repository_read": "allow",
            "source_repository_write": "deny",
            "git_mutation": "deny",
            "delegate": "deny",
            "artifact_write_domains": ["discovery"],
        },
        "inputs": [],
        "outputs": [
            {
                "artifact_type": "application-discovery",
                "path": "artifacts/application-discovery/INV-"
                + "A" * 32
                + "-application-discovery.yaml",
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

    policy = load_yaml("orchestrator/repository-intelligence-policy.yaml")
    check(policy["contract"]["id"] == "TU-REPOSITORY-INTELLIGENCE-POLICY", "GRF-POLICY-001", "canonical policy ID missing")
    check(policy.get("strategy") == "graphify-first-when-usable", "GRF-POLICY-002", "Graphify-first strategy missing")
    check(set(policy["availability"]["statuses"]) == STATUSES, "GRF-POLICY-003", "availability statuses differ")
    check(policy["availability"].get("graph_path") == "never hardcode; use only the locally documented integration", "GRF-POLICY-004", "graph path must not be hardcoded")
    check(policy["failure_behavior"][0] == "Do not stop the task.", "GRF-POLICY-005", "failure must be fail-open")
    for field in (
        "automatically_install",
        "automatically_upgrade",
        "automatically_initialize",
        "automatically_generate_graph",
        "automatically_rebuild_graph",
        "automatically_update_graph",
    ):
        check(policy["query_policy"].get(field) is False, "GRF-AUTO-001", f"{field} must be false", field)

    registry = load_yaml("orchestrator/skill-registry.yaml")["skills"]
    matches = [item for item in registry if item["id"] == "tu-repository-intelligence"]
    check(len(matches) == 1, "GRF-SKILL-001", "shared skill must be registered exactly once")
    if matches:
        check(matches[0]["owner"] == "t-understand", "GRF-SKILL-002", "orchestrator must own initial repository intelligence")
        check(matches[0]["status"] == "implemented", "GRF-SKILL-003", "shared skill must be implemented")
    skill_text = (ROOT / "skills/discovery/tu-repository-intelligence/SKILL.md").read_text(encoding="utf-8")
    check("name: tu-repository-intelligence" in skill_text, "GRF-SKILL-004", "skill frontmatter missing")
    check("Never invent a Graphify command or graph path." in skill_text, "GRF-SKILL-005", "skill must deny invented commands")

    schema = json.loads((ROOT / "schemas/delegation-packet.schema.json").read_text(encoding="utf-8"))
    check("repository_intelligence" in schema["properties"], "GRF-DELEGATION-001", "delegation field missing")
    check("repository_intelligence" not in schema["required"], "GRF-DELEGATION-002", "delegation field must stay optional")
    statuses = set(schema["properties"]["repository_intelligence"]["properties"]["graphify_status"]["enum"])
    check(statuses == STATUSES, "GRF-DELEGATION-003", "delegation statuses differ")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    old_packet = example_packet()
    check(not list(validator.iter_errors(old_packet)), "GRF-DELEGATION-004", "legacy packet without repository intelligence must remain valid")
    new_packet = deepcopy(old_packet)
    new_packet["repository_intelligence"] = load_yaml("examples/repository-intelligence.yaml")
    check(not list(validator.iter_errors(new_packet)), "GRF-DELEGATION-005", "packet with repository intelligence must validate")
    invalid_packet = deepcopy(new_packet)
    invalid_packet["repository_intelligence"]["graphify_status"] = "required"
    check(bool(list(validator.iter_errors(invalid_packet))), "GRF-DELEGATION-006", "invalid Graphify status must fail")

    permission = load_yaml("orchestrator/tool-permission-policy.yaml")
    allowed = set(permission["allowed_local_capabilities"])
    denied = set(permission["deny"])
    check({"graphify-availability-check", "graphify-read-only-query"} <= allowed, "GRF-PERM-001", "read-only Graphify capabilities missing")
    check({"graphify-installation", "graphify-upgrade", "graphify-initialization", "graphify-graph-generation", "graphify-graph-mutation", "graphify-graph-update", "graphify-graph-rebuild"} <= denied, "GRF-PERM-002", "Graphify mutation denials incomplete")
    check(permission.get("prompt_fallback") == "denied", "GRF-PERM-003", "denied Graphify action must not become an ask prompt")

    for agent in sorted(AGENTS):
        text = (ROOT / "agents" / agent / "AGENT.md").read_text(encoding="utf-8")
        check("Repository intelligence" in text or "Repository-intelligence contract" in text, "GRF-AGENT-001", "agent lacks repository-intelligence behavior", agent)
    root_text = (ROOT / "agents/t-understand/AGENT.md").read_text(encoding="utf-8")
    check("quietly evaluate Graphify once" in root_text, "GRF-ORCH-001", "orchestrator must own initial quiet evaluation")
    check("Delegate that package once" in root_text, "GRF-ORCH-002", "orchestrator must prevent duplicated discovery")

    for path in sorted(ADAPTER_FILES):
        text = (ROOT / path).read_text(encoding="utf-8")
        check("repository-intelligence-policy.yaml" in text or "canonical repository-intelligence policy" in text, "GRF-ADAPTER-001", "platform adapter is not aligned", path)
        check("fail-open" in text or "never blocks" in text, "GRF-ADAPTER-002", "platform adapter lacks fail-open semantics", path)

    for path in sorted(CODEX_ROLE_FILES):
        text = (ROOT / path).read_text(encoding="utf-8")
        check("Repository intelligence" in text, "GRF-CODEX-ROLE-001", "Codex role reference is stale", path)

    installation = (ROOT / "runtime/tu_runtime/core/installation.py").read_text(encoding="utf-8")
    check('"orchestrator"' in installation and 'rglob("SKILL.md")' in installation, "GRF-INSTALL-001", "installer must package canonical policy and skill automatically")

    command_pattern = re.compile(r"`graphify\s+([^`\s]+)(?:[^`]*)`", re.IGNORECASE)
    for path in sorted(GRAPHIFY_TEXT_FILES):
        text = (ROOT / path).read_text(encoding="utf-8")
        for match in command_pattern.finditer(text):
            token = match.group(1).rstrip(".,;:)")
            check(token == "--help", "GRF-COMMAND-001", f"undocumented Graphify command token: {token}", path)

    check((ROOT / "docs/graphify-first-repository-intelligence.md").is_file(), "GRF-DOC-001", "Graphify documentation missing")
    return {"status": "PASS" if not errors else "FAIL", "checks": checks, "errors": errors}
