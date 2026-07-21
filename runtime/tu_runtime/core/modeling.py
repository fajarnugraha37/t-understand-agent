from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .analysis import ID_RE
from .contracts import ContractValidator
from .discovery import _canonical_digest
from .errors import TUnderstandError
from .io import atomic_write_text, atomic_write_yaml, load_yaml, sha256_file, utc_now
from .memory import MemoryManager


def _id(prefix: str, *parts: Any) -> str:
    raw = "\x1f".join(str(x) for x in parts).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(raw).hexdigest()[:16].upper()}"


def _jsonl(values: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n" for x in values)


MODEL_TYPES = (
    "application-model",
    "architecture-model",
    "repository-model",
    "dependency-model",
    "data-model",
    "event-model",
    "deployment-model",
    "security-model",
    "observability-model",
    "business-goals",
    "business-capabilities",
    "business-processes",
    "actors",
    "business-rules",
    "policies-decisions",
    "controls-compliance",
    "domain-overview",
    "bounded-contexts",
    "aggregates-entities",
    "value-objects",
    "invariants",
    "domain-services",
    "commands",
    "domain-events",
    "state-model",
    "decision-tables",
    "ownership-boundaries",
    "flows",
    "flow-failures",
    "consistency-model",
    "terminology",
)

BUSINESS_VERBS = {
    "create", "submit", "approve", "reject", "cancel", "close", "open", "assign", "publish",
    "finalize", "review", "decide", "calculate", "price", "quote", "order", "pay", "triage",
    "investigate", "recommend", "sanction", "appeal", "fulfill", "activate", "suspend", "renew",
}


def _humanize(value: str) -> str:
    value = value.split(":")[-1].split("/")[-1]
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    value = re.sub(r"[^A-Za-z0-9]+", " ", value).strip()
    return " ".join(part.capitalize() for part in value.split()) or "Unnamed"


def _lower_words(value: str) -> set[str]:
    return {part.lower() for part in re.findall(r"[A-Za-z][A-Za-z0-9]*", _humanize(value))}


class ModelManager:
    def __init__(self, project_root: Path, context_root: Path):
        self.project_root = project_root
        self.context_root = context_root.resolve()
        self.memory = MemoryManager(project_root, context_root)
        self.contracts = ContractValidator(project_root)

    @property
    def root(self) -> Path:
        return self.context_root / "models"

    @property
    def versions_root(self) -> Path:
        return self.root / "versions"

    @property
    def reports_root(self) -> Path:
        return self.context_root / "reports" / "models"

    @contextmanager
    def lock(self) -> Iterator[None]:
        lock = self.context_root / "runtime" / "locks" / "models.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        try:
            lock.mkdir()
        except FileExistsError as exc:
            raise TUnderstandError("MOD-LOCK-001", "Model mutation is already active") from exc
        try:
            yield
        finally:
            lock.rmdir()

    def _dir(self, model_id: str) -> Path:
        if not ID_RE.fullmatch(model_id):
            raise TUnderstandError("MOD-ID-001", "model_id must match canonical ID pattern")
        return self.versions_root / model_id

    def build(self, model_id: str, memory_id: str, make_current: bool = True) -> dict[str, Any]:
        final = self._dir(model_id)
        if final.exists():
            raise TUnderstandError("MOD-ID-002", f"Model set already exists and is immutable: {model_id}")
        if self.memory.validate(memory_id)["status"] != "PASS":
            raise TUnderstandError("MOD-INPUT-001", f"Memory validation failed: {memory_id}")
        memory = self.memory.show(memory_id)
        evidence = self.memory._load_artifact(memory_id, "evidence")
        entities = self.memory._load_artifact(memory_id, "entities")
        relations = self.memory._load_artifact(memory_id, "relations")
        claims = self.memory._load_artifact(memory_id, "claims")
        conflicts = self.memory._load_artifact(memory_id, "conflicts")
        claim_by_entity, claim_by_relation = self._claim_maps(claims, entities, relations)
        artifacts = self._derive(model_id, memory, entities, relations, claims, conflicts, claim_by_entity, claim_by_relation)
        all_records = [r for doc in artifacts.values() for r in doc["records"]]
        trace = [{
            "schema_id": "https://t-understand.dev/schemas/model-trace.schema.json",
            "schema_version": "1.0.0", "model_id": model_id, "record_id": r["id"],
            "claim_ids": r["claim_ids"], "evidence_ids": r["evidence_ids"], "generated_at": utc_now(),
        } for r in all_records]
        for item in trace:
            self.contracts.validate("model-trace", item)
        unsupported = sum(1 for r in all_records if r["classification"] not in {"UNKNOWN", "LIMITATION"} and (not r["claim_ids"] or not r["evidence_ids"]))
        supported = len(all_records) - sum(1 for r in all_records if r["classification"] in {"UNKNOWN", "LIMITATION"})
        traced = sum(1 for r in all_records if r["classification"] in {"UNKNOWN", "LIMITATION"} or (r["claim_ids"] and r["evidence_ids"]))
        status = "CONFLICTED" if conflicts else memory["status"]
        with self.lock():
            temp = self.versions_root / f".{model_id}.{uuid.uuid4().hex}.tmp"
            temp.mkdir(parents=True)
            try:
                refs: dict[str, dict[str, Any]] = {}
                for name in MODEL_TYPES:
                    doc = artifacts[name]
                    base = {**doc, "generated_at": utc_now()}
                    doc = {**base, "content_digest": _canonical_digest(base)}
                    self.contracts.validate("model-artifact", doc)
                    for record in doc["records"]:
                        self.contracts.validate("model-record", record)
                    path = temp / f"{name}.yaml"
                    atomic_write_yaml(path, doc)
                    refs[name] = {"path": path.name, "sha256": sha256_file(path), "records": len(doc["records"])}
                trace_path = temp / "traceability.jsonl"
                atomic_write_text(trace_path, _jsonl(trace))
                refs["traceability"] = {"path": trace_path.name, "sha256": sha256_file(trace_path), "records": len(trace)}
                counts = {name: len(artifacts[name]["records"]) for name in MODEL_TYPES}
                base = {
                    "schema_id": "https://t-understand.dev/schemas/model-manifest.schema.json", "schema_version": "1.0.0",
                    "model_id": model_id, "application_id": memory["application_id"], "snapshot_id": memory["snapshot_id"],
                    "memory_id": memory_id, "status": status, "artifacts": refs, "counts": counts,
                    "quality": {"traceability_coverage": round(traced / len(all_records), 6) if all_records else 1.0,
                                "unsupported_records": unsupported,
                                "unknown_areas": sum(1 for r in all_records if r["classification"] in {"UNKNOWN", "LIMITATION"}),
                                "conflicts": len(conflicts)},
                    "generated_at": utc_now(),
                }
                manifest = {**base, "content_digest": _canonical_digest(base)}
                self.contracts.validate("model-manifest", manifest)
                atomic_write_yaml(temp / "model-manifest.yaml", manifest)
                os.replace(temp, final)
                verification = self.validate(model_id)
                critique = self.critique(model_id)
                if verification["status"] != "PASS" or critique["status"] != "PASS":
                    raise TUnderstandError("MOD-VERIFY-001", "Generated model set failed verification or critique")
                if make_current:
                    atomic_write_yaml(self.root / "current.yaml", {"model_id": model_id, "memory_id": memory_id,
                                      "snapshot_id": memory["snapshot_id"], "manifest_sha256": sha256_file(final / "model-manifest.yaml"),
                                      "updated_at": utc_now()})
            except Exception:
                shutil.rmtree(temp, ignore_errors=True)
                if final.exists():
                    shutil.rmtree(final, ignore_errors=True)
                raise
        return self.show(model_id)

    def _record(self, model_id: str, model_type: str, key: str, classification: str, title: str, description: str,
                claims: list[str], evidence: list[str], entities: list[str] | None = None,
                relations: list[str] | None = None, attributes: dict[str, Any] | None = None,
                limitations: list[str] | None = None) -> dict[str, Any]:
        return {
            "schema_id": "https://t-understand.dev/schemas/model-record.schema.json", "schema_version": "1.0.0",
            "id": _id("MODREC", model_type, key), "model_id": model_id, "model_type": model_type,
            "classification": classification, "title": title, "description": description,
            "claim_ids": sorted(set(claims)), "evidence_ids": sorted(set(evidence)),
            "source_entities": sorted(set(entities or [])), "source_relations": sorted(set(relations or [])),
            "attributes": attributes or {}, "freshness": "conflicted" if classification == "CONFLICT" else "current",
            **({"limitations": limitations} if limitations else {}),
        }

    @staticmethod
    def _claim_maps(claims, entities, relations):
        by_entity: dict[str, list[dict[str, Any]]] = defaultdict(list)
        by_relation: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for claim in claims:
            statement = claim.get("statement", "")
            for ent in entities:
                if ent["id"] in statement or ent["qualified_name"] in statement:
                    by_entity[ent["id"]].append(claim)
            for rel in relations:
                if rel["id"] in claim.get("reasoning", "") or (str(rel.get("source_entity")) in statement and str(rel.get("type")) in statement):
                    by_relation[rel["id"]].append(claim)
        return by_entity, by_relation

    def _support(self, entity_ids, relation_ids, claim_by_entity, claim_by_relation):
        cs=[]
        for eid in entity_ids: cs += claim_by_entity.get(eid, [])
        for rid in relation_ids: cs += claim_by_relation.get(rid, [])
        # fall back to any relation/entity evidence-bound claim discovered by IDs in statement
        claim_ids=sorted({c["id"] for c in cs})
        evidence=sorted({e for c in cs for e in c.get("evidence", [])})
        return claim_ids,evidence

    def _derive(self, model_id, memory, entities, relations, claims, conflicts, claim_by_entity, claim_by_relation):
        app = memory["application_id"]
        snap = memory["snapshot_id"]
        mid = memory["memory_id"]
        grouped: dict[str, list[dict[str, Any]]] = {name: [] for name in MODEL_TYPES}
        by_repo: dict[str, list[dict[str, Any]]] = defaultdict(list)
        by_path: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        entity_by_id = {entity["id"]: entity for entity in entities}
        for entity in entities:
            by_repo[entity["repository_id"]].append(entity)
            by_path[(entity["repository_id"], entity["path"])].append(entity)

        def support(entity_ids: list[str], relation_ids: list[str] | None = None, fallback: list[str] | None = None):
            claim_ids, evidence_ids = self._support(entity_ids, relation_ids or [], claim_by_entity, claim_by_relation)
            if fallback:
                evidence_ids = sorted(set(evidence_ids) | set(fallback))
            return claim_ids, evidence_ids

        def add(
            model_type: str,
            key: str,
            classification: str,
            title: str,
            description: str,
            entity_ids: list[str] | None = None,
            relation_ids: list[str] | None = None,
            attributes: dict[str, Any] | None = None,
            limitations: list[str] | None = None,
            fallback_evidence: list[str] | None = None,
        ) -> dict[str, Any]:
            entity_ids = entity_ids or []
            relation_ids = relation_ids or []
            claim_ids, evidence_ids = support(entity_ids, relation_ids, fallback_evidence)
            record = self._record(
                model_id,
                model_type,
                key,
                classification,
                title,
                description,
                claim_ids,
                evidence_ids,
                entity_ids,
                relation_ids,
                attributes,
                limitations,
            )
            grouped[model_type].append(record)
            return record

        # Application and repository boundaries are factual because repository membership is snapshot-bound.
        for repository_id, repository_entities in sorted(by_repo.items()):
            entity_ids = [entity["id"] for entity in repository_entities]
            kinds = sorted({entity["kind"] for entity in repository_entities})
            entry_points = sorted({entity["qualified_name"] for entity in repository_entities if entity["kind"] == "entry-point"})
            contracts = sorted({
                entity["qualified_name"] for entity in repository_entities
                if entity["kind"] in {"http-provider", "http-consumer", "event-producer", "event-consumer", "interface"}
            })
            add(
                "application-model", repository_id, "FACT", repository_id,
                f"Repository {repository_id} is part of the analyzed application snapshot and contributed {len(repository_entities)} extracted entities.",
                entity_ids,
                attributes={"repository_id": repository_id, "entity_count": len(repository_entities), "entity_kinds": kinds},
                fallback_evidence=[evidence for entity in repository_entities for evidence in entity.get("evidence", [])],
            )
            add(
                "repository-model", repository_id, "FACT", f"Repository {repository_id}",
                f"Repository {repository_id} owns the implementation surfaces listed in this record for the captured snapshot.",
                entity_ids,
                attributes={"repository_id": repository_id, "entry_points": entry_points, "contracts": contracts, "entity_kinds": kinds},
                fallback_evidence=[evidence for entity in repository_entities for evidence in entity.get("evidence", [])],
            )
            add(
                "architecture-model", repository_id, "IMPLEMENTED_BEHAVIOR", f"Component {repository_id}",
                f"The implementation surface for {repository_id} exposes its recorded entry points, contracts, configuration, and dependencies.",
                entity_ids,
                attributes={"repository_id": repository_id, "entry_points": entry_points, "contracts": contracts},
                fallback_evidence=[evidence for entity in repository_entities for evidence in entity.get("evidence", [])],
            )
            add(
                "ownership-boundaries", repository_id, "IMPLEMENTED_BEHAVIOR", f"Implementation ownership: {repository_id}",
                f"Source artifacts and contracts located in {repository_id} are implementation-owned by that repository in the analyzed snapshot; organizational ownership is not inferred.",
                entity_ids,
                attributes={"repository_id": repository_id, "owned_surfaces": contracts},
                limitations=["Organizational and business ownership require human confirmation."],
                fallback_evidence=[evidence for entity in repository_entities for evidence in entity.get("evidence", [])],
            )
            add(
                "bounded-contexts", repository_id, "BUSINESS_INFERENCE", f"Candidate context: {_humanize(repository_id)}",
                f"The vocabulary and implementation boundary in {repository_id} form a candidate domain context. A repository boundary alone does not prove a DDD bounded context.",
                entity_ids,
                attributes={"repository_id": repository_id, "candidate": True, "vocabulary": sorted({_humanize(entity["name"]) for entity in repository_entities if entity["kind"] not in {"file", "import"}})[:100]},
                limitations=["Bounded-context status and context-map relationship require domain-owner confirmation."],
                fallback_evidence=[evidence for entity in repository_entities for evidence in entity.get("evidence", [])],
            )

        # Technical relations, integrations, flow edges, and consistency boundaries.
        for relation in relations:
            relation_id = relation["id"]
            source_entity = entity_by_id.get(relation.get("source_entity"))
            target_entity = entity_by_id.get(relation.get("target_entity"))
            repository_id = relation.get("source_repository") or relation.get("repository_id") or (source_entity or {}).get("repository_id")
            target_repository = relation.get("target_repository") or (target_entity or {}).get("repository_id")
            target = relation.get("target_repository") or relation.get("target_entity") or relation.get("target_key") or relation.get("contract_key")
            inferred = relation.get("classification") in {"INFERENCE", "INFERRED"}
            classification = "BUSINESS_INFERENCE" if inferred else "IMPLEMENTED_BEHAVIOR"
            limitations = ["Relationship semantics are inferred from complementary source surfaces; runtime execution was not observed."] if inferred else None
            attributes = {
                "contract_key": relation.get("contract_key") or relation.get("target_key"),
                "source_repository": repository_id,
                "target_repository": target_repository,
                "confidence": relation.get("confidence"),
                "relation_type": relation["type"],
            }
            add(
                "dependency-model", relation_id, classification, relation["type"],
                f"{repository_id or relation.get('source_entity')} {relation['type']} {target}.",
                [item for item in (relation.get("source_entity"), relation.get("target_entity")) if item],
                [relation_id], attributes, limitations, relation.get("evidence", []),
            )
            if relation["type"] in {"PRODUCES", "CONSUMES", "PRODUCES_FOR"}:
                add(
                    "event-model", relation_id, classification, _humanize(str(target)),
                    f"The captured implementation records event interaction {relation['type']} for {target}.",
                    [item for item in (relation.get("source_entity"), relation.get("target_entity")) if item],
                    [relation_id], attributes, limitations, relation.get("evidence", []),
                )
            if relation["type"] in {"READS", "WRITES", "SHARES_DATA_WITH"}:
                add(
                    "data-model", relation_id, classification, _humanize(str(target)),
                    f"The captured implementation records data interaction {relation['type']} for {target}.",
                    [item for item in (relation.get("source_entity"), relation.get("target_entity")) if item],
                    [relation_id], attributes, limitations, relation.get("evidence", []),
                )
            if relation["type"] == "TRANSACTION_BOUNDARY":
                add(
                    "consistency-model", relation_id, "IMPLEMENTED_BEHAVIOR", "Local transaction boundary",
                    f"An explicit local transaction boundary is present in {repository_id}; remote operations and cross-repository atomicity are not implied.",
                    [relation.get("source_entity")] if relation.get("source_entity") else [],
                    [relation_id], attributes,
                    ["Cross-resource consistency, retry, compensation, and reconciliation behavior require additional evidence."],
                    relation.get("evidence", []),
                )
            if relation["type"] == "THROWS":
                add(
                    "flow-failures", relation_id, "IMPLEMENTED_BEHAVIOR", _humanize(str(target)),
                    f"The implementation explicitly raises or throws {target}; caller handling and user-visible outcome may require additional evidence.",
                    [relation.get("source_entity")] if relation.get("source_entity") else [],
                    [relation_id], attributes,
                    ["Recovery, retryability, and operational response are not assumed without evidence."],
                    relation.get("evidence", []),
                )
                add(
                    "invariants", relation_id, "BUSINESS_INFERENCE", f"Guard associated with {_humanize(str(target))}",
                    f"The explicit failure {target} indicates a guarded condition or invariant candidate in {repository_id}.",
                    [relation.get("source_entity")] if relation.get("source_entity") else [],
                    [relation_id], attributes,
                    ["The exact business rule and predicate must be confirmed from surrounding implementation or domain documentation."],
                    relation.get("evidence", []),
                )

        # Entity-level semantic models. Classification is conservative when semantics are derived from naming or placement.
        for entity in entities:
            kind = entity["kind"]
            name = entity["name"]
            qualified = entity["qualified_name"]
            repository_id = entity["repository_id"]
            path = entity["path"].lower()
            words = _lower_words(name)
            suffix = name.lower()
            evidence = entity.get("evidence", [])
            attributes = {"repository_id": repository_id, "kind": kind, "path": entity["path"], "technical_surface": qualified}

            if kind in {"event-producer", "event-consumer"}:
                add("event-model", entity["id"], "IMPLEMENTED_BEHAVIOR", qualified, f"{repository_id} contains {kind} {qualified}.", [entity["id"]], attributes=attributes, fallback_evidence=evidence)
                add("domain-events", entity["id"], "BUSINESS_INFERENCE", _humanize(name), f"The event surface {qualified} is a candidate domain or integration event relevant to application behavior.", [entity["id"]], attributes={**attributes, "event_role": kind}, limitations=["Business semantics, payload meaning, and delivery guarantees require contract or handler evidence."], fallback_evidence=evidence)
            if kind in {"data-reader", "data-writer", "table", "view", "materialized view"}:
                add("data-model", entity["id"], "IMPLEMENTED_BEHAVIOR", qualified, f"{repository_id} contains the recorded data surface {qualified}.", [entity["id"]], attributes=attributes, fallback_evidence=evidence)
            if kind in {"http-provider", "interface", "entry-point", "http-mapping", "http-route", "http-operation"}:
                title = _humanize(name)
                add("business-capabilities", entity["id"], "BUSINESS_INFERENCE", title, f"The implemented entry surface {qualified} indicates a candidate application capability.", [entity["id"]], attributes=attributes, limitations=["Business purpose, value, outcome, and capability hierarchy require domain confirmation."], fallback_evidence=evidence)
            if kind in {"http-provider", "http-consumer", "event-consumer", "event-producer", "interface"}:
                actor_type = "system actor" if kind in {"http-consumer", "event-consumer", "event-producer"} else "external or internal actor"
                add("actors", entity["id"], "BUSINESS_INFERENCE", f"Actor interacting with {_humanize(name)}", f"A {actor_type} interacts with {qualified}; identity, goals, and organizational responsibility are not derivable from this surface alone.", [entity["id"]], attributes={**attributes, "actor_type": actor_type}, limitations=["Actor identity and stakeholder classification require human confirmation."], fallback_evidence=evidence)
            if kind in {"process", "collaboration", "decisionService", "entry-definition"}:
                add("business-processes", entity["id"], "IMPLEMENTED_BEHAVIOR", _humanize(name), f"The workflow or decision definition {qualified} provides an implemented process surface.", [entity["id"]], attributes=attributes, limitations=["The technical workflow may not represent the complete human business process."], fallback_evidence=evidence)
            if kind in {"exclusiveGateway", "inclusiveGateway", "eventBasedGateway", "decision", "decisionService", "businessKnowledgeModel"}:
                add("policies-decisions", entity["id"], "IMPLEMENTED_BEHAVIOR", _humanize(name), f"The implementation contains decision or routing surface {qualified}.", [entity["id"]], attributes=attributes, limitations=["Decision inputs, outputs, precedence, and business ownership require expression or table evidence."], fallback_evidence=evidence)
                add("decision-tables", entity["id"], "BUSINESS_INFERENCE", _humanize(name), f"The routing or decision surface {qualified} is a candidate for normalized decision-table documentation.", [entity["id"]], attributes=attributes, limitations=["A complete condition/action matrix cannot be asserted unless all branches and predicates are extracted."], fallback_evidence=evidence)
            if any(token in suffix for token in ("authorization", "authentication", "permission", "security", "audit", "compliance", "consent")):
                add("security-model", entity["id"], "IMPLEMENTED_BEHAVIOR", _humanize(name), f"Security-related implementation surface {qualified} is present.", [entity["id"]], attributes=attributes, fallback_evidence=evidence)
                add("controls-compliance", entity["id"], "BUSINESS_INFERENCE", _humanize(name), f"The implementation surface {qualified} indicates a control or compliance concern.", [entity["id"]], attributes=attributes, limitations=["Control objective, regulatory source, control owner, and evidence of operating effectiveness require human confirmation."], fallback_evidence=evidence)
            if any(token in suffix for token in ("metric", "trace", "span", "health", "readiness", "liveness", "logger", "logging", "telemetry")):
                add("observability-model", entity["id"], "IMPLEMENTED_BEHAVIOR", _humanize(name), f"Observability-related implementation surface {qualified} is present.", [entity["id"]], attributes=attributes, fallback_evidence=evidence)
            if any(token in kind.lower() for token in ("deploy", "kubernetes", "terraform", "docker", "workload", "network-interface", "base-image")):
                add("deployment-model", entity["id"], "IMPLEMENTED_BEHAVIOR", qualified, f"Deployment-related source surface {qualified} is present.", [entity["id"]], attributes=attributes, fallback_evidence=evidence)

            semantic_classification = "BUSINESS_INFERENCE"
            semantic_limit = ["Semantic classification is derived from naming, source placement, and implementation structure; domain-owner confirmation is required."]
            is_domain_path = any(token in path for token in ("/domain/", "/model/", "/aggregate/", "/entity/", "/valueobject/", "/value-object/"))
            if kind in {"class", "record", "struct", "type", "interface"} and (is_domain_path or suffix.endswith(("aggregate", "entity", "record"))):
                add("aggregates-entities", entity["id"], semantic_classification, _humanize(name), f"{qualified} is a candidate aggregate or domain entity represented in {repository_id}.", [entity["id"]], attributes={**attributes, "semantic_kind": "aggregate-or-entity"}, limitations=semantic_limit, fallback_evidence=evidence)
            if kind in {"record", "struct", "type", "class"} and (suffix.endswith(("id", "identifier", "code", "money", "amount", "address", "period", "range", "value")) or "value" in path):
                add("value-objects", entity["id"], semantic_classification, _humanize(name), f"{qualified} is a candidate value object or identity type.", [entity["id"]], attributes={**attributes, "semantic_kind": "value-object"}, limitations=semantic_limit, fallback_evidence=evidence)
            if suffix.endswith(("command", "request")) or (kind == "method" and words & BUSINESS_VERBS):
                add("commands", entity["id"], semantic_classification, _humanize(name), f"{qualified} represents a candidate command or application action.", [entity["id"]], attributes={**attributes, "command_candidate": True}, limitations=semantic_limit, fallback_evidence=evidence)
            if suffix.endswith(("event", "created", "updated", "approved", "rejected", "submitted", "cancelled", "closed")) and kind in {"class", "record", "type", "interface"}:
                add("domain-events", entity["id"], semantic_classification, _humanize(name), f"{qualified} is a candidate event describing an occurrence in the application domain.", [entity["id"]], attributes={**attributes, "event_candidate": True}, limitations=semantic_limit, fallback_evidence=evidence)
            if suffix.endswith(("service", "policy", "specification", "validator", "calculator")) and is_domain_path:
                target_type = "domain-services" if suffix.endswith(("service", "calculator")) else "policies-decisions"
                add(target_type, entity["id"], semantic_classification, _humanize(name), f"{qualified} is a candidate domain {target_type.replace('-', ' ').rstrip('s')}.", [entity["id"]], attributes=attributes, limitations=semantic_limit, fallback_evidence=evidence)
            if kind == "enum" and (suffix.endswith(("status", "state", "phase")) or words & {"status", "state", "phase"}):
                add("state-model", entity["id"], semantic_classification, _humanize(name), f"{qualified} defines a candidate lifecycle state vocabulary.", [entity["id"]], attributes={**attributes, "state_container": True}, limitations=["Enum constants and legal transitions must be extracted before claiming a complete state machine."], fallback_evidence=evidence)
            if suffix.endswith(("rule", "policy", "specification", "validator")):
                add("business-rules", entity["id"], semantic_classification, _humanize(name), f"{qualified} indicates a candidate rule or policy implementation.", [entity["id"]], attributes=attributes, limitations=["Rule predicate, precedence, exception handling, and business ownership require direct implementation or human evidence."], fallback_evidence=evidence)

            if qualified.startswith(("http:", "event:", "data:", "config:")) or kind in {"class", "record", "enum", "process", "decision"}:
                add("terminology", entity["id"], "IMPLEMENTED_BEHAVIOR", _humanize(name), f"The technical term {qualified} is observed in {repository_id}.", [entity["id"]], attributes={"term": name, "qualified_term": qualified, "repository_id": repository_id, "kind": kind}, fallback_evidence=evidence)

        # Build use-case and cross-repository flow records from explicit interface/event/data relations.
        flow_relations = [relation for relation in relations if relation["type"] in {"CALLS", "EXPOSES", "PRODUCES", "CONSUMES", "PRODUCES_FOR", "READS", "WRITES", "SHARES_DATA_WITH"}]
        grouped_flows: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for relation in flow_relations:
            key = str(relation.get("contract_key") or relation.get("target_key") or relation["id"])
            grouped_flows[key].append(relation)
        for flow_key, flow_edges in sorted(grouped_flows.items()):
            relation_ids = [edge["id"] for edge in flow_edges]
            entity_ids = sorted({item for edge in flow_edges for item in (edge.get("source_entity"), edge.get("target_entity")) if item})
            repositories = sorted({
                value for edge in flow_edges for value in (
                    edge.get("source_repository"), edge.get("target_repository"),
                    (entity_by_id.get(edge.get("source_entity")) or {}).get("repository_id"),
                    (entity_by_id.get(edge.get("target_entity")) or {}).get("repository_id"),
                ) if value
            })
            edge_types = sorted({edge["type"] for edge in flow_edges})
            async_flow = any(edge["type"] in {"PRODUCES", "CONSUMES", "PRODUCES_FOR"} or flow_key.startswith("event:") for edge in flow_edges)
            cross_repo = len(repositories) > 1
            score = (3 if cross_repo else 0) + (2 if async_flow else 0) + (2 if any(edge["type"] == "WRITES" for edge in flow_edges) else 0)
            related_paths = {(entity_by_id[eid]["repository_id"], entity_by_id[eid]["path"]) for eid in entity_ids if eid in entity_by_id}
            related_entities = [entity for key in related_paths for entity in by_path.get(key, [])]
            failures = sorted({_humanize(entity["name"]) for entity in related_entities if entity["kind"] == "failure"})
            transactions = sorted({entity["qualified_name"] for entity in related_entities if entity["kind"] == "transaction-boundary"})
            security = sorted({entity["qualified_name"] for entity in related_entities if any(token in entity["name"].lower() for token in ("auth", "permission", "security", "role"))})
            if failures:
                score += 1
            if transactions:
                score += 2
            if security:
                score += 2
            tier = "TIER_1" if score >= 6 else "TIER_2" if score >= 3 else "TIER_3"
            flow_type = "EVENT_FLOW" if async_flow else "CROSS_REPOSITORY_FLOW" if cross_repo else "APPLICATION_USE_CASE"
            steps = []
            for index, edge in enumerate(sorted(flow_edges, key=lambda item: item["id"]), 1):
                source = edge.get("source_repository") or (entity_by_id.get(edge.get("source_entity")) or {}).get("repository_id")
                target = edge.get("target_repository") or (entity_by_id.get(edge.get("target_entity")) or {}).get("repository_id") or edge.get("target_key")
                steps.append({"order": index, "source": source, "action": edge["type"], "target": target, "contract": edge.get("contract_key") or edge.get("target_key")})
            add(
                "flows", flow_key, "IMPLEMENTED_BEHAVIOR" if all(edge.get("classification") == "OBSERVED" for edge in flow_edges) else "BUSINESS_INFERENCE",
                _humanize(flow_key),
                f"The captured source describes a {flow_type.lower().replace('_', ' ')} around {flow_key} spanning {len(repositories)} repository or repositories.",
                entity_ids, relation_ids,
                attributes={
                    "flow_key": flow_key,
                    "flow_type": flow_type,
                    "tier": tier,
                    "criticality_score": score,
                    "repositories": repositories,
                    "steps": steps,
                    "trigger": flow_key,
                    "synchronous": not async_flow,
                    "transaction_boundaries": transactions,
                    "failure_candidates": failures,
                    "security_surfaces": security,
                    "state_impact": [],
                    "data_impact": sorted({edge.get("target_key") for edge in flow_edges if edge["type"] in {"READS", "WRITES", "SHARES_DATA_WITH"} and edge.get("target_key")}),
                    "observability": [],
                },
                limitations=["Business intention, actor, postconditions, SLA, recovery ownership, and unobserved alternative paths require additional evidence."] if any(edge.get("classification") != "OBSERVED" for edge in flow_edges) else ["Runtime execution was not observed; this flow is reconstructed from source-bound evidence."],
                fallback_evidence=[evidence for edge in flow_edges for evidence in edge.get("evidence", [])],
            )

        # Domain overview summarizes discovered semantic records without inventing product intent.
        semantic_counts = {name: len(grouped[name]) for name in (
            "bounded-contexts", "aggregates-entities", "value-objects", "invariants", "domain-services", "commands", "domain-events", "state-model"
        )}
        all_semantic_entities = sorted({entity for name in semantic_counts for record in grouped[name] for entity in record["source_entities"]})
        if all_semantic_entities:
            add(
                "domain-overview", app, "BUSINESS_INFERENCE", f"Domain overview for {_humanize(app)}",
                "The domain view summarizes implementation-derived concepts, boundaries, actions, events, rules, and lifecycle candidates while preserving unknown business intent.",
                all_semantic_entities,
                attributes={"counts": semantic_counts, "application_id": app},
                limitations=["This overview is implementation-derived and must not be treated as a substitute for domain-expert confirmation."],
                fallback_evidence=[evidence for entity_id in all_semantic_entities for evidence in entity_by_id.get(entity_id, {}).get("evidence", [])],
            )
        else:
            add(
                "domain-overview", app, "UNKNOWN", f"Domain overview for {_humanize(app)}",
                "No source-grounded domain concepts, boundaries, actions, events, rules, or lifecycle candidates were proven by the current evidence set.",
                attributes={"counts": semantic_counts, "application_id": app},
                limitations=["Domain documentation requires source evidence or domain-expert confirmation."],
            )

        # Goals cannot be safely inferred from technical surfaces. Preserve a first-class unknown instead of fabricating one.
        add(
            "business-goals", "unconfirmed-goals", "UNKNOWN", "Business goals and measurable outcomes",
            "No authoritative business-goal or measurable-outcome source was proven by the current evidence set.",
            attributes={"required_confirmation": ["business problem", "stakeholders", "target outcomes", "success measures"]},
            limitations=["Human-confirmed product or business documentation is required."],
        )

        unknown_messages = {
            "deployment-model": "No complete deployment topology can be proven from the current evidence.",
            "security-model": "No complete security architecture can be proven from the current evidence.",
            "observability-model": "No complete logging, metrics, tracing, alerting, or SLO model can be proven from the current evidence.",
            "business-processes": "No complete business-process map can be proven from the current evidence.",
            "business-rules": "No complete business-rule catalog can be proven from the current evidence.",
            "policies-decisions": "No complete policy and decision model can be proven from the current evidence.",
            "controls-compliance": "No complete controls and compliance model can be proven from the current evidence.",
            "aggregates-entities": "No aggregate or entity semantics can be proven from the current evidence.",
            "value-objects": "No value-object semantics can be proven from the current evidence.",
            "invariants": "No complete invariant catalog can be proven from the current evidence.",
            "domain-services": "No domain-service semantics can be proven from the current evidence.",
            "commands": "No complete command catalog can be proven from the current evidence.",
            "domain-events": "No complete domain-event catalog can be proven from the current evidence.",
            "state-model": "No complete domain state machine can be proven from the current evidence.",
            "decision-tables": "No complete condition/action decision table can be proven from the current evidence.",
            "flow-failures": "No complete failure and recovery model can be proven from the current evidence.",
            "consistency-model": "No complete transaction and consistency model can be proven from the current evidence.",
        }
        for model_type, message in unknown_messages.items():
            if not grouped[model_type]:
                add(model_type, "unknown", "UNKNOWN", _humanize(model_type), message, limitations=[message])

        if conflicts:
            for conflict in conflicts:
                grouped["architecture-model"].append(self._record(
                    model_id, "architecture-model", conflict["id"], "CONFLICT", "Conflicting architecture evidence",
                    conflict["statement"], conflict.get("conflicting_claims", []), conflict.get("evidence", []),
                    attributes={"conflict_id": conflict["id"]},
                ))

        result = {}
        for model_type in MODEL_TYPES:
            result[model_type] = {
                "schema_id": "https://t-understand.dev/schemas/model-artifact.schema.json",
                "schema_version": "1.0.0",
                "model_id": model_id,
                "model_type": model_type,
                "application_id": app,
                "snapshot_id": snap,
                "memory_id": mid,
                "status": "CONFLICTED" if conflicts else "CURRENT",
                "records": sorted(grouped[model_type], key=lambda item: item["id"]),
                "limitations": [],
            }
        return result

    def reconcile(self, reconciliation_id: str, candidate_model_id: str, base_model_id: str, memory_id: str) -> dict[str, Any]:
        if not ID_RE.fullmatch(reconciliation_id):
            raise TUnderstandError("MOD-REC-001", "reconciliation_id must match canonical ID pattern")
        if self.validate(base_model_id)["status"] != "PASS":
            raise TUnderstandError("MOD-REC-002", "Base model is invalid")
        candidate = self.build(candidate_model_id, memory_id)
        base = self.show(base_model_id)
        def records(mid):
            result = {}
            for name in MODEL_TYPES:
                for record in self.artifact(mid, name)["records"]:
                    normalized = {k: v for k, v in record.items() if k not in {"model_id", "freshness"}}
                    result[record["id"]] = _canonical_digest(normalized)
            return result
        before, after = records(base_model_id), records(candidate_model_id)
        added = sorted(set(after) - set(before)); removed = sorted(set(before) - set(after))
        common = sorted(set(before) & set(after)); changed = [x for x in common if before[x] != after[x]]
        unchanged = [x for x in common if before[x] == after[x]]
        report = {
            "schema_id": "https://t-understand.dev/schemas/model-reconciliation.schema.json",
            "schema_version": "1.0.0", "reconciliation_id": reconciliation_id,
            "base_model_id": base_model_id, "candidate_model_id": candidate_model_id,
            "base_memory_id": base["memory_id"], "candidate_memory_id": candidate["memory_id"],
            "status": "CHANGED" if added or removed or changed else "UNCHANGED",
            "added": added, "removed": removed, "changed": changed, "unchanged": unchanged,
            "generated_at": utc_now(),
        }
        self.contracts.validate("model-reconciliation", report)
        atomic_write_yaml(self.reports_root / candidate_model_id / f"reconciliation-{reconciliation_id}.yaml", report)
        return report

    def show(self, model_id: str) -> dict[str, Any]:
        return load_yaml(self._dir(model_id) / "model-manifest.yaml")

    def list(self) -> dict[str, Any]:
        current = load_yaml(self.root / "current.yaml") if (self.root / "current.yaml").exists() else None
        vals=[]
        if self.versions_root.exists():
            for p in sorted(self.versions_root.iterdir()):
                if p.is_dir() and (p/"model-manifest.yaml").exists(): vals.append(self.show(p.name))
        return {"current":current,"versions":vals}

    def artifact(self, model_id: str, name: str) -> dict[str, Any]:
        doc=self.show(model_id)
        if name not in doc["artifacts"]: raise TUnderstandError("MOD-ART-001",f"Unknown model artifact: {name}")
        return load_yaml(self._dir(model_id)/doc["artifacts"][name]["path"])

    def validate(self, model_id: str) -> dict[str, Any]:
        errors=[]; checks=0
        try:
            manifest=self.show(model_id); self.contracts.validate("model-manifest",manifest); checks+=1
            if _canonical_digest({k:v for k,v in manifest.items() if k!='content_digest'}) != manifest['content_digest']: errors.append('model manifest digest mismatch')
            claim_ids={x['id'] for x in self.memory._load_artifact(manifest['memory_id'],'claims')} | {x['id'] for x in self.memory._load_artifact(manifest['memory_id'],'conflicts')}
            evidence_ids={x['id'] for x in self.memory._load_artifact(manifest['memory_id'],'evidence')}
            records=[]
            for name,meta in manifest['artifacts'].items():
                path=self._dir(model_id)/meta['path']; checks+=2
                if sha256_file(path)!=meta['sha256']: errors.append(f'{name} checksum mismatch')
                if name=='traceability':
                    vals=[json.loads(x) for x in path.read_text().splitlines() if x]
                    for x in vals: self.contracts.validate('model-trace',x); checks+=1
                else:
                    doc=load_yaml(path); self.contracts.validate('model-artifact',doc); checks+=1
                    if _canonical_digest({k:v for k,v in doc.items() if k!='content_digest'}) != doc['content_digest']: errors.append(f'{name} digest mismatch')
                    if len(doc['records'])!=meta['records']: errors.append(f'{name} count mismatch')
                    for r in doc['records']:
                        self.contracts.validate('model-record',r); checks+=1; records.append(r)
                        if set(r['claim_ids'])-claim_ids: errors.append(f"{r['id']} references missing claims")
                        if set(r['evidence_ids'])-evidence_ids: errors.append(f"{r['id']} references missing evidence")
                        if r['classification'] not in {'UNKNOWN','LIMITATION'} and (not r['claim_ids'] or not r['evidence_ids']): errors.append(f"{r['id']} is unsupported")
            ids=[r['id'] for r in records]
            if len(ids)!=len(set(ids)): errors.append('duplicate model record IDs')
        except Exception as exc: errors.append(str(exc))
        report={"schema_id":"https://t-understand.dev/schemas/model-verification.schema.json","schema_version":"1.0.0","model_id":model_id,"status":"PASS" if not errors else "FAIL","checks":checks,"errors":errors,"generated_at":utc_now()}
        self.contracts.validate('model-verification',report); atomic_write_yaml(self.reports_root/model_id/'verification.yaml',report); return report

    def critique(self, model_id: str) -> dict[str, Any]:
        issues=[]; checks=0; manifest=self.show(model_id)
        for name in MODEL_TYPES:
            doc=self.artifact(model_id,name)
            for r in doc['records']:
                checks+=1
                if r['classification'] in {'FACT','IMPLEMENTED_BEHAVIOR'} and (not r['claim_ids'] or not r['evidence_ids']): issues.append({'code':'MOD-UNSUPPORTED','severity':'BLOCKER','record_id':r['id']})
                if r['model_type'] in {'business-capabilities','actors','business-rules'} and r['classification']=='FACT': issues.append({'code':'MOD-BUSINESS-PROMOTION','severity':'BLOCKER','record_id':r['id']})
                if r['classification']=='BUSINESS_INFERENCE' and not r.get('limitations'): issues.append({'code':'MOD-INFERENCE-DISCLOSURE','severity':'MAJOR','record_id':r['id']})
        report={"schema_id":"https://t-understand.dev/schemas/model-critique.schema.json","schema_version":"1.0.0","model_id":model_id,"status":"PASS" if not issues else "FAIL","checks":checks,"issues":issues,"generated_at":utc_now()}
        self.contracts.validate('model-critique',report); atomic_write_yaml(self.reports_root/model_id/'critique.yaml',report); return report
