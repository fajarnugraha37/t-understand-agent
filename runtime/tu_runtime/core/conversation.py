from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .analysis import AnalysisManager
from .application import ApplicationManager, default_machine_id
from .contracts import ContractValidator
from .discovery import AdapterManager, DiscoveryManager
from .documentation import DocumentationManager
from .errors import TUnderstandError
from .graph import GraphManager
from .io import atomic_write_text, atomic_write_yaml, load_yaml, utc_now
from .memory import MemoryManager
from .modeling import ModelManager
from .snapshot import SnapshotManager
from .workspace_discovery import (
    WorkspaceDiscovery,
    discover_git_roots,
    find_existing_application_root,
    git_root,
    resolve_workspace,
    write_workspace_discovery,
)


DIRECT_INTENTS = {"GREETING", "HELP", "CAPABILITY_DETAILS"}
FORBIDDEN_LEAKAGE = (
    "ContextRoot",
    "$TU",
    "Thought:",
    "# Todos",
    "Let me summarize the key findings for the user",
)


def _slug(value: str, fallback: str = "application") -> str:
    candidate = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not candidate or not candidate[0].isalpha():
        candidate = f"app-{candidate}" if candidate else fallback
    if len(candidate) < 2:
        candidate += "-app"
    return candidate[:63].rstrip("-")


def _git(workspace: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(workspace), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"},
    )


def active_workspace_root() -> Path:
    override = os.environ.get("T_UNDERSTAND_WORKSPACE")
    if override:
        return Path(override).expanduser().resolve()
    current = Path.cwd().resolve()
    existing = find_existing_application_root(current)
    if existing:
        return existing
    root = git_root(current)
    return root if root else current


def context_root_for(workspace: Path) -> Path:
    override = os.environ.get("T_UNDERSTAND_CONTEXT_ROOT")
    return Path(override).expanduser().resolve() if override else workspace / ".t-understand"


def bootstrap_workspace(
    project_root: Path,
    workspace: Path,
    context_root: Path,
    prompt: str = "",
    discovery: WorkspaceDiscovery | None = None,
) -> dict[str, Any]:
    manager = ApplicationManager(project_root, context_root)
    if manager.manifest_path.exists():
        resolution = manager.resolve()
        return {
            "status": "READY",
            "workspace_root": str(workspace),
            "managed_state": str(context_root),
            "application_id": resolution["application_id"],
            "workspace_model": resolution["workspace_model"],
            "repositories": len(resolution["repositories"]),
        }
    discovered = discovery or resolve_workspace(workspace, prompt)
    app_id = _slug(discovered.workspace_root.name)
    manager.initialize(
        app_id,
        discovered.workspace_root.name,
        discovered.workspace_model,
        default_machine_id(),
        "Auto-managed by the t-understand agent from the active application workspace",
    )
    for candidate in discovered.repositories:
        kwargs: dict[str, Any]
        if candidate.identity_kind == "remote" and candidate.remote:
            kwargs = {"remote": candidate.remote}
        else:
            kwargs = {"identity_key": candidate.identity_value}
        try:
            manager.add_repository(
                candidate.repository_id,
                candidate.name,
                candidate.role,
                default_ref=None,
                tags=["auto-discovered", candidate.role],
                **kwargs,
            )
        except TUnderstandError as exc:
            if candidate.identity_kind != "remote" or exc.code not in {"APP-REMOTE-001", "APP-REMOTE-002", "APP-REMOTE-003", "APP-REMOTE-004", "APP-REMOTE-005", "APP-REMOTE-006"}:
                raise
            manager.add_repository(
                candidate.repository_id,
                candidate.name,
                candidate.role,
                default_ref=None,
                tags=["auto-discovered", candidate.role],
                identity_key=f"local-{candidate.repository_id}-{hashlib.sha256(candidate.identity_value.encode()).hexdigest()[:20]}",
            )
        manager.bind_repository(candidate.repository_id, candidate.path)
    write_workspace_discovery(context_root, discovered)
    ContractValidator(project_root).validate("agent-workspace-discovery", discovered.as_dict())
    resolution = manager.resolve()
    return {
        "status": "INITIALIZED",
        "workspace_root": str(discovered.workspace_root),
        "managed_state": str(context_root),
        "application_id": resolution["application_id"],
        "workspace_model": resolution["workspace_model"],
        "repositories": len(resolution["repositories"]),
    }


