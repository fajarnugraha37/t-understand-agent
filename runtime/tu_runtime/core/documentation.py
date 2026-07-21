from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from .analysis import ID_RE
from .contracts import ContractValidator
from .discovery import _canonical_digest
from .errors import TUnderstandError
from .io import atomic_write_text, atomic_write_yaml, load_yaml, sha256_file, utc_now
from .memory import MemoryManager
from .modeling import MODEL_TYPES, ModelManager


def _id(prefix: str, *parts: Any) -> str:
    raw = "\x1f".join(str(value) for value in parts).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(raw).hexdigest()[:16].upper()}"


def _slug(value: str, fallback: str = "item") -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not result:
        result = fallback
    if not result[0].isalpha():
        result = f"item-{result}"
    return result[:72].rstrip("-")


def _jsonl(values: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n" for value in values)


GENERIC_SECTIONS = ("Purpose and scope", "Coverage summary", "Evidenced findings", "Evidence and traceability", "Unknowns and limitations")
FLOW_ALL_SECTIONS = (
    "Purpose and scope", "Business and application intent", "Trigger and preconditions", "Participants and repositories",
    "Sequence and interactions", "State and data impact", "Transactions and consistency", "Alternatives, failures, and recovery",
    "Security", "Observability and operations", "Evidence and traceability", "Unknowns and limitations",
)

# Base documents are mandatory. Runtime planning adds per-repository and per-flow documents.
DOCUMENT_CATALOG = (
    ("application-overview", "index.md", "mixed", ["application-model", "business-goals", "domain-overview", "flows"]),
    ("application-architecture", "application/architecture.md", "technical", ["architecture-model", "dependency-model", "deployment-model", "security-model"]),
    ("repository-landscape", "application/repository-landscape.md", "mixed", ["repository-model", "application-model", "ownership-boundaries"]),
    ("application-capability-map", "application/capability-map.md", "mixed", ["business-capabilities", "ownership-boundaries", "repository-model"]),
    ("end-to-end-flows", "application/end-to-end-flows.md", "mixed", ["flows", "business-processes", "consistency-model"]),
    ("business-goals", "business/goals-and-outcomes.md", "business", ["business-goals"]),
    ("business-capabilities", "business/capabilities.md", "business", ["business-capabilities", "ownership-boundaries"]),
    ("business-actors", "business/actors-and-stakeholders.md", "business", ["actors"]),
    ("business-processes", "business/business-processes.md", "business", ["business-processes", "flows"]),
    ("business-policies", "business/policies-and-decisions.md", "business", ["policies-decisions", "business-rules", "decision-tables"]),
    ("business-controls", "business/controls-and-compliance.md", "business", ["controls-compliance", "security-model"]),
    ("domain-overview", "domain/overview.md", "mixed", ["domain-overview"]),
    ("bounded-contexts", "domain/bounded-contexts.md", "mixed", ["bounded-contexts", "ownership-boundaries"]),
    ("ubiquitous-language", "domain/ubiquitous-language.md", "mixed", ["terminology"]),
    ("aggregates-entities", "domain/aggregates-and-entities.md", "technical", ["aggregates-entities"]),
    ("value-objects", "domain/value-objects.md", "technical", ["value-objects"]),
    ("domain-invariants", "domain/invariants.md", "mixed", ["invariants", "business-rules"]),
    ("domain-services", "domain/domain-services.md", "technical", ["domain-services"]),
    ("commands", "domain/commands.md", "mixed", ["commands"]),
    ("domain-events", "domain/domain-events.md", "mixed", ["domain-events", "event-model"]),
    ("state-machines", "domain/state-machines.md", "mixed", ["state-model", "flows"]),
    ("decision-tables", "domain/decision-tables.md", "mixed", ["decision-tables", "policies-decisions"]),
    ("ownership-boundaries", "domain/ownership-and-boundaries.md", "mixed", ["ownership-boundaries", "bounded-contexts", "data-model"]),
    ("flow-index", "flows/index.md", "mixed", ["flows"]),
    ("flow-catalog", "flows/flow-catalog.md", "mixed", ["flows"]),
    ("flow-failure-catalog", "flows/failure-and-recovery.md", "mixed", ["flow-failures", "consistency-model"]),
    ("integration-overview", "integrations/overview.md", "technical", ["dependency-model", "flows"]),
    ("http-contract-map", "integrations/http-contract-map.md", "technical", ["dependency-model", "architecture-model"]),
    ("event-topology", "integrations/event-topology.md", "technical", ["event-model", "flows"]),
    ("data-dependency-map", "integrations/data-and-dependency-map.md", "technical", ["data-model", "dependency-model"]),
    ("data-model", "data/data-model.md", "technical", ["data-model", "aggregates-entities", "value-objects"]),
    ("consistency-transactions", "data/consistency-and-transactions.md", "technical", ["consistency-model", "flows", "flow-failures"]),
    ("build-development", "operations/build-and-development.md", "technical", ["application-model", "repository-model"]),
    ("configuration", "operations/configuration.md", "technical", ["architecture-model", "repository-model"]),
    ("deployment", "operations/deployment.md", "technical", ["deployment-model"]),
    ("security", "operations/security.md", "technical", ["security-model", "controls-compliance"]),
    ("observability", "operations/observability.md", "technical", ["observability-model"]),
    ("operational-failures", "operations/failure-and-recovery.md", "technical", ["flow-failures", "consistency-model"]),
    ("testing-verification", "operations/testing-and-verification.md", "technical", ["application-model", "business-rules", "flows"]),
    ("terminology", "reference/terminology.md", "mixed", ["terminology"]),
    ("known-unknowns", "reference/known-unknowns.md", "mixed", list(MODEL_TYPES)),
)


@dataclass(frozen=True)
class DocumentSpec:
    document_id: str
    path: str
    audience: str
    source_models: tuple[str, ...]
    category: str
    required_sections: tuple[str, ...] = GENERIC_SECTIONS
    generation_mode: str = "catalog"
    scope: dict[str, str] | None = None

    @property
    def requirement_id(self) -> str:
        return _id("DOCREQ", self.document_id, self.path, json.dumps(self.scope or {}, sort_keys=True))

    def as_requirement(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "category": self.category,
            "document_id": self.document_id,
            "path": self.path,
            "audience": self.audience,
            "source_models": list(self.source_models),
            "required_sections": list(self.required_sections),
            "generation_mode": self.generation_mode,
            "scope": self.scope or {},
        }


CATEGORY_BY_PREFIX = {
    "application/": "application", "business/": "business", "domain/": "domain", "flows/": "flows",
    "repositories/": "repositories", "integrations/": "integrations", "data/": "data",
    "operations/": "operations", "reference/": "reference",
}


class DocumentationManager:
    def __init__(self, project_root: Path, context_root: Path):
        self.project_root = project_root
        self.context_root = context_root.resolve()
        self.models = ModelManager(project_root, context_root)
        self.memory = MemoryManager(project_root, context_root)
        self.contracts = ContractValidator(project_root)

    @property
    def root(self) -> Path:
        return self.context_root / "documentation" / "canonical"

    @property
    def reports_root(self) -> Path:
        return self.context_root / "reports" / "documentation"

    @property
    def invalidations_root(self) -> Path:
        return self.context_root / "documentation" / "invalidations"

    @property
    def user_output_root(self) -> Path:
        return self.context_root / "output" / "documentation"

    @property
    def latest_output(self) -> Path:
        return self.user_output_root / "latest"

    @contextmanager
    def lock(self) -> Iterator[None]:
        lock = self.context_root / "runtime" / "locks" / "documentation.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        try:
            lock.mkdir()
        except FileExistsError as exc:
            raise TUnderstandError("DOC-LOCK-001", "Documentation mutation is already active") from exc
        try:
            yield
        finally:
            lock.rmdir()

    def _dir(self, docset_id: str) -> Path:
        if not ID_RE.fullmatch(docset_id):
            raise TUnderstandError("DOC-ID-001", "docset_id must match canonical ID pattern")
        return self.root / docset_id

    def _base_specs(self) -> list[DocumentSpec]:
        specs: list[DocumentSpec] = []
        for document_id, path, audience, sources in DOCUMENT_CATALOG:
            category = "application" if path == "index.md" else next((value for prefix, value in CATEGORY_BY_PREFIX.items() if path.startswith(prefix)), "reference")
            mode = "known-unknowns" if document_id == "known-unknowns" else "catalog"
            specs.append(DocumentSpec(document_id, path, audience, tuple(sources), category, generation_mode=mode))
        return specs

    def _plan_specs(self, model_docs: dict[str, dict[str, Any]]) -> list[DocumentSpec]:
        specs = self._base_specs()
        repositories = sorted({
            record.get("attributes", {}).get("repository_id")
            for record in model_docs["application-model"]["records"]
            if record.get("attributes", {}).get("repository_id")
        })
        repository_documents = (
            ("overview", "mixed", ("repository-model", "application-model")),
            ("architecture", "technical", ("architecture-model", "dependency-model")),
            ("interfaces", "technical", ("dependency-model", "event-model", "data-model")),
            ("domain", "mixed", ("bounded-contexts", "aggregates-entities", "value-objects", "invariants", "commands", "domain-events", "state-model")),
            ("flows", "mixed", ("flows", "flow-failures", "consistency-model")),
            ("operations", "technical", ("deployment-model", "security-model", "observability-model", "consistency-model")),
            ("limitations", "mixed", tuple(MODEL_TYPES)),
        )
        for repository_id in repositories:
            repo_slug = _slug(repository_id, "repository")
            for section, audience, sources in repository_documents:
                specs.append(DocumentSpec(
                    f"repository-{repo_slug}-{section}", f"repositories/{repo_slug}/{section}.md", audience, sources,
                    "repositories", generation_mode="repository", scope={"repository_id": repository_id},
                ))

        for flow in model_docs["flows"]["records"]:
            attributes = flow.get("attributes", {})
            tier = attributes.get("tier", "TIER_3")
            flow_key = str(attributes.get("flow_key") or flow["title"])
            flow_slug = f"{_slug(flow_key, 'flow')}-{flow['id'][-6:].lower()}"
            scope = {"flow_record_id": flow["id"], "flow_key": flow_key}
            if tier == "TIER_1":
                deep = (
                    ("overview", ("Purpose and scope", "Business and application intent", "Trigger and preconditions", "Participants and repositories", "Evidence and traceability", "Unknowns and limitations")),
                    ("sequence-and-interactions", ("Purpose and scope", "Sequence and interactions", "Synchronous and asynchronous boundaries", "Evidence and traceability", "Unknowns and limitations")),
                    ("alternatives-failures-recovery", ("Purpose and scope", "Alternatives, failures, and recovery", "Retry, compensation, and reconciliation", "Evidence and traceability", "Unknowns and limitations")),
                    ("state-data-consistency", ("Purpose and scope", "State and data impact", "Transactions and consistency", "Evidence and traceability", "Unknowns and limitations")),
                    ("security-observability-operations", ("Purpose and scope", "Security", "Observability and operations", "Evidence and traceability", "Unknowns and limitations")),
                )
                for suffix, sections in deep:
                    specs.append(DocumentSpec(
                        f"flow-{flow_slug}-{suffix}", f"flows/{flow_slug}/{suffix}.md", "mixed", ("flows", "flow-failures", "consistency-model", "security-model", "observability-model"),
                        "flows", sections, "deep-flow", scope,
                    ))
            elif tier == "TIER_2":
                specs.append(DocumentSpec(
                    f"flow-{flow_slug}", f"flows/{flow_slug}.md", "mixed", ("flows", "flow-failures", "consistency-model", "security-model", "observability-model"),
                    "flows", FLOW_ALL_SECTIONS, "standard-flow", scope,
                ))
        ids = [spec.document_id for spec in specs]
        paths = [spec.path for spec in specs]
        if len(ids) != len(set(ids)) or len(paths) != len(set(paths)):
            raise TUnderstandError("DOC-PLAN-001", "Dynamic documentation plan contains duplicate document IDs or paths")
        return specs

    @staticmethod
    def _record_repositories(record: dict[str, Any], entity_by_id: dict[str, dict[str, Any]]) -> set[str]:
        attributes = record.get("attributes", {})
        repositories = set()
        for key in ("repository_id", "source_repository", "target_repository"):
            value = attributes.get(key)
            if value:
                repositories.add(str(value))
        repositories.update(str(value) for value in attributes.get("repositories", []) if value)
        for entity_id in record.get("source_entities", []):
            entity = entity_by_id.get(entity_id)
            if entity:
                repositories.add(entity["repository_id"])
        return repositories

    def _select_records(self, spec: DocumentSpec, model_docs: dict[str, dict[str, Any]], entity_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        records = [record for source in spec.source_models for record in model_docs[source]["records"]]
        # Stable de-duplication because a source model may be listed more than once through future composition.
        records = list({record["id"]: record for record in records}.values())
        scope = spec.scope or {}
        if spec.generation_mode == "known-unknowns":
            records = [record for record in records if record["classification"] in {"UNKNOWN", "CONFLICT", "LIMITATION"} or record.get("limitations")]
        if repository_id := scope.get("repository_id"):
            records = [record for record in records if repository_id in self._record_repositories(record, entity_by_id)]
            if spec.path.endswith("limitations.md"):
                records = [record for record in records if record["classification"] in {"UNKNOWN", "CONFLICT", "LIMITATION"} or record.get("limitations")]
        if flow_record_id := scope.get("flow_record_id"):
            flow = next((record for record in model_docs["flows"]["records"] if record["id"] == flow_record_id), None)
            records = [flow] if flow else []
        return sorted(records, key=lambda record: (record["title"].lower(), record["id"]))

    def generate(self, docset_id: str, model_id: str, make_current: bool = True) -> dict[str, Any]:
        final = self._dir(docset_id)
        if final.exists():
            raise TUnderstandError("DOC-ID-002", f"Documentation set already exists and is immutable: {docset_id}")
        if self.models.validate(model_id)["status"] != "PASS":
            raise TUnderstandError("DOC-INPUT-001", "Model validation failed")
        model = self.models.show(model_id)
        memory_manifest = self.memory.show(model["memory_id"])
        entities = self.memory._load_artifact(model["memory_id"], "entities")
        entity_by_id = {entity["id"]: entity for entity in entities}
        model_docs = {name: self.models.artifact(model_id, name) for name in MODEL_TYPES}
        specs = self._plan_specs(model_docs)
        requirements = {
            "schema_id": "https://t-understand.dev/schemas/documentation-requirements.schema.json",
            "schema_version": "1.0.0", "docset_id": docset_id, "model_id": model_id,
            "requirements": [spec.as_requirement() for spec in specs], "generated_at": utc_now(),
        }
        self.contracts.validate("documentation-requirements", requirements)
        plan = {
            "schema_id": "https://t-understand.dev/schemas/document-plan.schema.json", "schema_version": "1.0.0",
            "docset_id": docset_id, "model_id": model_id,
            "documents": [spec.as_requirement() for spec in specs], "generated_at": utc_now(),
        }
        self.contracts.validate("document-plan", plan)
        status = "CONFLICTED" if model["status"] == "CONFLICTED" else "CURRENT"

        with self.lock():
            temp = self.root / f".{docset_id}.{uuid.uuid4().hex}.tmp"
            temp.mkdir(parents=True)
            try:
                atomic_write_yaml(temp / "documentation-requirements.yaml", requirements)
                atomic_write_yaml(temp / "document-plan.yaml", plan)
                info = self._information_architecture(docset_id, model["application_id"], specs)
                atomic_write_yaml(temp / "information-architecture.yaml", info)
                sections: list[dict[str, Any]] = []
                traces: list[dict[str, Any]] = []
                documents: list[dict[str, Any]] = []
                generation: list[dict[str, Any]] = []
                covered: set[str] = set()
                all_record_ids = {record["id"] for document in model_docs.values() for record in document["records"]}

                for spec in specs:
                    selected = self._select_records(spec, model_docs, entity_by_id)
                    body, document_sections = self._render_document(docset_id, spec, model, selected)
                    path = temp / "docs" / spec.path
                    atomic_write_text(path, body)
                    generated_headings = self._headings(path)
                    missing_sections = [heading for heading in spec.required_sections if heading not in generated_headings]
                    if missing_sections:
                        raise TUnderstandError("DOC-SECTION-001", f"{spec.document_id} missed required sections: {', '.join(missing_sections)}")
                    model_record_ids = sorted({record_id for _, record_ids in document_sections for record_id in record_ids})
                    covered.update(model_record_ids)
                    for section, record_ids in document_sections:
                        self.contracts.validate("documentation-section", section)
                        sections.append(section)
                        trace = {
                            "schema_id": "https://t-understand.dev/schemas/documentation-trace.schema.json", "schema_version": "1.0.0",
                            "docset_id": docset_id, "document_id": spec.document_id, "section_id": section["section_id"],
                            "model_record_ids": record_ids, "claim_ids": section["claims"], "evidence_ids": section["evidence"],
                            "generated_at": utc_now(),
                        }
                        self.contracts.validate("documentation-trace", trace)
                        traces.append(trace)
                    document = {
                        "document_id": spec.document_id, "path": f"docs/{spec.path}", "audience": spec.audience,
                        "sha256": sha256_file(path), "sections": len(document_sections),
                    }
                    documents.append(document)
                    item = {
                        "schema_id": "https://t-understand.dev/schemas/documentation-generation-record.schema.json", "schema_version": "1.0.0",
                        "docset_id": docset_id, "requirement_id": spec.requirement_id, "document_id": spec.document_id,
                        "path": f"docs/{spec.path}", "status": "GENERATED", "required_sections": list(spec.required_sections),
                        "generated_sections": generated_headings, "model_record_ids": model_record_ids, "sha256": document["sha256"],
                        "generated_at": utc_now(),
                    }
                    self.contracts.validate("documentation-generation-record", item)
                    generation.append(item)

                atomic_write_text(temp / "sections.jsonl", _jsonl(sections))
                atomic_write_text(temp / "traceability.jsonl", _jsonl(traces))
                atomic_write_text(temp / "generation-ledger.jsonl", _jsonl(generation))
                ledger = self._coverage_ledger(docset_id, specs, generation, model_docs, covered, all_record_ids)
                self.contracts.validate("coverage-ledger", ledger)
                atomic_write_yaml(temp / "coverage-ledger.yaml", ledger)

                artifact_sources = (
                    ("documentation-requirements", temp / "documentation-requirements.yaml", len(requirements["requirements"])),
                    ("document-plan", temp / "document-plan.yaml", len(plan["documents"])),
                    ("information-architecture", temp / "information-architecture.yaml", len(info["navigation"])),
                    ("sections", temp / "sections.jsonl", len(sections)),
                    ("traceability", temp / "traceability.jsonl", len(traces)),
                    ("generation-ledger", temp / "generation-ledger.jsonl", len(generation)),
                    ("coverage-ledger", temp / "coverage-ledger.yaml", 1),
                )
                refs = {name: {"path": path.relative_to(temp).as_posix(), "sha256": sha256_file(path), "records": count} for name, path, count in artifact_sources}
                supported = [section for section in sections if section["classification"] not in {"LIMITATION", "UNKNOWN_INTENT"}]
                traced = sum(1 for section in supported if section["claims"] and section["evidence"])
                inferences = [section for section in sections if section["classification"] == "BUSINESS_INFERENCE"]
                disclosed = sum(1 for section in inferences if section.get("limitations"))
                quality = {
                    "section_traceability": round(traced / len(supported), 6) if supported else 1.0,
                    "unsupported_sections": sum(1 for section in supported if not section["claims"] or not section["evidence"]),
                    "stale_sections": sum(1 for section in sections if section["freshness"] == "stale"),
                    "catalog_coverage": ledger["requirement_coverage"],
                    "requirement_coverage": ledger["requirement_coverage"],
                    "model_record_coverage": ledger["coverage"],
                    "required_section_coverage": ledger["section_coverage"],
                    "repository_coverage": ledger["repository_coverage"],
                    "flow_coverage": ledger["flow_coverage"],
                    "inference_disclosure": round(disclosed / len(inferences), 6) if inferences else 1.0,
                }
                base = {
                    "schema_id": "https://t-understand.dev/schemas/documentation-manifest.schema.json", "schema_version": "1.0.0",
                    "docset_id": docset_id, "application_id": model["application_id"], "snapshot_id": model["snapshot_id"],
                    "memory_id": model["memory_id"], "model_id": model_id, "status": status, "artifacts": refs,
                    "documents": documents, "quality": quality, "generated_at": utc_now(),
                }
                manifest = {**base, "content_digest": _canonical_digest(base)}
                self.contracts.validate("documentation-manifest", manifest)
                atomic_write_yaml(temp / "documentation-manifest.yaml", manifest)
                os.replace(temp, final)
                verification = self.validate(docset_id)
                critique = self.critique(docset_id)
                if verification["status"] != "PASS" or critique["status"] != "PASS":
                    raise TUnderstandError("DOC-VERIFY-001", "Generated documentation failed validation or critique")
                self._publish_user_view(docset_id)
                if self.validate_user_view()["status"] != "PASS":
                    raise TUnderstandError("DOC-VIEW-001", "Generated user-facing documentation view failed validation")
                if make_current:
                    atomic_write_yaml(self.root / "current.yaml", {
                        "docset_id": docset_id, "model_id": model_id, "snapshot_id": model["snapshot_id"],
                        "manifest_sha256": sha256_file(final / "documentation-manifest.yaml"), "updated_at": utc_now(),
                    })
            except Exception:
                shutil.rmtree(temp, ignore_errors=True)
                if final.exists():
                    shutil.rmtree(final, ignore_errors=True)
                raise
        return self.show(docset_id)

    @staticmethod
    def _information_architecture(docset_id: str, application_id: str, specs: list[DocumentSpec]) -> dict[str, Any]:
        groups: dict[str, list[str]] = defaultdict(list)
        labels = {
            "application": "Application", "business": "Business", "domain": "Domain", "flows": "Flows",
            "repositories": "Repositories", "integrations": "Integrations", "data": "Data", "operations": "Operations", "reference": "Reference",
        }
        for spec in specs:
            groups[spec.category].append(spec.path.removesuffix(".md"))
        return {
            "docset_id": docset_id, "title": f"{application_id} documentation",
            "navigation": [{"group": labels[category], "pages": pages} for category, pages in groups.items()],
            "generated_at": utc_now(),
        }

    def _coverage_ledger(self, docset_id, specs, generation, model_docs, covered, all_record_ids):
        expected_by_category = Counter(spec.category for spec in specs)
        generated_by_category = Counter(self._category_for_path(item["path"].removeprefix("docs/")) for item in generation)
        category_coverage = {
            category: {
                "expected": expected, "generated": generated_by_category.get(category, 0),
                "coverage": round(generated_by_category.get(category, 0) / expected, 6) if expected else 1.0,
            }
            for category, expected in expected_by_category.items()
        }
        required_sections = sum(len(spec.required_sections) for spec in specs)
        generated_sections = sum(len(set(item["required_sections"]) & set(item["generated_sections"])) for item in generation)
        repositories = {spec.scope["repository_id"] for spec in specs if spec.scope and spec.scope.get("repository_id")}
        generated_repositories = {spec.scope["repository_id"] for spec in specs if spec.scope and spec.scope.get("repository_id") and any(item["requirement_id"] == spec.requirement_id for item in generation)}
        flow_records = {record["id"] for record in model_docs["flows"]["records"]}
        documented_flow_records = flow_records & covered
        business_types = ("business-goals", "business-capabilities", "business-processes", "actors", "business-rules", "policies-decisions", "controls-compliance")
        domain_types = ("domain-overview", "bounded-contexts", "aggregates-entities", "value-objects", "invariants", "domain-services", "commands", "domain-events", "state-model", "decision-tables", "ownership-boundaries")

        def scoped(model_types):
            ids = {record["id"] for model_type in model_types for record in model_docs[model_type]["records"]}
            return {"total": len(ids), "documented": len(ids & covered), "coverage": round(len(ids & covered) / len(ids), 6) if ids else 1.0}

        return {
            "schema_id": "https://t-understand.dev/schemas/coverage-ledger.schema.json", "schema_version": "1.0.0",
            "docset_id": docset_id, "expected_documents": len(specs), "generated_documents": len(generation),
            "covered_model_records": len(covered), "total_model_records": len(all_record_ids),
            "coverage": round(len(covered) / len(all_record_ids), 6) if all_record_ids else 1.0,
            "gaps": sorted(all_record_ids - covered),
            "requirement_coverage": round(len(generation) / len(specs), 6) if specs else 1.0,
            "section_coverage": round(generated_sections / required_sections, 6) if required_sections else 1.0,
            "repository_coverage": round(len(generated_repositories) / len(repositories), 6) if repositories else 1.0,
            "flow_coverage": round(len(documented_flow_records) / len(flow_records), 6) if flow_records else 1.0,
            "category_coverage": category_coverage,
            "business_coverage": scoped(business_types), "domain_coverage": scoped(domain_types),
            "flow_detail": {
                "discovered": len(flow_records), "documented": len(documented_flow_records),
                "tier_1": sum(1 for record in model_docs["flows"]["records"] if record.get("attributes", {}).get("tier") == "TIER_1"),
                "tier_2": sum(1 for record in model_docs["flows"]["records"] if record.get("attributes", {}).get("tier") == "TIER_2"),
                "tier_3": sum(1 for record in model_docs["flows"]["records"] if record.get("attributes", {}).get("tier", "TIER_3") == "TIER_3"),
            },
            "generated_at": utc_now(),
        }

    @staticmethod
    def _category_for_path(path: str) -> str:
        if path == "index.md":
            return "application"
        return next((value for prefix, value in CATEGORY_BY_PREFIX.items() if path.startswith(prefix)), "reference")

    def _render_document(self, docset_id: str, spec: DocumentSpec, model: dict[str, Any], records: list[dict[str, Any]]):
        if spec.generation_mode in {"deep-flow", "standard-flow"}:
            return self._render_flow_document(docset_id, spec, model, records)
        return self._render_catalog_document(docset_id, spec, model, records)

    def _frontmatter(self, docset_id, spec, model, title):
        return [
            "---", f"title: {title}", f"document_id: {spec.document_id}", f"requirement_id: {spec.requirement_id}",
            f"docset_id: {docset_id}", f"snapshot_id: {model['snapshot_id']}", f"memory_id: {model['memory_id']}",
            f"model_id: {model['model_id']}", f"audience: {spec.audience}", f"category: {spec.category}", "---", "", f"# {title}", "",
            f"> Generated from immutable model `{model['model_id']}` and snapshot `{model['snapshot_id']}`. Facts, implementation-derived behavior, inference, unknowns, and conflicts remain explicitly classified.", "",
        ]

    def _render_catalog_document(self, docset_id, spec, model, records):
        title = spec.document_id.replace("-", " ").title()
        lines = self._frontmatter(docset_id, spec, model, title)
        lines += ["## Purpose and scope", "", self._purpose(spec), ""]
        counts = Counter(record["classification"] for record in records)
        lines += ["## Coverage summary", "", f"This document covers **{len(records)}** model record(s) for the declared scope.", "", "| Classification | Records |", "|---|---:|"]
        for classification in ("FACT", "IMPLEMENTED_BEHAVIOR", "BUSINESS_INFERENCE", "HUMAN_CONFIRMED", "UNKNOWN", "CONFLICT", "LIMITATION"):
            lines.append(f"| `{classification}` | {counts.get(classification, 0)} |")
        lines += ["", "## Evidenced findings", ""]
        sections: list[tuple[dict[str, Any], list[str]]] = []
        if not records:
            limitation = self._limitation_section(spec, model, "No model record matched this document scope. The document is retained so the expected knowledge area cannot disappear silently.")
            lines += ["### Coverage limitation", "", limitation[0]["content"], "", "> Limitation: Additional source evidence or human confirmation is required.", ""]
            sections.append(limitation)
        else:
            for index, record in enumerate(records, 1):
                section = self._section_from_record(spec, model, record, index)
                lines += self._record_markdown(record)
                sections.append((section, [record["id"]]))
        lines += ["## Evidence and traceability", "", "Every evidenced section is linked to immutable model records, claims, and source evidence in `_meta/traceability.jsonl`. Model-record and document-requirement coverage are enforced by the release gate.", ""]
        lines += ["## Unknowns and limitations", ""]
        limitations = sorted({limitation for record in records for limitation in record.get("limitations", [])})
        if limitations:
            lines += [f"- {limitation}" for limitation in limitations]
        else:
            lines += ["- No additional limitation was recorded beyond the evidence classification and captured snapshot boundary."]
        lines += ["", "The documentation does not claim runtime behavior, business intent, ownership, test success, or operational guarantees that are absent from evidence.", ""]
        return "\n".join(lines), sections

    def _render_flow_document(self, docset_id, spec, model, records):
        flow = records[0] if records else None
        title = flow["title"] if flow else spec.document_id.replace("-", " ").title()
        attributes = flow.get("attributes", {}) if flow else {}
        lines = self._frontmatter(docset_id, spec, model, title)
        sections: list[tuple[dict[str, Any], list[str]]] = []
        for index, heading in enumerate(spec.required_sections, 1):
            content = self._flow_section_content(heading, flow, attributes)
            lines += [f"## {heading}", "", content, ""]
            if heading == "Sequence and interactions" and attributes.get("steps"):
                lines += self._sequence_markdown(attributes["steps"])
            if flow:
                section = self._section_from_record(spec, model, flow, index, title=heading, content=content)
                sections.append((section, [flow["id"]]))
            else:
                sections.append(self._limitation_section(spec, model, content, index, heading))
        return "\n".join(lines), sections

    def _flow_section_content(self, heading, flow, attributes):
        if not flow:
            return "No flow model record matched this planned document. The required document remains visible and is classified as a limitation."
        repositories = attributes.get("repositories", [])
        steps = attributes.get("steps", [])
        mapping = {
            "Purpose and scope": f"This document describes the `{attributes.get('flow_type', 'APPLICATION_FLOW')}` `{attributes.get('flow_key', flow['title'])}` at `{attributes.get('tier', 'TIER_3')}` depth. It is reconstructed from source evidence rather than runtime observation.",
            "Business and application intent": "The implementation establishes this interaction, but the business goal, success metric, and product-owner intent remain unknown unless separately evidenced.",
            "Trigger and preconditions": f"Observed trigger or contract: `{attributes.get('trigger', attributes.get('flow_key', 'unknown'))}`. Preconditions not encoded in the captured model remain unknown.",
            "Participants and repositories": f"Participating repositories: {', '.join(repositories) if repositories else 'not resolved'}. Human actors and external organizations require explicit evidence.",
            "Sequence and interactions": f"The model contains {len(steps)} ordered interaction step(s). Ordering reflects deterministic source-model ordering, not a claim of runtime timing where execution evidence is absent.",
            "Synchronous and asynchronous boundaries": "The interaction is reconstructed as synchronous." if attributes.get("synchronous", True) else "The interaction includes asynchronous event publication or consumption boundaries.",
            "State and data impact": f"State impacts: {', '.join(attributes.get('state_impact', [])) or 'not proven'}. Data impacts: {', '.join(attributes.get('data_impact', [])) or 'not proven'}.",
            "Transactions and consistency": f"Observed local transaction boundaries: {', '.join(attributes.get('transaction_boundaries', [])) or 'none proven'}. Cross-repository atomicity, eventual consistency, idempotency, and reconciliation are not assumed.",
            "Alternatives, failures, and recovery": f"Observed failure candidates: {', '.join(attributes.get('failure_candidates', [])) or 'none proven'}. Alternative paths and user-visible outcomes require direct branch or test evidence.",
            "Retry, compensation, and reconciliation": "No retry, compensation, or reconciliation guarantee is claimed unless it appears in the evidence-backed attributes and related failure model.",
            "Security": f"Observed security surfaces: {', '.join(attributes.get('security_surfaces', [])) or 'none proven'}. Authentication, authorization, data classification, and policy ownership require direct evidence.",
            "Observability and operations": f"Observed observability surfaces: {', '.join(attributes.get('observability', [])) or 'none proven'}. Logs, metrics, traces, alerts, SLOs, and runbooks are not invented.",
            "Evidence and traceability": f"Primary model record: `{flow['id']}`. Claims: {', '.join(flow.get('claim_ids', [])) or 'none'}. Evidence: {', '.join(flow.get('evidence_ids', [])) or 'none'}.",
            "Unknowns and limitations": "Runtime timing, complete preconditions, business ownership, postconditions, SLAs, unobserved branches, and operational recovery remain unknown unless separately evidenced.",
        }
        return mapping.get(heading, "This required perspective is retained, but no more specific evidence-backed statement is available.")

    @staticmethod
    def _sequence_markdown(steps):
        lines = ["| Step | Source | Action | Target | Contract |", "|---:|---|---|---|---|"]
        for step in steps:
            lines.append(f"| {step.get('order')} | {step.get('source') or 'unknown'} | `{step.get('action')}` | {step.get('target') or 'unknown'} | `{step.get('contract') or 'unknown'}` |")
        participants = []
        for step in steps:
            for value in (step.get("source"), step.get("target")):
                if value and value not in participants and re.fullmatch(r"[A-Za-z0-9_.-]+", str(value)):
                    participants.append(str(value))
        if participants:
            aliases = {value: f"P{index}" for index, value in enumerate(participants, 1)}
            lines += ["", "```mermaid", "sequenceDiagram"]
            for value in participants:
                lines.append(f"    participant {aliases[value]} as {value}")
            for step in steps:
                source, target = str(step.get("source") or ""), str(step.get("target") or "")
                if source in aliases and target in aliases:
                    arrow = "-->>" if step.get("action") in {"PRODUCES", "CONSUMES", "PRODUCES_FOR"} else "->>"
                    lines.append(f"    {aliases[source]}{arrow}{aliases[target]}: {step.get('action')} {step.get('contract') or ''}")
            lines += ["```", ""]
        return lines + [""]

    @staticmethod
    def _purpose(spec):
        scope = spec.scope or {}
        if repository := scope.get("repository_id"):
            return f"This document provides the `{spec.document_id}` perspective for repository `{repository}` and excludes unrelated repository records."
        if flow := scope.get("flow_key"):
            return f"This document provides an evidence-backed perspective for application flow `{flow}`."
        return f"This document covers the `{spec.category}` knowledge area using model types: {', '.join(spec.source_models)}."

    @staticmethod
    def _classification(value):
        return {
            "FACT": "TECHNICAL_FACT", "IMPLEMENTED_BEHAVIOR": "IMPLEMENTED_BEHAVIOR", "BUSINESS_INFERENCE": "BUSINESS_INFERENCE",
            "HUMAN_CONFIRMED": "HUMAN_CONFIRMED_RULE", "UNKNOWN": "UNKNOWN_INTENT", "CONFLICT": "LIMITATION", "LIMITATION": "LIMITATION",
        }[value]

    @staticmethod
    def _substantive_section_content(content: str, classification: str) -> str:
        value = content.strip()
        if len(value) >= 30:
            return value
        boundary = {
            "TECHNICAL_FACT": "This fact is limited to the immutable source evidence captured for the analyzed snapshot.",
            "IMPLEMENTED_BEHAVIOR": "This behavior is reconstructed from implementation evidence and is not a claim of observed runtime execution.",
            "BUSINESS_INFERENCE": "This interpretation is implementation-derived and requires confirmation from an authoritative business or domain source.",
            "HUMAN_CONFIRMED_RULE": "This rule remains scoped to the recorded confirmation and its cited evidence.",
            "UNKNOWN_INTENT": "This knowledge area remains explicitly unknown until additional source evidence or human confirmation is available.",
            "LIMITATION": "The limitation is retained explicitly so the missing knowledge cannot disappear from documentation coverage.",
        }[classification]
        return f"{value} {boundary}".strip()

    def _section_from_record(self, spec, model, record, index, title=None, content=None):
        classification = self._classification(record["classification"])
        section_content = self._substantive_section_content(content or record["description"], classification)
        return {
            "schema_id": "https://t-understand.dev/schemas/documentation-section.schema.json", "schema_version": "1.0.0",
            "document_id": spec.document_id, "section_id": f"{spec.document_id}-s{index:04d}",
            "title": title or record["title"], "classification": classification, "application_snapshot": model["snapshot_id"],
            "content": section_content, "claims": record.get("claim_ids", []), "evidence": record.get("evidence_ids", []),
            "freshness": "stale" if record.get("freshness") == "stale" else "current",
            "coverage": "partial" if classification in {"UNKNOWN_INTENT", "LIMITATION"} else "complete-for-declared-scope",
            "limitations": record.get("limitations", []),
        }

    def _limitation_section(self, spec, model, content, index=1, title="Coverage limitation"):
        return ({
            "schema_id": "https://t-understand.dev/schemas/documentation-section.schema.json", "schema_version": "1.0.0",
            "document_id": spec.document_id, "section_id": f"{spec.document_id}-s{index:04d}", "title": title,
            "classification": "LIMITATION", "application_snapshot": model["snapshot_id"], "content": content,
            "claims": [], "evidence": [], "freshness": "current", "coverage": "partial",
            "limitations": ["Additional source evidence or human confirmation is required."],
        }, [])

    def _record_markdown(self, record):
        classification = self._classification(record["classification"])
        lines = [f"### {record['title']}", "", f"**Classification:** `{classification}`", "", record["description"], ""]
        attributes = record.get("attributes", {})
        if attributes:
            lines += ["**Structured details:**", "", "```yaml", self._yaml_fragment(attributes).rstrip(), "```", ""]
        lines += [f"**Traceability:** model record `{record['id']}`; claims `{', '.join(record.get('claim_ids', [])) or 'none'}`; evidence `{', '.join(record.get('evidence_ids', [])) or 'none'}`.", ""]
        for limitation in record.get("limitations", []):
            lines += [f"> Limitation: {limitation}", ""]
        return lines

    @staticmethod
    def _yaml_fragment(value):
        import yaml
        return yaml.safe_dump(value, sort_keys=True, allow_unicode=True)

    @staticmethod
    def _headings(path: Path) -> list[str]:
        return [match.group(1).strip() for match in re.finditer(r"^##\s+(.+?)\s*$", path.read_text(encoding="utf-8"), re.MULTILINE)]

    def _publish_user_view(self, docset_id: str) -> None:
        source = self._dir(docset_id)
        self.user_output_root.mkdir(parents=True, exist_ok=True)
        temp = self.user_output_root / f".latest.{uuid.uuid4().hex}.tmp"
        backup = self.user_output_root / f".latest.{uuid.uuid4().hex}.backup"
        try:
            shutil.copytree(source / "docs", temp)
            meta = temp / "_meta"
            meta.mkdir(parents=True, exist_ok=True)
            mapping = {
                "documentation-manifest.yaml": "manifest.yaml", "documentation-requirements.yaml": "requirements.yaml",
                "document-plan.yaml": "document-plan.yaml", "information-architecture.yaml": "information-architecture.yaml",
                "coverage-ledger.yaml": "coverage-ledger.yaml", "sections.jsonl": "sections.jsonl",
                "traceability.jsonl": "traceability.jsonl", "generation-ledger.jsonl": "generation-ledger.jsonl",
            }
            for source_name, target_name in mapping.items():
                shutil.copy2(source / source_name, meta / target_name)
            reports = self.reports_root / docset_id
            shutil.copy2(reports / "verification.yaml", meta / "validation.yaml")
            shutil.copy2(reports / "critique.yaml", meta / "critique.yaml")
            files = [{"path": path.relative_to(temp).as_posix(), "sha256": sha256_file(path)} for path in sorted(item for item in temp.rglob("*") if item.is_file())]
            atomic_write_yaml(meta / "user-view.yaml", {
                "docset_id": docset_id, "entrypoint": "index.md",
                "documents": len([item for item in files if item["path"].endswith(".md") and not item["path"].startswith("_meta/")]),
                "files": files, "generated_at": utc_now(),
            })
            if self.latest_output.exists():
                os.replace(self.latest_output, backup)
            os.replace(temp, self.latest_output)
            shutil.rmtree(backup, ignore_errors=True)
        except Exception:
            shutil.rmtree(temp, ignore_errors=True)
            if backup.exists() and not self.latest_output.exists():
                os.replace(backup, self.latest_output)
            raise

    def validate_user_view(self) -> dict[str, Any]:
        errors: list[str] = []
        checks = 0
        required = (
            "index.md", "business/goals-and-outcomes.md", "domain/overview.md", "flows/flow-catalog.md",
            "_meta/manifest.yaml", "_meta/requirements.yaml", "_meta/document-plan.yaml", "_meta/coverage-ledger.yaml",
            "_meta/traceability.jsonl", "_meta/generation-ledger.jsonl", "_meta/validation.yaml", "_meta/critique.yaml", "_meta/user-view.yaml",
        )
        for relative in required:
            checks += 1
            if not (self.latest_output / relative).is_file():
                errors.append(f"missing user-facing documentation artifact: {relative}")
        if not errors:
            view = load_yaml(self.latest_output / "_meta/user-view.yaml")
            ledger = load_yaml(self.latest_output / "_meta/coverage-ledger.yaml")
            checks += 7
            if view.get("documents", 0) < len(DOCUMENT_CATALOG):
                errors.append("user-facing view contains fewer documents than the mandatory base catalog")
            for metric in ("coverage", "requirement_coverage", "section_coverage", "repository_coverage", "flow_coverage"):
                if ledger.get(metric) != 1.0:
                    errors.append(f"user-facing documentation {metric} is not complete")
            for item in view.get("files", []):
                checks += 1
                path = self.latest_output / item["path"]
                if not path.is_file() or sha256_file(path) != item["sha256"]:
                    errors.append(f"user-facing documentation checksum mismatch: {item['path']}")
        return {"status": "PASS" if not errors else "FAIL", "checks": checks, "errors": errors}

    def show(self, docset_id):
        return load_yaml(self._dir(docset_id) / "documentation-manifest.yaml")

    def list(self):
        current = load_yaml(self.root / "current.yaml") if (self.root / "current.yaml").exists() else None
        values = []
        if self.root.exists():
            for path in sorted(self.root.iterdir()):
                if path.is_dir() and (path / "documentation-manifest.yaml").exists():
                    values.append(self.show(path.name))
        return {"current": current, "docsets": values}

    def _jsonl(self, docset_id, name):
        return [json.loads(line) for line in (self._dir(docset_id) / name).read_text().splitlines() if line]

    def validate(self, docset_id):
        errors: list[str] = []
        checks = 0
        try:
            manifest = self.show(docset_id)
            self.contracts.validate("documentation-manifest", manifest)
            checks += 1
            if _canonical_digest({key: value for key, value in manifest.items() if key != "content_digest"}) != manifest["content_digest"]:
                errors.append("documentation manifest digest mismatch")
            root = self._dir(docset_id)
            for name, meta in manifest["artifacts"].items():
                path = root / meta["path"]
                checks += 2
                if not path.is_file() or sha256_file(path) != meta["sha256"]:
                    errors.append(f"{name} checksum mismatch")
            requirements = load_yaml(root / "documentation-requirements.yaml")
            self.contracts.validate("documentation-requirements", requirements)
            plan = load_yaml(root / "document-plan.yaml")
            self.contracts.validate("document-plan", plan)
            requirement_by_id = {item["requirement_id"]: item for item in requirements["requirements"]}
            generation = self._jsonl(docset_id, "generation-ledger.jsonl")
            generated_by_requirement = {}
            for item in generation:
                self.contracts.validate("documentation-generation-record", item)
                checks += 1
                generated_by_requirement[item["requirement_id"]] = item
            if set(requirement_by_id) != set(generated_by_requirement):
                errors.append("planned/generated documentation requirement sets differ")
            sections = self._jsonl(docset_id, "sections.jsonl")
            traces = self._jsonl(docset_id, "traceability.jsonl")
            trace_keys = {(trace["document_id"], trace["section_id"]) for trace in traces}
            for section in sections:
                self.contracts.validate("documentation-section", section)
                checks += 1
                if (section["document_id"], section["section_id"]) not in trace_keys:
                    errors.append(f"{section['section_id']} missing trace")
                if section["classification"] in {"TECHNICAL_FACT", "IMPLEMENTED_BEHAVIOR", "BUSINESS_INFERENCE", "HUMAN_CONFIRMED_RULE"} and (not section["claims"] or not section["evidence"]):
                    errors.append(f"{section['section_id']} unsupported")
            for trace in traces:
                self.contracts.validate("documentation-trace", trace)
                checks += 1
            document_by_id = {document["document_id"]: document for document in manifest["documents"]}
            if set(document_by_id) != {item["document_id"] for item in requirements["requirements"]}:
                errors.append("manifest document set differs from requirements")
            for document in manifest["documents"]:
                path = root / document["path"]
                checks += 1
                if not path.is_file() or sha256_file(path) != document["sha256"]:
                    errors.append(f"{document['document_id']} checksum mismatch")
                if self._broken_links(path):
                    errors.append(f"{document['document_id']} contains broken relative links")
                requirement = next(item for item in requirements["requirements"] if item["document_id"] == document["document_id"])
                headings = self._headings(path)
                missing = sorted(set(requirement["required_sections"]) - set(headings))
                if missing:
                    errors.append(f"{document['document_id']} missing required sections: {missing}")
            ledger = load_yaml(root / "coverage-ledger.yaml")
            self.contracts.validate("coverage-ledger", ledger)
            checks += 6
            for metric in ("coverage", "requirement_coverage", "section_coverage", "repository_coverage", "flow_coverage"):
                if ledger.get(metric) != 1.0:
                    errors.append(f"{metric} must be 1.0")
            if ledger.get("gaps"):
                errors.append("coverage ledger contains undocumented model records")
        except Exception as exc:
            errors.append(str(exc))
        report = {
            "schema_id": "https://t-understand.dev/schemas/documentation-verification.schema.json", "schema_version": "1.0.0",
            "id": docset_id, "status": "PASS" if not errors else "FAIL", "checks": checks, "errors": errors, "generated_at": utc_now(),
        }
        self.contracts.validate("documentation-verification", report)
        atomic_write_yaml(self.reports_root / docset_id / "verification.yaml", report)
        return report

    def critique(self, docset_id):
        issues: list[dict[str, Any]] = []
        checks = 0
        manifest = self.show(docset_id)
        root = self._dir(docset_id)
        sections = self._jsonl(docset_id, "sections.jsonl")
        generation = self._jsonl(docset_id, "generation-ledger.jsonl")
        for section in sections:
            checks += 1
            if section["classification"] == "BUSINESS_INFERENCE" and not section.get("limitations"):
                issues.append({"code": "DOC-INFERENCE-DISCLOSURE", "severity": "BLOCKER", "section_id": section["section_id"]})
            if section["freshness"] != "current":
                issues.append({"code": "DOC-STALE", "severity": "BLOCKER", "section_id": section["section_id"]})
            if section["classification"] in {"TECHNICAL_FACT", "IMPLEMENTED_BEHAVIOR"} and not section["evidence"]:
                issues.append({"code": "DOC-UNSUPPORTED", "severity": "BLOCKER", "section_id": section["section_id"]})
            if len(section["content"].strip()) < 30:
                issues.append({"code": "DOC-SHALLOW-SECTION", "severity": "MAJOR", "section_id": section["section_id"]})
        hashes: dict[str, list[str]] = defaultdict(list)
        for item in generation:
            checks += 1
            missing = sorted(set(item["required_sections"]) - set(item["generated_sections"]))
            if missing:
                issues.append({"code": "DOC-MISSING-SECTION", "severity": "BLOCKER", "document_id": item["document_id"], "missing": missing})
            path = root / item["path"]
            text = path.read_text(encoding="utf-8")
            if len(text) < (350 if "/flows/" in f"/{item['path']}" else 250):
                issues.append({"code": "DOC-SHALLOW-DOCUMENT", "severity": "MAJOR", "document_id": item["document_id"]})
            if re.search(r"\b(?:TODO|TBD|FIXME|lorem ipsum)\b|<[^>]+placeholder[^>]*>", text, re.IGNORECASE):
                issues.append({"code": "DOC-PLACEHOLDER", "severity": "BLOCKER", "document_id": item["document_id"]})
            hashes[item["sha256"]].append(item["document_id"])
        for digest, document_ids in hashes.items():
            if len(document_ids) > 1:
                issues.append({"code": "DOC-DUPLICATE-CONTENT", "severity": "MAJOR", "documents": document_ids})
        quality = manifest["quality"]
        for metric in ("catalog_coverage", "requirement_coverage", "model_record_coverage", "required_section_coverage", "repository_coverage", "flow_coverage", "inference_disclosure", "section_traceability"):
            if quality.get(metric) != 1.0:
                issues.append({"code": "DOC-QUALITY-COVERAGE", "severity": "BLOCKER", "metric": metric, "value": quality.get(metric)})
        if quality["unsupported_sections"]:
            issues.append({"code": "DOC-UNSUPPORTED-COUNT", "severity": "BLOCKER", "count": quality["unsupported_sections"]})
        report = {
            "schema_id": "https://t-understand.dev/schemas/documentation-critique.schema.json", "schema_version": "1.0.0",
            "id": docset_id, "status": "PASS" if not issues else "FAIL", "checks": checks, "issues": issues, "generated_at": utc_now(),
        }
        self.contracts.validate("documentation-critique", report)
        atomic_write_yaml(self.reports_root / docset_id / "critique.yaml", report)
        return report

    def invalidate(self, invalidation_id, docset_id, memory_invalidation_id):
        if not ID_RE.fullmatch(invalidation_id):
            raise TUnderstandError("DOC-INV-001", "Invalid invalidation ID")
        target = self.invalidations_root / f"{invalidation_id}.yaml"
        if target.exists():
            raise TUnderstandError("DOC-INV-002", "Document invalidation already exists")
        invalidation = load_yaml(self.context_root / "memory" / "invalidations" / f"{memory_invalidation_id}.yaml")
        affected_claims = set(invalidation.get("affected_claims", []))
        affected_sections = []
        affected_documents = set()
        for section in self._jsonl(docset_id, "sections.jsonl"):
            if set(section["claims"]) & affected_claims:
                affected_sections.append(section["section_id"])
                affected_documents.add(section["document_id"])
        report = {
            "schema_id": "https://t-understand.dev/schemas/document-invalidation.schema.json", "schema_version": "1.0.0",
            "invalidation_id": invalidation_id, "docset_id": docset_id, "memory_invalidation_id": memory_invalidation_id,
            "status": "INVALIDATED" if affected_sections else "UNCHANGED", "affected_documents": sorted(affected_documents),
            "affected_sections": sorted(affected_sections), "generated_at": utc_now(),
        }
        self.contracts.validate("document-invalidation", report)
        atomic_write_yaml(target, report)
        return report

    @staticmethod
    def _broken_links(path: Path):
        text = path.read_text(encoding="utf-8")
        broken = []
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target = target.split("#", 1)[0]
            if target and not (path.parent / target).resolve().exists():
                broken.append(target)
        return broken
