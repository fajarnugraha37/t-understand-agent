from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .errors import TUnderstandError


SCHEMA_FILES = {
    "delegation-packet": "delegation-packet.schema.json",
    "result-envelope": "result-envelope.schema.json",
    "work-state": "work-state.schema.json",
    "approval-record": "approval-record.schema.json",
    "transition-record": "transition-record.schema.json",
    "loopback-record": "loopback-record.schema.json",
    "application-manifest": "application-manifest.schema.json",
    "workspace-map": "workspace-map.schema.json",
    "workspace-resolution": "workspace-resolution.schema.json",
    "application-validation-report": "application-validation-report.schema.json",
    "repository-snapshot": "repository-snapshot.schema.json",
    "application-snapshot": "application-snapshot.schema.json",
    "snapshot-validation-report": "snapshot-validation-report.schema.json",
    "snapshot-drift-report": "snapshot-drift-report.schema.json",
    "review-target": "review-target.schema.json",
    "file-inventory-record": "file-inventory-record.schema.json",
    "repository-discovery": "repository-discovery.schema.json",
    "application-discovery": "application-discovery.schema.json",
    "adapter-manifest": "adapter-manifest.schema.json",
    "adapter-extraction": "adapter-extraction.schema.json",
    "adapter-run": "adapter-run.schema.json",
    "adapter-capability-matrix": "adapter-capability-matrix.schema.json",
    "evidence-record": "evidence-record.schema.json",
    "claim": "claim.schema.json",
    "analysis-entity": "analysis-entity.schema.json",
    "analysis-relation": "analysis-relation.schema.json",
    "analysis-observation": "analysis-observation.schema.json",
    "analysis-run": "analysis-run.schema.json",
    "analysis-summary": "analysis-summary.schema.json",
    "application-graph": "application-graph.schema.json",
    "cross-repository-relation": "cross-repository-relation.schema.json",
    "relationship-candidate": "relationship-candidate.schema.json",
    "memory-manifest": "memory-manifest.schema.json",
    "memory-invalidation": "memory-invalidation.schema.json",
    "memory-critique": "memory-critique.schema.json",
    "memory-verification": "memory-verification.schema.json",
    "freshness-assessment": "freshness-assessment.schema.json",
    "model-record": "model-record.schema.json",
    "model-artifact": "model-artifact.schema.json",
    "model-manifest": "model-manifest.schema.json",
    "model-trace": "model-trace.schema.json",
    "model-critique": "model-critique.schema.json",
    "model-verification": "model-verification.schema.json",
    "model-reconciliation": "model-reconciliation.schema.json",
    "documentation-section": "documentation-section.schema.json",
    "documentation-manifest": "documentation-manifest.schema.json",
    "document-plan": "document-plan.schema.json",
    "documentation-trace": "documentation-trace.schema.json",
    "coverage-ledger": "coverage-ledger.schema.json",
    "documentation-critique": "documentation-critique.schema.json",
    "documentation-verification": "documentation-verification.schema.json",
    "document-invalidation": "document-invalidation.schema.json",
    "export-manifest": "export-manifest.schema.json",
    "render-validation": "render-validation.schema.json",
    "qna-retrieval-set": "qna-retrieval-set.schema.json",
    "direct-source-verification": "direct-source-verification.schema.json",
    "qna-answer": "qna-answer.schema.json",
    "answer-critique": "answer-critique.schema.json",
    "citation-validation": "citation-validation.schema.json",
    "qna-manifest": "qna-manifest.schema.json",
    "review-changed-file": "review-changed-file.schema.json",
    "review-coverage": "review-coverage.schema.json",
    "review-analysis": "review-analysis.schema.json",
    "review-finding": "review-finding.schema.json",
    "finding-critique": "finding-critique.schema.json",
    "severity-calibration": "severity-calibration.schema.json",
    "review-verification": "review-verification.schema.json",
    "review-manifest": "review-manifest.schema.json",
    "review-export-manifest": "review-export-manifest.schema.json",
    "quality-report": "quality-report.schema.json",
    "quality-manifest": "quality-manifest.schema.json",
    "qualification-report": "qualification-report.schema.json",
    "qualification-manifest": "qualification-manifest.schema.json",
    "platform-package": "platform-package.schema.json",
    "install-manifest": "install-manifest.schema.json",
    "integration-report": "integration-report.schema.json",
    "release-qualification": "release-qualification.schema.json",
    "software-bill-of-materials": "software-bill-of-materials.schema.json",
    "platform-adapter": "platform-adapter.schema.json",
}


class ContractValidator:
    def __init__(self, root: Path):
        self.root = root
        self.validators: dict[str, Draft202012Validator] = {}
        for name, filename in SCHEMA_FILES.items():
            schema_path = root / "schemas" / filename
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            self.validators[name] = Draft202012Validator(schema, format_checker=FormatChecker())

    def validate(self, contract: str, data: Any) -> None:
        validator = self.validators.get(contract)
        if validator is None:
            raise TUnderstandError("RT-SCHEMA-001", f"Unknown runtime contract: {contract}")
        errors = sorted(validator.iter_errors(data), key=lambda item: list(item.absolute_path))
        if errors:
            rendered = []
            for error in errors[:10]:
                path = ".".join(str(part) for part in error.absolute_path) or "$"
                rendered.append(f"{path}: {error.message}")
            raise TUnderstandError("RT-SCHEMA-002", f"{contract} validation failed: {'; '.join(rendered)}")