class AgentConversationManager:
    def __init__(self, project_root: Path, workspace: Path | None = None, context_root: Path | None = None):
        self.project_root = project_root
        self._explicit_workspace = workspace is not None
        self._explicit_context_root = context_root is not None or bool(os.environ.get("T_UNDERSTAND_CONTEXT_ROOT"))
        self.workspace = (workspace or active_workspace_root()).resolve()
        self.context_root = (context_root or context_root_for(self.workspace)).resolve()
        self.contracts = ContractValidator(project_root)
        self.catalog = load_yaml(project_root / "orchestrator" / "capabilities.yaml")
        self.contracts.validate("capability-catalog", self.catalog)

    def _prepare_workspace_scope(self, prompt: str) -> WorkspaceDiscovery:
        discovery = resolve_workspace(self.workspace, prompt)
        if not self._explicit_context_root:
            self.workspace = discovery.workspace_root
            self.context_root = context_root_for(self.workspace).resolve()
        elif discovery.workspace_root != self.workspace and self._explicit_workspace:
            # Explicit callers control storage but can still request sibling discovery.
            self.workspace = discovery.workspace_root
        return discovery

    @property
    def plans_root(self) -> Path:
        return self.context_root / "agent" / "plans"

    @property
    def runs_root(self) -> Path:
        return self.context_root / "agent" / "runs"

    def workspace_status(self) -> dict[str, Any]:
        known = (self.context_root / "application.yaml").exists()
        roots: list[Path] = []
        current = git_root(self.workspace)
        if current:
            roots = [current]
        elif self.workspace.is_dir():
            # Greeting/help stays lightweight: only direct and one-level child Git roots.
            roots = discover_git_roots(self.workspace, max_depth=1)
        if not roots:
            return {
                "status": "NO_WORKSPACE",
                "repository_name": None,
                "repository_count": 0,
                "workspace_model": None,
                "knowledge_available": known,
                "changes_detected": False,
            }
        changes = False
        for root in roots:
            status = _git(root, "status", "--porcelain", "--untracked-files=normal")
            if any(line and not line[3:].replace("\\", "/").startswith(".t-understand/") for line in status.stdout.splitlines()):
                changes = True
                break
        return {
            "status": "KNOWN_REPOSITORY" if known else "NEW_REPOSITORY",
            "repository_name": self.workspace.name,
            "repository_count": len(roots),
            "workspace_model": "single-repo" if len(roots) == 1 else "multi-repo",
            "knowledge_available": known,
            "changes_detected": changes,
        }

    @staticmethod
    def _normalize(prompt: str) -> str:
        return " ".join(prompt.lower().strip().split()).strip(".!? ")

    def classify(self, prompt: str) -> str:
        normalized = self._normalize(prompt)
        interaction = self.catalog["interaction"]
        intents = self.catalog["intents"]
        has_doc_verb = any(re.search(rf"\b{re.escape(v)}\b", normalized) for v in intents["documentation_verbs"])
        has_doc_noun = any(noun in normalized for noun in intents["documentation_nouns"])
        if has_doc_verb and has_doc_noun:
            return "DOCUMENTATION_GENERATION"
        if any(phrase in normalized for phrase in intents["review_verbs"]):
            return "CODE_REVIEW"
        if normalized in interaction["details_phrases"]:
            return "CAPABILITY_DETAILS"
        if normalized in interaction["help_phrases"]:
            return "HELP"
        if normalized in interaction["greeting_only"]:
            return "GREETING"
        question_markers = ("where ", "what ", "which ", "who ", "when ", "why ", "how ", "apa ", "di mana", "kenapa", "bagaimana")
        if normalized.endswith("?") or normalized.startswith(question_markers):
            return "QUESTION_ANSWERING"
        return "EXPLANATION"

    def _capability_lines(self, detailed: bool = False) -> list[str]:
        caps = self.catalog["capabilities"]
        selected = caps if detailed else caps[:7]
        return [f"- {item['title']}" for item in selected]

    def _direct_response(self, intent: str, status: dict[str, Any]) -> str:
        repo = status["repository_name"]
        if intent == "GREETING":
            if status["status"] == "NO_WORKSPACE":
                opening = "Hi! I’m t-understand. Open a repository and ask what you want to understand."
            elif status["status"] == "NEW_REPOSITORY":
                opening = f"Hi! I detected the {repo} repository. I can analyze it when you give me a task."
            else:
                opening = f"Hi! Existing repository knowledge is available for {repo}."
            examples = [
                '“Explain how this repository works.”',
                '“Review my current changes against HEAD.”',
                '“Generate comprehensive repository documentation.”',
            ]
            return "\n".join([opening, "", "Capabilities:", *self._capability_lines(), "", "Examples:", *[f"- {x}" for x in examples]])
        if intent == "HELP":
            return "\n".join(["I can help with these repository outcomes:", *self._capability_lines(detailed=True), "", "Application source remains read-only; Git is inspection-only."])
        return "\n".join(["Available t-understand capabilities:", *self._capability_lines(detailed=True), "", "Limitations:", *[f"- {x}" for x in self.catalog["limitations"]]])

    def plan(self, prompt: str) -> dict[str, Any]:
        intent = self.classify(prompt)
        discovery: WorkspaceDiscovery | None = None
        if intent not in DIRECT_INTENTS:
            discovery = self._prepare_workspace_scope(prompt)
        status = self.workspace_status()
        artifact_required = intent == "DOCUMENTATION_GENERATION"
        response_mode = "DIRECT" if intent in DIRECT_INTENTS else "SUMMARY_ONLY" if artifact_required else "CONVERSATIONAL"
        required_action = {
            "GREETING": "return-capability-greeting",
            "HELP": "return-capability-help",
            "CAPABILITY_DETAILS": "return-capability-details",
            "DOCUMENTATION_GENERATION": "run-agent-documentation-workflow",
            "CODE_REVIEW": "run-review-workflow",
            "QUESTION_ANSWERING": "run-source-grounded-qna",
            "EXPLANATION": "run-source-grounded-explanation",
        }[intent]
        required_artifacts = []
        if artifact_required:
            required_artifacts = [
                ".t-understand/output/documentation/latest/_meta/manifest.yaml",
                ".t-understand/output/documentation/latest/_meta/document-plan.yaml",
                ".t-understand/output/documentation/latest/_meta/coverage-ledger.yaml",
                ".t-understand/output/documentation/latest/_meta/traceability.jsonl",
                ".t-understand/output/documentation/latest/_meta/validation.yaml",
                ".t-understand/output/documentation/latest/index.md",
            ]
        base: dict[str, Any] = {
            "schema_id": "https://t-understand.dev/schemas/agent-operation-plan.schema.json",
            "schema_version": "1.0.0",
            "intent": intent,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "workspace": status,
            "response_mode": response_mode,
            "artifact_required": artifact_required,
            "required_action": required_action,
            "completion_contract": {
                "required_artifacts": required_artifacts,
                "chat_only_completion": "forbidden" if artifact_required else "allowed",
                "max_chat_characters": 4000 if artifact_required else 12000,
                "forbidden_leakage": list(FORBIDDEN_LEAKAGE),
            },
            "created_at": utc_now(),
        }
        if intent in DIRECT_INTENTS:
            base["direct_response"] = self._direct_response(intent, status)
            self.contracts.validate("agent-operation-plan", base)
            return base
        bootstrap = bootstrap_workspace(self.project_root, self.workspace, self.context_root, prompt, discovery)
        base["workspace"] = {**status, "workspace_model": bootstrap["workspace_model"], "repository_count": bootstrap["repositories"]}
        plan_id = f"PLAN-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{base['prompt_sha256'][:8].upper()}-{uuid.uuid4().hex[:4].upper()}"
        base["plan_id"] = plan_id
        self.contracts.validate("agent-operation-plan", base)
        self.plans_root.mkdir(parents=True, exist_ok=True)
        atomic_write_yaml(self.plans_root / f"{plan_id}.yaml", base)
        return base

    @staticmethod
    def _suffix(prompt: str) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{stamp}-{hashlib.sha256((prompt + uuid.uuid4().hex).encode()).hexdigest()[:8].upper()}"

    def generate_documentation(self, prompt: str) -> dict[str, Any]:
        plan = self.plan(prompt)
        if plan["intent"] != "DOCUMENTATION_GENERATION":
            raise TUnderstandError("AGENT-INTENT-001", "The prompt does not request documentation artifact generation")
        suffix = self._suffix(prompt)
        ids = {
            "snapshot": f"SNAP-DOC-{suffix}",
            "discovery": f"DISC-DOC-{suffix}",
            "extraction": f"EXT-DOC-{suffix}",
            "analysis": f"ANL-DOC-{suffix}",
            "graph": f"GRAPH-DOC-{suffix}",
            "memory": f"MEM-DOC-{suffix}",
            "model": f"MODEL-DOC-{suffix}",
            "docset": f"DOCS-{suffix}",
            "run": f"RUN-DOC-{suffix}",
        }
        application = ApplicationManager(self.project_root, self.context_root)
        resolution = application.resolve()
        targets = {item["repository_id"]: {"type": "worktree", "ref": None} for item in resolution["repositories"]}
        snapshots = SnapshotManager(self.project_root, self.context_root)
        discovery = DiscoveryManager(self.project_root, self.context_root)
        adapters = AdapterManager(self.project_root, self.context_root)
        analysis = AnalysisManager(self.project_root, self.context_root)
        graph = GraphManager(self.project_root, self.context_root)
        memory = MemoryManager(self.project_root, self.context_root)
        models = ModelManager(self.project_root, self.context_root)
        docs = DocumentationManager(self.project_root, self.context_root)

        snapshots.create_snapshot(ids["snapshot"], targets, "documentation")
        discovery.create(ids["discovery"], ids["snapshot"])
        adapters.run(ids["extraction"], ids["discovery"])
        analysis.run(ids["analysis"], ids["extraction"], [])
        graph.create(ids["graph"], ids["analysis"])
        memory.build(ids["memory"], ids["graph"])
        models.build(ids["model"], ids["memory"])
        manifest = docs.generate(ids["docset"], ids["model"])
        verification = docs.validate(ids["docset"])
        critique = docs.critique(ids["docset"])
        user_view = docs.validate_user_view()
        if any(item["status"] != "PASS" for item in (verification, critique, user_view)):
            raise TUnderstandError("AGENT-DOC-VERIFY-001", "Documentation artifacts failed final validation")
        relative_output = ".t-understand/output/documentation/latest/"
        coverage_ledger = load_yaml(self.context_root / "documentation" / "canonical" / ids["docset"] / "coverage-ledger.yaml")
        coverage = coverage_ledger["coverage"]
        workspace_model = resolution["workspace_model"]
        repository_count = len(resolution["repositories"])
        chat_response = "\n".join(
            [
                "Documentation generated successfully.",
                "",
                f"Workspace: {workspace_model} ({repository_count} repositories).",
                f"Created {len(manifest['documents'])} documentation files under:",
                relative_output,
                "",
                "Main entry point:",
                f"{relative_output}index.md",
                "",
                f"Coverage: requirements {coverage_ledger['requirement_coverage'] * 100:.1f}%, model records {coverage * 100:.1f}%, repositories {coverage_ledger['repository_coverage'] * 100:.1f}%, flows {coverage_ledger['flow_coverage'] * 100:.1f}%.",
                "Unknown or weakly evidenced business/domain areas remain explicitly marked instead of being invented.",
                "Build, unit tests, and integration tests were not executed during this documentation run; no pass claim is made for them.",
                "Application source files and Git state were not modified.",
            ]
        )
        completion = {
            "schema_id": "https://t-understand.dev/schemas/agent-completion.schema.json",
            "schema_version": "1.0.0",
            "run_id": ids["run"],
            "intent": "DOCUMENTATION_GENERATION",
            "status": "PASS",
            "workspace_root": str(self.workspace),
            "output_path": relative_output,
            "documents": len(manifest["documents"]),
            "coverage": coverage,
            "workspace_model": workspace_model,
            "repositories": repository_count,
            "quality": {
                "requirement_coverage": coverage_ledger["requirement_coverage"],
                "model_record_coverage": coverage_ledger["coverage"],
                "required_section_coverage": coverage_ledger["section_coverage"],
                "repository_coverage": coverage_ledger["repository_coverage"],
                "flow_coverage": coverage_ledger["flow_coverage"],
            },
            "verification": {"documentation": "PASS", "critique": "PASS", "user_view": "PASS"},
            "execution_claims": {"build": "NOT_EXECUTED", "unit_tests": "NOT_EXECUTED", "integration_tests": "NOT_EXECUTED"},
            "chat_response": chat_response,
            "completed_at": utc_now(),
        }
        self.contracts.validate("agent-completion", completion)
        self.runs_root.mkdir(parents=True, exist_ok=True)
        atomic_write_yaml(self.runs_root / f"{ids['run']}.yaml", completion)
        return completion

    def validate_response(self, prompt: str, response: str) -> dict[str, Any]:
        intent = self.classify(prompt)
        errors: list[str] = []
        max_chars = 4000 if intent == "DOCUMENTATION_GENERATION" else 12000
        if len(response) > max_chars:
            errors.append(f"response exceeds {max_chars} characters")
        for token in FORBIDDEN_LEAKAGE:
            if token.lower() in response.lower():
                errors.append(f"forbidden internal leakage: {token}")
        if re.search(r"\b(?:SNAP|DISC|EXT|ANL|GRAPH|MEM|MODEL|DOCS|RUN)-[A-Z0-9_-]+", response):
            errors.append("internal artifact identifier leaked")
        if intent == "DOCUMENTATION_GENERATION":
            view = DocumentationManager(self.project_root, self.context_root).validate_user_view()
            if view["status"] != "PASS":
                errors.append("documentation artifact view is missing or invalid")
            if len(response.splitlines()) > 80:
                errors.append("documentation body appears to be dumped into chat")
            forbidden_claims = ("all tests pass", "make verify —", "integration tests pass", "read every source file")
            for claim in forbidden_claims:
                if claim in response.lower():
                    errors.append(f"unverified execution/completeness claim: {claim}")
        return {"status": "PASS" if not errors else "FAIL", "intent": intent, "checks": 5, "errors": errors}
