from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path

from .core.application import ApplicationManager, default_machine_id
from .core.engine import LifecycleEngine
from .core.discovery import AdapterManager, DiscoveryManager
from .core.analysis import AnalysisManager
from .core.graph import GraphManager
from .core.memory import MemoryManager
from .core.modeling import ModelManager
from .core.documentation import DocumentationManager
from .core.exporting import ExportManager, PROFILES
from .core.qna import QnAManager
from .core.reviewing import ReviewManager, ReviewExportManager, PROFILES as REVIEW_PROFILES, EXPORT_PROFILES as REVIEW_EXPORT_PROFILES
from .core.quality import QualityManager
from .core.qualification import QualificationManager, PROFILES as QUALIFICATION_PROFILES, RUNNERS as QUALIFICATION_RUNNERS
from .core.installation import InstallationManager, PLATFORMS
from .core.integration import IntegrationManager
from .core.release import ReleaseManager
from .core.errors import TUnderstandError
from .core.io import load_yaml
from .core.snapshot import SnapshotManager, parse_target_assignments
from .core.conversation import AgentConversationManager, active_workspace_root as conversation_workspace_root, context_root_for, bootstrap_workspace


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def active_workspace_root() -> Path:
    override = os.environ.get("T_UNDERSTAND_WORKSPACE")
    if override:
        return Path(override).expanduser().resolve()
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"},
    )
    if completed.returncode == 0 and completed.stdout.strip():
        return Path(completed.stdout.strip()).resolve()
    return Path.cwd().resolve()


def resolved_context_root(args: argparse.Namespace) -> Path:
    explicit = getattr(args, "context_root", None) or os.environ.get("T_UNDERSTAND_CONTEXT_ROOT")
    if explicit:
        return Path(explicit).expanduser().resolve()
    return active_workspace_root() / ".t-understand"


def _slug(value: str, fallback: str = "application") -> str:
    candidate = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not candidate or not candidate[0].isalpha():
        candidate = f"app-{candidate}" if candidate else fallback
    if len(candidate) < 2:
        candidate += "-app"
    return candidate[:63].rstrip("-")


