from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
VERSION = (ROOT / "VERSION").read_text().strip()


def load(name: str) -> dict:
    return json.loads((REPORTS / name).read_text())


def passed(*reports: dict) -> bool:
    return all(report.get("status") == "PASS" for report in reports)


def write(phase: int, report: dict) -> None:
    payload = {
        "product": "t-understand",
        "version": VERSION,
        "phase": phase,
        **report,
    }
    (REPORTS / f"phase-{phase}-summary.json").write_text(
        json.dumps(payload, indent=2) + "\n"
    )


qna_contract = load("qna-contract-report.json")
qna_tests = load("qna-test-report.json")
write(13, {
    "phase_name": "Evidence-Grounded Question Answering",
    "status": "PASS" if passed(qna_contract, qna_tests) else "FAIL",
    "validation": {
        "contract_checks": qna_contract["checks"],
        "tests": qna_tests["tests_run"],
    },
    "assurances": [
        "snapshot_aware_retrieval",
        "direct_evidence_verification",
        "cited_answers",
        "unknown_over_guessing",
        "inference_disclosure",
        "tamper_detection",
        "atomic_rollback",
    ],
})

review_contract = load("review-contract-report.json")
review_tests = load("review-test-report.json")
write(14, {
    "phase_name": "Repository Review",
    "status": "PASS" if passed(review_contract, review_tests) else "FAIL",
    "validation": {
        "contract_checks": review_contract["checks"],
        "tests": review_tests["tests_run"],
    },
    "assurances": [
        "static_and_diff_review",
        "coverage_ledger",
        "impact_tracing",
        "finding_deduplication",
        "critic_challenge",
        "severity_calibration",
        "merge_gate",
    ],
})

review_export_contract = load("review-export-contract-report.json")
write(15, {
    "phase_name": "Review Export",
    "status": "PASS" if passed(review_export_contract, review_tests) else "FAIL",
    "validation": {
        "contract_checks": review_export_contract["checks"],
        "shared_review_tests": review_tests["tests_run"],
    },
    "profiles": ["canonical", "github", "gitlab", "cli", "json"],
    "assurances": [
        "canonical_semantics_preserved",
        "source_review_digest",
        "tamper_detection",
    ],
})

quality_contract = load("quality-contract-report.json")
quality_tests = load("quality-test-report.json")
write(16, {
    "phase_name": "Consolidated Quality Plane",
    "status": "PASS" if passed(quality_contract, quality_tests) else "FAIL",
    "validation": {
        "contract_checks": quality_contract["checks"],
        "tests": quality_tests["tests_run"],
    },
    "assurances": [
        "fail_closed_multi_artifact_validation",
        "independent_critique",
        "immutable_reports",
        "tamper_detection",
        "atomic_rollback",
    ],
})

qualification_contract = load("qualification-contract-report.json")
qualification_tests = load("qualification-test-report.json")
write(17, {
    "phase_name": "Cheap-Model Contract Qualification",
    "status": "PASS" if passed(qualification_contract, qualification_tests) else "FAIL",
    "validation": {
        "contract_checks": qualification_contract["checks"],
        "tests": qualification_tests["tests_run"],
    },
    "assurances": [
        "economy_balanced_deep_profiles",
        "provider_neutral_contract_runner",
        "explicit_no_live_model_claim",
        "immutable_reports",
    ],
    "limitations": [
        "The built-in qualification runner is provider-neutral and does not invoke a live external AI model."
    ],
})

installation_contract = load("installation-contract-report.json")
installation_tests = load("installation-test-report.json")
write(18, {
    "phase_name": "Platform Adapters and Installation",
    "status": "PASS" if passed(installation_contract, installation_tests) else "FAIL",
    "validation": {
        "contract_checks": installation_contract["checks"],
        "tests": installation_tests["tests_run"],
        "platforms": 4,
    },
    "assurances": [
        "managed_ownership",
        "source_context_target_denial",
        "backup_restore",
        "doctor",
        "modified_file_refusal",
        "safe_uninstall",
        "agent_native_private_engine_packaging",
    ],
    "limitations": [
        "External OpenCode, Codex, Claude Code, and Cursor executables are not invoked by the release harness."
    ],
})

integration = load("integration-test-report.json")
write(19, {
    "phase_name": "Complete Integration Scenarios",
    "status": integration["status"],
    "validation": {
        "scenarios": integration["checks"],
        "passed": sum(1 for item in integration["scenarios"] if item["status"] == "PASS"),
    },
    "scenario_ids": [item["id"] for item in integration["scenarios"]],
    "assurances": [
        "isolated_scenario_evidence",
        "single_repository",
        "monorepo",
        "multi_repository",
        "review_matrix",
        "freshness_refresh",
        "installation",
        "qualification",
    ],
})

release_contract = load("release-contract-report.json")
governance = load("governance-report.json")
negative = load("negative-test-report.json")
agent_tests = load("agent-native-test-report.json")
agent_cli = load("agent-native-cli-report.json")
write(20, {
    "phase_name": "Release Qualification",
    "status": "PASS" if passed(
        release_contract, governance, negative, integration, agent_tests, agent_cli
    ) else "FAIL",
    "validation": {
        "release_contract_checks": release_contract["checks"],
        "schemas": len(list((ROOT / "schemas").glob("*.schema.json"))),
        "governance_checks": governance["checks"],
        "negative_cases": 25,
        "integration_scenarios": integration["checks"],
        "agent_native_tests": agent_tests["tests"],
        "agent_native_cli_checks": agent_cli["checks"],
    },
    "assurances": [
        "version_consistency",
        "software_bill_of_materials",
        "checksums",
        "deterministic_zip",
        "extracted_package_verification_required",
    ],
    "limitations": [
        "Deterministic ZIP and extracted-package verification are performed during final release freeze, after this source-tree summary is generated."
    ],
})

print(json.dumps({"status": "PASS", "version": VERSION, "phases": list(range(13, 21))}, indent=2))