def bootstrap_active_workspace(args: argparse.Namespace) -> dict[str, object]:
    workspace = active_workspace_root()
    context = resolved_context_root(args)
    manager = ApplicationManager(project_root(), context)
    if manager.manifest_path.exists():
        resolution = manager.resolve()
        return {
            "status": "READY",
            "workspace_root": str(workspace),
            "managed_state": str(context),
            "application_id": resolution["application_id"],
            "repositories": len(resolution["repositories"]),
        }
    git_check = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "--is-inside-work-tree"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"},
    )
    if git_check.returncode != 0 or git_check.stdout.strip() != "true":
        raise TUnderstandError("AGENT-WORKSPACE-001", "Run the agent from a Git working directory")
    app_id = _slug(workspace.name)
    repository_id = app_id
    manager.initialize(app_id, workspace.name, "single-repo", default_machine_id(), "Auto-managed by the t-understand agent")
    remote = subprocess.run(
        ["git", "-C", str(workspace), "remote", "get-url", "origin"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"},
    )
    remote_value = remote.stdout.strip() if remote.returncode == 0 else ""
    kwargs = {"remote": remote_value} if remote_value else {"identity_key": f"local-{app_id}"}
    manager.add_repository(repository_id, workspace.name, "application-repository", default_ref=None, tags=["auto-discovered"], **kwargs)
    manager.bind_repository(repository_id, workspace)
    resolution = manager.resolve()
    return {
        "status": "INITIALIZED",
        "workspace_root": str(workspace),
        "managed_state": str(context),
        "application_id": resolution["application_id"],
        "repositories": len(resolution["repositories"]),
    }


SNAPSHOT_COMMANDS = {
    "snapshot-create",
    "snapshot-show",
    "snapshot-list",
    "snapshot-validate",
    "snapshot-drift",
    "review-target-create",
    "review-target-show",
    "review-target-validate",
}
APPLICATION_COMMANDS = {
    "application-init",
    "application-show",
    "application-validate",
    "repository-add",
    "repository-remove",
    "workspace-bind",
    "workspace-unbind",
    "workspace-resolve",
}

KNOWLEDGE_COMMANDS = {
    "analysis-run", "analysis-refresh", "analysis-show", "analysis-list", "analysis-validate",
    "graph-create", "graph-show", "graph-list", "graph-validate",
    "memory-build", "memory-show", "memory-list", "memory-validate", "memory-critique",
    "memory-freshness", "memory-invalidate", "memory-index-rebuild", "memory-search",
}

MODELING_COMMANDS = {
    "model-build", "model-reconcile", "model-show", "model-list", "model-validate", "model-critique", "model-artifact",
}
QNA_COMMANDS = {
    "qna-ask", "qna-show", "qna-answer", "qna-list", "qna-validate", "qna-critique",
}
REVIEW_COMMANDS = {
    "review-run", "review-show", "review-list", "review-findings", "review-validate",
    "review-export-create", "review-export-show", "review-export-list", "review-export-validate", "review-export-profiles",
}
QUALITY_COMMANDS = {"quality-run", "quality-show", "quality-list", "quality-validate"}
QUALIFICATION_COMMANDS = {"qualification-run", "qualification-show", "qualification-list", "qualification-validate", "qualification-matrix"}
INSTALLATION_COMMANDS = {"platforms", "platform-package", "platform-package-show", "platform-package-validate", "platform-install", "platform-doctor", "platform-uninstall"}
FINAL_COMMANDS = {"integration-matrix", "integration-report", "release-audit", "release-show"}
DOCUMENTATION_COMMANDS = {
    "documentation-generate", "documentation-show", "documentation-list", "documentation-validate",
    "documentation-critique", "documentation-invalidate",
    "export-create", "export-show", "export-list", "export-validate", "export-profiles",
}

DISCOVERY_COMMANDS = {
    "discovery-run",
    "discovery-show",
    "discovery-list",
    "discovery-validate",
    "adapter-run",
    "adapter-show",
    "adapter-list",
    "adapter-validate",
    "adapter-capabilities",
}
AGENT_NATIVE_COMMANDS = {"agent-plan", "agent-capabilities", "agent-document", "agent-response-validate"}
NO_RUNTIME_COMMANDS = {"workflows", "agent-bootstrap", "validate-packet", "validate-result"} | AGENT_NATIVE_COMMANDS | APPLICATION_COMMANDS | SNAPSHOT_COMMANDS | DISCOVERY_COMMANDS | KNOWLEDGE_COMMANDS | MODELING_COMMANDS | DOCUMENTATION_COMMANDS | QNA_COMMANDS | REVIEW_COMMANDS | QUALITY_COMMANDS | QUALIFICATION_COMMANDS | INSTALLATION_COMMANDS | FINAL_COMMANDS


def engine(args: argparse.Namespace) -> LifecycleEngine:
    if not args.runtime_root and args.command not in NO_RUNTIME_COMMANDS:
        raise TUnderstandError(
            "CLI-RUNTIME-001",
            "--runtime-root is required for work-item commands so t-understand never writes to an implicit source-repository path",
        )
    runtime_root = Path(args.runtime_root) if args.runtime_root else project_root() / ".runtime-validation-only"
    return LifecycleEngine(project_root(), runtime_root)


def application_manager(args: argparse.Namespace) -> ApplicationManager:
    return ApplicationManager(project_root(), resolved_context_root(args))


def snapshot_manager(args: argparse.Namespace) -> SnapshotManager:
    return SnapshotManager(project_root(), resolved_context_root(args))


def discovery_manager(args: argparse.Namespace) -> DiscoveryManager:
    return DiscoveryManager(project_root(), resolved_context_root(args))


def adapter_manager(args: argparse.Namespace) -> AdapterManager:
    return AdapterManager(project_root(), resolved_context_root(args))


def analysis_manager(args: argparse.Namespace) -> AnalysisManager:
    return AnalysisManager(project_root(), resolved_context_root(args))


def graph_manager(args: argparse.Namespace) -> GraphManager:
    return GraphManager(project_root(), resolved_context_root(args))


def memory_manager(args: argparse.Namespace) -> MemoryManager:
    return MemoryManager(project_root(), resolved_context_root(args))


def model_manager(args: argparse.Namespace) -> ModelManager:
    return ModelManager(project_root(), resolved_context_root(args))


def documentation_manager(args: argparse.Namespace) -> DocumentationManager:
    return DocumentationManager(project_root(), resolved_context_root(args))


def export_manager(args: argparse.Namespace) -> ExportManager:
    return ExportManager(project_root(), resolved_context_root(args))


def qna_manager(args: argparse.Namespace) -> QnAManager:
    return QnAManager(project_root(), resolved_context_root(args))


def review_manager(args: argparse.Namespace) -> ReviewManager:
    return ReviewManager(project_root(), resolved_context_root(args))


def review_export_manager(args: argparse.Namespace) -> ReviewExportManager:
    return ReviewExportManager(project_root(), resolved_context_root(args))


def quality_manager(args: argparse.Namespace) -> QualityManager:
    return QualityManager(project_root(), resolved_context_root(args))


def qualification_manager(args: argparse.Namespace) -> QualificationManager:
    return QualificationManager(project_root(), resolved_context_root(args))


def installation_manager(args: argparse.Namespace) -> InstallationManager:
    explicit = getattr(args, "context_root", None) or os.environ.get("T_UNDERSTAND_INSTALLER_STATE")
    context = (
        Path(explicit).expanduser().resolve()
        if explicit
        else (Path.home() / ".t-understand" / "installer").resolve()
    )
    context.mkdir(parents=True, exist_ok=True)
    return InstallationManager(project_root(), context)


def emit(data: object) -> None:
    print(json.dumps(data, indent=2, sort_keys=False, ensure_ascii=False))


def parse_artifacts(values: list[str]) -> dict[str, Path]:
    parsed: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise TUnderstandError("CLI-ARTIFACT-001", "Artifact must use TYPE=PATH")
        artifact_type, path = value.split("=", 1)
        parsed[artifact_type] = Path(path)
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="t-understand", description="Deterministic t-understand runtime")
    parser.add_argument("--runtime-root", help="Explicit runtime work root for lifecycle work items")
    parser.add_argument("--context-root", help="Internal state override; normally omitted because the active workspace is auto-managed")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("workflows")
    sub.add_parser("agent-bootstrap", help="Silently prepare the active workspace for agent-native use")
    agent_plan = sub.add_parser("agent-plan", help="Private agent intent and completion planning")
    agent_plan.add_argument("--prompt", required=True)
    agent_caps = sub.add_parser("agent-capabilities", help="Private capability greeting/help renderer")
    agent_caps.add_argument("--mode", choices=["greeting", "help", "details"], default="greeting")
    agent_document = sub.add_parser("agent-document", help="Private artifact-first documentation workflow")
    agent_document.add_argument("--prompt", required=True)
    agent_response = sub.add_parser("agent-response-validate", help="Private final response contract validator")
    agent_response.add_argument("--prompt", required=True)
    agent_response.add_argument("--response-file", required=True)

    init = sub.add_parser("init")
    init.add_argument("--work-id", required=True)
    init.add_argument("--workflow", required=True)
    init.add_argument("--snapshot", required=True)
    init.add_argument("--profile", default="economy")
    init.add_argument("--application-id")

    for name in ("status", "route", "validate-work"):
        command = sub.add_parser(name)
        command.add_argument("--work-id", required=True)
        if name == "route":
            command.add_argument("--objective")

    complete = sub.add_parser("complete")
    complete.add_argument("--work-id", required=True)
    complete.add_argument("--artifact", action="append", default=[])
    complete.add_argument("--next-state")

    accept = sub.add_parser("accept-result")
    accept.add_argument("--work-id", required=True)
    accept.add_argument("--result", required=True)
    accept.add_argument("--next-state")

    approval = sub.add_parser("record-approval")
    approval.add_argument("--work-id", required=True)
    approval.add_argument("--decision", required=True, choices=["APPROVE", "REJECT", "approve", "reject"])
    approval.add_argument("--rationale", required=True)
    approval.add_argument("--loopback-target")
    approval.add_argument("--subject-sha256")

    resume = sub.add_parser("resume")
    resume.add_argument("--work-id", required=True)
    resume.add_argument("--reason", required=True)

    validate_packet = sub.add_parser("validate-packet")
    validate_packet.add_argument("path")
    validate_result = sub.add_parser("validate-result")
    validate_result.add_argument("path")

    app_init = sub.add_parser("application-init")
    app_init.add_argument("--application-id", required=True)
    app_init.add_argument("--name", required=True)
    app_init.add_argument("--workspace-model", required=True, choices=["single-repo", "monorepo", "multi-repo"])
    app_init.add_argument("--machine-id", default=default_machine_id())
    app_init.add_argument("--description", default="")

    sub.add_parser("application-show")
    app_validate = sub.add_parser("application-validate")
    app_validate.add_argument("--inspect-workspace", action="store_true")

    repo_add = sub.add_parser("repository-add")
    repo_add.add_argument("--repository-id", required=True)
    repo_add.add_argument("--name", required=True)
    repo_add.add_argument("--role", required=True)
    identity = repo_add.add_mutually_exclusive_group(required=True)
    identity.add_argument("--remote")
    identity.add_argument("--identity-key")
    repo_add.add_argument("--default-ref")
    repo_add.add_argument("--tag", action="append", default=[])

    repo_remove = sub.add_parser("repository-remove")
    repo_remove.add_argument("--repository-id", required=True)

    bind = sub.add_parser("workspace-bind")
    bind.add_argument("--repository-id", required=True)
    bind.add_argument("--path", required=True)

    unbind = sub.add_parser("workspace-unbind")
    unbind.add_argument("--repository-id", required=True)

    sub.add_parser("workspace-resolve")

    snapshot_create = sub.add_parser("snapshot-create")
    snapshot_create.add_argument("--snapshot-id", required=True)
    snapshot_create.add_argument("--purpose", default="manual", choices=["foundation", "documentation", "qna", "review", "manual"])
    snapshot_create.add_argument("--target", action="append", default=[], help="REPOSITORY_ID=TYPE[:REF]")

    snapshot_show = sub.add_parser("snapshot-show")
    snapshot_show.add_argument("--snapshot-id", required=True)
    sub.add_parser("snapshot-list")
    snapshot_validate = sub.add_parser("snapshot-validate")
    snapshot_validate.add_argument("--snapshot-id", required=True)
    snapshot_drift = sub.add_parser("snapshot-drift")
    snapshot_drift.add_argument("--snapshot-id", required=True)

    review_create = sub.add_parser("review-target-create")
    review_create.add_argument("--review-id", required=True)
    review_create.add_argument("--mode", required=True, choices=["static-audit", "diff", "STATIC_AUDIT", "DIFF"])
    review_create.add_argument("--candidate", required=True)
    review_create.add_argument("--baseline")
    review_show = sub.add_parser("review-target-show")
    review_show.add_argument("--review-id", required=True)
    review_validate = sub.add_parser("review-target-validate")
    review_validate.add_argument("--review-id", required=True)

    discovery_run = sub.add_parser("discovery-run")
    discovery_run.add_argument("--discovery-id", required=True)
    discovery_run.add_argument("--snapshot-id", required=True)
    discovery_show = sub.add_parser("discovery-show")
    discovery_show.add_argument("--discovery-id", required=True)
    sub.add_parser("discovery-list")
    discovery_validate = sub.add_parser("discovery-validate")
    discovery_validate.add_argument("--discovery-id", required=True)

    adapter_run = sub.add_parser("adapter-run")
    adapter_run.add_argument("--extraction-id", required=True)
    adapter_run.add_argument("--discovery-id", required=True)
    adapter_show = sub.add_parser("adapter-show")
    adapter_show.add_argument("--extraction-id", required=True)
    sub.add_parser("adapter-list")
    adapter_validate = sub.add_parser("adapter-validate")
    adapter_validate.add_argument("--extraction-id", required=True)
    sub.add_parser("adapter-capabilities")

    analysis_run = sub.add_parser("analysis-run")
    analysis_run.add_argument("--analysis-id", required=True)
    analysis_run.add_argument("--extraction-id", required=True)
    analysis_run.add_argument("--scope", action="append", default=[])
    analysis_refresh = sub.add_parser("analysis-refresh")
    analysis_refresh.add_argument("--analysis-id", required=True)
    analysis_refresh.add_argument("--base-analysis-id", required=True)
    analysis_refresh.add_argument("--extraction-id", required=True)
    analysis_show = sub.add_parser("analysis-show"); analysis_show.add_argument("--analysis-id", required=True)
    sub.add_parser("analysis-list")
    analysis_validate = sub.add_parser("analysis-validate"); analysis_validate.add_argument("--analysis-id", required=True)

    graph_create = sub.add_parser("graph-create"); graph_create.add_argument("--graph-id", required=True); graph_create.add_argument("--analysis-id", required=True)
    graph_show = sub.add_parser("graph-show"); graph_show.add_argument("--graph-id", required=True)
    sub.add_parser("graph-list")
    graph_validate = sub.add_parser("graph-validate"); graph_validate.add_argument("--graph-id", required=True)

    memory_build = sub.add_parser("memory-build"); memory_build.add_argument("--memory-id", required=True); memory_build.add_argument("--graph-id", required=True); memory_build.add_argument("--no-current", action="store_true")
    memory_show = sub.add_parser("memory-show"); memory_show.add_argument("--memory-id", required=True)
    sub.add_parser("memory-list")
    memory_validate = sub.add_parser("memory-validate"); memory_validate.add_argument("--memory-id", required=True)
    memory_critique = sub.add_parser("memory-critique"); memory_critique.add_argument("--memory-id", required=True)
    memory_freshness = sub.add_parser("memory-freshness"); memory_freshness.add_argument("--memory-id", required=True); memory_freshness.add_argument("--snapshot-id", required=True)
    memory_invalidate = sub.add_parser("memory-invalidate"); memory_invalidate.add_argument("--invalidation-id", required=True); memory_invalidate.add_argument("--memory-id", required=True); memory_invalidate.add_argument("--candidate-discovery-id", required=True)
    memory_rebuild = sub.add_parser("memory-index-rebuild"); memory_rebuild.add_argument("--memory-id", required=True)
    memory_search = sub.add_parser("memory-search"); memory_search.add_argument("--memory-id", required=True); memory_search.add_argument("--query", required=True); memory_search.add_argument("--limit", type=int, default=20)

    model_build = sub.add_parser("model-build"); model_build.add_argument("--model-id", required=True); model_build.add_argument("--memory-id", required=True); model_build.add_argument("--no-current", action="store_true")
    model_reconcile = sub.add_parser("model-reconcile"); model_reconcile.add_argument("--reconciliation-id", required=True); model_reconcile.add_argument("--model-id", required=True); model_reconcile.add_argument("--base-model-id", required=True); model_reconcile.add_argument("--memory-id", required=True)
    model_show = sub.add_parser("model-show"); model_show.add_argument("--model-id", required=True)
    sub.add_parser("model-list")
    model_validate = sub.add_parser("model-validate"); model_validate.add_argument("--model-id", required=True)
    model_critique = sub.add_parser("model-critique"); model_critique.add_argument("--model-id", required=True)
    model_artifact = sub.add_parser("model-artifact"); model_artifact.add_argument("--model-id", required=True); model_artifact.add_argument("--name", required=True)

    doc_gen = sub.add_parser("documentation-generate"); doc_gen.add_argument("--docset-id", required=True); doc_gen.add_argument("--model-id", required=True); doc_gen.add_argument("--no-current", action="store_true")
    doc_show = sub.add_parser("documentation-show"); doc_show.add_argument("--docset-id", required=True)
    sub.add_parser("documentation-list")
    doc_val = sub.add_parser("documentation-validate"); doc_val.add_argument("--docset-id", required=True)
    doc_crit = sub.add_parser("documentation-critique"); doc_crit.add_argument("--docset-id", required=True)
    doc_inv = sub.add_parser("documentation-invalidate"); doc_inv.add_argument("--invalidation-id", required=True); doc_inv.add_argument("--docset-id", required=True); doc_inv.add_argument("--memory-invalidation-id", required=True)

    exp_create = sub.add_parser("export-create"); exp_create.add_argument("--export-id", required=True); exp_create.add_argument("--docset-id", required=True); exp_create.add_argument("--profile", required=True, choices=PROFILES)
    exp_show = sub.add_parser("export-show"); exp_show.add_argument("--export-id", required=True)
    sub.add_parser("export-list")
    exp_val = sub.add_parser("export-validate"); exp_val.add_argument("--export-id", required=True)
    sub.add_parser("export-profiles")

    qna_ask = sub.add_parser("qna-ask"); qna_ask.add_argument("--answer-id", required=True); qna_ask.add_argument("--memory-id", required=True); qna_ask.add_argument("--question", required=True); qna_ask.add_argument("--limit", type=int, default=8)
    qna_show = sub.add_parser("qna-show"); qna_show.add_argument("--answer-id", required=True)
    qna_answer = sub.add_parser("qna-answer"); qna_answer.add_argument("--answer-id", required=True)
    sub.add_parser("qna-list")
    qna_validate = sub.add_parser("qna-validate"); qna_validate.add_argument("--answer-id", required=True)
    qna_critique = sub.add_parser("qna-critique"); qna_critique.add_argument("--answer-id", required=True)

    review_run = sub.add_parser("review-run"); review_run.add_argument("--run-id", required=True); review_run.add_argument("--review-target-id", required=True); review_run.add_argument("--profile", default="balanced", choices=REVIEW_PROFILES)
    review_show = sub.add_parser("review-show"); review_show.add_argument("--run-id", required=True)
    sub.add_parser("review-list")
    review_findings = sub.add_parser("review-findings"); review_findings.add_argument("--run-id", required=True)
    review_validate = sub.add_parser("review-validate"); review_validate.add_argument("--run-id", required=True)
    rvx_create = sub.add_parser("review-export-create"); rvx_create.add_argument("--export-id", required=True); rvx_create.add_argument("--run-id", required=True); rvx_create.add_argument("--profile", required=True, choices=REVIEW_EXPORT_PROFILES)
    rvx_show = sub.add_parser("review-export-show"); rvx_show.add_argument("--export-id", required=True)
    sub.add_parser("review-export-list")
    rvx_validate = sub.add_parser("review-export-validate"); rvx_validate.add_argument("--export-id", required=True)
    sub.add_parser("review-export-profiles")

    quality_run=sub.add_parser("quality-run"); quality_run.add_argument("--quality-id",required=True); quality_run.add_argument("--target",action="append",default=[]); quality_run.add_argument("--profile",default="comprehensive",choices=["comprehensive","release"])
    quality_show=sub.add_parser("quality-show"); quality_show.add_argument("--quality-id",required=True)
    sub.add_parser("quality-list")
    quality_validate=sub.add_parser("quality-validate"); quality_validate.add_argument("--quality-id",required=True)

    qualification_run=sub.add_parser("qualification-run"); qualification_run.add_argument("--qualification-id",required=True); qualification_run.add_argument("--runner",default="contract-simulator",choices=QUALIFICATION_RUNNERS); qualification_run.add_argument("--profile",action="append",choices=QUALIFICATION_PROFILES)
    qualification_show=sub.add_parser("qualification-show"); qualification_show.add_argument("--qualification-id",required=True)
    sub.add_parser("qualification-list"); qualification_validate=sub.add_parser("qualification-validate"); qualification_validate.add_argument("--qualification-id",required=True); sub.add_parser("qualification-matrix")

    sub.add_parser("platforms")
    pp=sub.add_parser("platform-package"); pp.add_argument("--package-id",required=True); pp.add_argument("--platform",required=True,choices=PLATFORMS); pp.add_argument("--force",action="store_true")
    pps=sub.add_parser("platform-package-show"); pps.add_argument("--package-id",required=True)
    ppv=sub.add_parser("platform-package-validate"); ppv.add_argument("--package-id",required=True)
    pi=sub.add_parser("platform-install")
    pi.add_argument("--platform",choices=PLATFORMS,help="Agent host; package/install IDs are generated automatically")
    pi.add_argument("--install-id")
    pi.add_argument("--package-id")
    pi.add_argument("--target-root",help="Advanced override for the normal global host config directory")
    pi.add_argument("--force",action="store_true")
    pd=sub.add_parser("platform-doctor")
    pd.add_argument("--platform",choices=PLATFORMS)
    pd.add_argument("--target-root")
    pu=sub.add_parser("platform-uninstall")
    pu.add_argument("--platform",choices=PLATFORMS)
    pu.add_argument("--target-root")
    pu.add_argument("--force",action="store_true")

    sub.add_parser("integration-matrix"); sub.add_parser("integration-report"); sub.add_parser("release-audit"); sub.add_parser("release-show")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command in FINAL_COMMANDS:
            if args.command == "integration-matrix": emit(IntegrationManager(project_root()).matrix())
            elif args.command == "integration-report": emit(IntegrationManager(project_root()).report())
            elif args.command == "release-audit":
                report=ReleaseManager(project_root()).audit(); emit(report); return 0 if report["status"]=="PASS" else 2
            elif args.command == "release-show": emit(ReleaseManager(project_root()).show())
            return 0

        if args.command in INSTALLATION_COMMANDS:
            manager=installation_manager(args)
            if args.command == "platforms":
                emit(manager.platforms())
            elif args.command == "platform-package":
                emit(manager.package(args.package_id,args.platform,args.force))
            elif args.command == "platform-package-show":
                emit(manager.show_package(args.package_id))
            elif args.command == "platform-package-validate":
                report=manager.validate_package(args.package_id); emit(report); return 0 if report["status"]=="PASS" else 2
            elif args.command == "platform-install":
                target=Path(args.target_root) if args.target_root else None
                if args.platform:
                    emit(manager.install_platform(args.platform,target,args.force))
                else:
                    if not (args.install_id and args.package_id and target):
                        raise TUnderstandError("CLI-INSTALL-001","Use --platform for normal installation, or provide --install-id, --package-id, and --target-root for advanced installation")
                    emit(manager.install(args.install_id,args.package_id,target,args.force))
            elif args.command == "platform-doctor":
                target=Path(args.target_root) if args.target_root else None
                if args.platform:
                    report=manager.doctor_platform(args.platform,target)
                elif target:
                    report=manager.doctor(target)
                else:
                    raise TUnderstandError("CLI-INSTALL-002","Use --platform or --target-root")
                emit(report); return 0 if report["status"]=="PASS" else 2
            elif args.command == "platform-uninstall":
                target=Path(args.target_root) if args.target_root else None
                if args.platform:
                    emit(manager.uninstall_platform(args.platform,target,args.force))
                elif target:
                    emit(manager.uninstall(target,args.force))
                else:
                    raise TUnderstandError("CLI-INSTALL-003","Use --platform or --target-root")
            return 0

        if args.command in QUALIFICATION_COMMANDS:
            manager=qualification_manager(args)
            if args.command == "qualification-run": emit(manager.run(args.qualification_id,args.runner,args.profile))
            elif args.command == "qualification-show": emit(manager.show(args.qualification_id))
            elif args.command == "qualification-list": emit(manager.list())
            elif args.command == "qualification-matrix": emit(manager.matrix())
            elif args.command == "qualification-validate":
                report=manager.validate(args.qualification_id); emit(report); return 0 if report["status"]=="PASS" else 2
            return 0

        if args.command in QUALITY_COMMANDS:
            manager=quality_manager(args)
            if args.command == "quality-run": emit(manager.run(args.quality_id,args.target,args.profile))
            elif args.command == "quality-show": emit(manager.show(args.quality_id))
            elif args.command == "quality-list": emit(manager.list())
            elif args.command == "quality-validate":
                report=manager.validate(args.quality_id); emit(report); return 0 if report["status"]=="PASS" else 2
            return 0

        if args.command in QNA_COMMANDS:
            manager = qna_manager(args)
            if args.command == "qna-ask": emit(manager.ask(args.answer_id, args.memory_id, args.question, args.limit))
            elif args.command == "qna-show": emit(manager.show(args.answer_id))
            elif args.command == "qna-answer": emit(manager.answer(args.answer_id))
            elif args.command == "qna-list": emit(manager.list())
            elif args.command == "qna-validate":
                report=manager.validate(args.answer_id); emit(report); return 0 if report["status"]=="PASS" else 2
            elif args.command == "qna-critique":
                report=manager.critique(args.answer_id); emit(report); return 0 if report["status"]=="PASS" else 2
            return 0

        if args.command in REVIEW_COMMANDS:
            if args.command == "review-export-profiles": emit({"profiles":list(REVIEW_EXPORT_PROFILES)}); return 0
            if args.command.startswith("review-export-"):
                manager=review_export_manager(args)
                if args.command == "review-export-create": emit(manager.create(args.export_id,args.run_id,args.profile))
                elif args.command == "review-export-show": emit(manager.show(args.export_id))
                elif args.command == "review-export-list": emit(manager.list())
                elif args.command == "review-export-validate":
                    report=manager.validate(args.export_id); emit(report); return 0 if report["status"]=="PASS" else 2
            else:
                manager=review_manager(args)
                if args.command == "review-run": emit(manager.run(args.run_id,args.review_target_id,args.profile))
                elif args.command == "review-show": emit(manager.show(args.run_id))
                elif args.command == "review-list": emit(manager.list())
                elif args.command == "review-findings": emit({"findings":manager.findings(args.run_id)})
                elif args.command == "review-validate":
                    report=manager.validate(args.run_id); emit(report); return 0 if report["status"]=="PASS" else 2
            return 0

        if args.command in MODELING_COMMANDS:
            manager = model_manager(args)
            if args.command == "model-build": emit(manager.build(args.model_id, args.memory_id, not args.no_current))
            elif args.command == "model-reconcile": emit(manager.reconcile(args.reconciliation_id,args.model_id,args.base_model_id,args.memory_id))
            elif args.command == "model-show": emit(manager.show(args.model_id))
            elif args.command == "model-list": emit(manager.list())
            elif args.command == "model-validate":
                report=manager.validate(args.model_id); emit(report); return 0 if report["status"]=="PASS" else 2
            elif args.command == "model-critique":
                report=manager.critique(args.model_id); emit(report); return 0 if report["status"]=="PASS" else 2
            elif args.command == "model-artifact": emit(manager.artifact(args.model_id,args.name))
            return 0

        if args.command in DOCUMENTATION_COMMANDS:
            if args.command == "export-profiles":
                emit({"profiles":list(PROFILES)})
                return 0
            if args.command.startswith("export-"):
                manager=export_manager(args)
                if args.command == "export-create": emit(manager.create(args.export_id,args.docset_id,args.profile))
                elif args.command == "export-show": emit(manager.show(args.export_id))
                elif args.command == "export-list": emit(manager.list())
                elif args.command == "export-validate":
                    report=manager.validate(args.export_id); emit(report); return 0 if report["status"]=="PASS" else 2
            else:
                manager=documentation_manager(args)
                if args.command == "documentation-generate": emit(manager.generate(args.docset_id,args.model_id,not args.no_current))
                elif args.command == "documentation-show": emit(manager.show(args.docset_id))
                elif args.command == "documentation-list": emit(manager.list())
                elif args.command == "documentation-validate":
                    report=manager.validate(args.docset_id); emit(report); return 0 if report["status"]=="PASS" else 2
                elif args.command == "documentation-critique":
                    report=manager.critique(args.docset_id); emit(report); return 0 if report["status"]=="PASS" else 2
                elif args.command == "documentation-invalidate": emit(manager.invalidate(args.invalidation_id,args.docset_id,args.memory_invalidation_id))
            return 0

        if args.command in KNOWLEDGE_COMMANDS:
            if args.command.startswith("analysis-"):
                manager = analysis_manager(args)
                if args.command == "analysis-run": emit(manager.run(args.analysis_id, args.extraction_id, args.scope))
                elif args.command == "analysis-refresh": emit(manager.refresh(args.analysis_id, args.base_analysis_id, args.extraction_id))
                elif args.command == "analysis-show": emit(manager.show(args.analysis_id))
                elif args.command == "analysis-list": emit(manager.list())
                elif args.command == "analysis-validate":
                    report = manager.validate(args.analysis_id); emit(report); return 0 if report["status"] == "PASS" else 2
            elif args.command.startswith("graph-"):
                manager = graph_manager(args)
                if args.command == "graph-create": emit(manager.create(args.graph_id, args.analysis_id))
                elif args.command == "graph-show": emit(manager.show(args.graph_id))
                elif args.command == "graph-list": emit(manager.list())
                elif args.command == "graph-validate":
                    report = manager.validate(args.graph_id); emit(report); return 0 if report["status"] == "PASS" else 2
            else:
                manager = memory_manager(args)
                if args.command == "memory-build": emit(manager.build(args.memory_id, args.graph_id, not args.no_current))
                elif args.command == "memory-show": emit(manager.show(args.memory_id))
                elif args.command == "memory-list": emit(manager.list())
                elif args.command == "memory-validate":
                    report = manager.validate(args.memory_id); emit(report); return 0 if report["status"] == "PASS" else 2
                elif args.command == "memory-critique":
                    report = manager.critique(args.memory_id); emit(report); return 0 if report["status"] == "PASS" else 2
                elif args.command == "memory-freshness": emit(manager.freshness(args.memory_id, args.snapshot_id))
                elif args.command == "memory-invalidate": emit(manager.invalidate(args.invalidation_id, args.memory_id, args.candidate_discovery_id))
                elif args.command == "memory-index-rebuild": emit(manager.rebuild_index(args.memory_id))
                elif args.command == "memory-search": emit(manager.search(args.memory_id, args.query, args.limit))
            return 0

        if args.command in DISCOVERY_COMMANDS:
            if args.command.startswith("discovery-"):
                manager = discovery_manager(args)
                if args.command == "discovery-run":
                    emit(manager.create(args.discovery_id, args.snapshot_id))
                elif args.command == "discovery-show":
                    emit(manager.show(args.discovery_id))
                elif args.command == "discovery-list":
                    emit(manager.list())
                elif args.command == "discovery-validate":
                    report = manager.validate(args.discovery_id)
                    emit(report)
                    return 0 if report["status"] == "PASS" else 2
            else:
                manager = adapter_manager(args)
                if args.command == "adapter-run":
                    emit(manager.run(args.extraction_id, args.discovery_id))
                elif args.command == "adapter-show":
                    emit(manager.show(args.extraction_id))
                elif args.command == "adapter-list":
                    emit(manager.list())
                elif args.command == "adapter-validate":
                    report = manager.validate(args.extraction_id)
                    emit(report)
                    return 0 if report["status"] == "PASS" else 2
                elif args.command == "adapter-capabilities":
                    emit(manager.capabilities())
            return 0

        if args.command in SNAPSHOT_COMMANDS:
            manager = snapshot_manager(args)
            if args.command == "snapshot-create":
                emit(manager.create_snapshot(args.snapshot_id, parse_target_assignments(args.target), args.purpose))
            elif args.command == "snapshot-show":
                emit(manager.show_snapshot(args.snapshot_id))
            elif args.command == "snapshot-list":
                emit(manager.list_snapshots())
            elif args.command == "snapshot-validate":
                report = manager.validate_snapshot(args.snapshot_id)
                emit(report)
                return 0 if report["status"] == "PASS" else 2
            elif args.command == "snapshot-drift":
                report = manager.drift(args.snapshot_id)
                emit(report)
                return 0 if report["status"] == "UNCHANGED" else 3
            elif args.command == "review-target-create":
                emit(manager.create_review_target(args.review_id, args.mode, args.candidate, args.baseline))
            elif args.command == "review-target-show":
                emit(manager.show_review_target(args.review_id))
            elif args.command == "review-target-validate":
                report = manager.validate_review_target(args.review_id)
                emit(report)
                return 0 if report["status"] == "PASS" else 2
            return 0

        if args.command in AGENT_NATIVE_COMMANDS:
            manager = AgentConversationManager(project_root(), active_workspace_root(), resolved_context_root(args))
            if args.command == "agent-plan":
                emit(manager.plan(args.prompt))
            elif args.command == "agent-capabilities":
                prompt = {"greeting": "hi", "help": "help", "details": "show all capabilities"}[args.mode]
                emit(manager.plan(prompt))
            elif args.command == "agent-document":
                emit(manager.generate_documentation(args.prompt))
            elif args.command == "agent-response-validate":
                response = sys.stdin.read() if args.response_file == "-" else Path(args.response_file).read_text(encoding="utf-8")
                report = manager.validate_response(args.prompt, response)
                emit(report)
                return 0 if report["status"] == "PASS" else 2
            return 0

        if args.command == "agent-bootstrap":
            emit(bootstrap_active_workspace(args))
            return 0

        if args.command in APPLICATION_COMMANDS:
            manager = application_manager(args)
            if args.command == "application-init":
                emit(manager.initialize(args.application_id, args.name, args.workspace_model, args.machine_id, args.description))
            elif args.command == "application-show":
                emit(manager.show())
            elif args.command == "application-validate":
                report = manager.validate(args.inspect_workspace)
                emit(report)
                return 0 if report["status"] == "PASS" else 2
            elif args.command == "repository-add":
                emit(manager.add_repository(args.repository_id, args.name, args.role, args.remote, args.identity_key, args.default_ref, args.tag))
            elif args.command == "repository-remove":
                emit(manager.remove_repository(args.repository_id))
            elif args.command == "workspace-bind":
                emit(manager.bind_repository(args.repository_id, Path(args.path)))
            elif args.command == "workspace-unbind":
                emit(manager.unbind_repository(args.repository_id))
            elif args.command == "workspace-resolve":
                emit(manager.resolve())
            return 0

        runtime = engine(args)
        if args.command == "workflows":
            emit({
                "workflows": [
                    {
                        "id": workflow.id,
                        "initial_state": workflow.initial_state,
                        "terminal_states": list(workflow.terminal_states),
                        "states": len(workflow.states),
                    }
                    for workflow in runtime.registry.workflows.values()
                ]
            })
        elif args.command == "init":
            emit(runtime.init_work(args.work_id, args.workflow, args.snapshot, args.profile, args.application_id))
        elif args.command == "status":
            emit(runtime.status(args.work_id))
        elif args.command == "route":
            emit(runtime.route(args.work_id, args.objective))
        elif args.command == "complete":
            emit(runtime.complete_root_state(args.work_id, parse_artifacts(args.artifact), args.next_state))
        elif args.command == "accept-result":
            emit(runtime.accept_result(args.work_id, Path(args.result), args.next_state))
        elif args.command == "record-approval":
            emit(runtime.record_approval(args.work_id, args.decision, args.rationale, args.loopback_target, args.subject_sha256))
        elif args.command == "resume":
            emit(runtime.resume(args.work_id, args.reason))
        elif args.command == "validate-work":
            emit(runtime.validate_work(args.work_id))
        elif args.command == "validate-packet":
            runtime.contracts.validate("delegation-packet", load_yaml(Path(args.path)))
            emit({"status": "PASS", "contract": "delegation-packet", "path": args.path})
        elif args.command == "validate-result":
            runtime.contracts.validate("result-envelope", load_yaml(Path(args.path)))
            emit({"status": "PASS", "contract": "result-envelope", "path": args.path})
        return 0
    except TUnderstandError as exc:
        print(json.dumps({"status": "ERROR", **exc.as_dict()}, indent=2), file=sys.stderr)
        return 2


def entrypoint() -> None:
    import os
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)


if __name__ == "__main__":
    entrypoint()
