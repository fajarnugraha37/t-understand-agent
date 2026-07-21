from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .analysis import AnalysisManager, ID_RE
from .contracts import ContractValidator
from .discovery import _canonical_digest
from .errors import TUnderstandError
from .io import atomic_write_text, atomic_write_yaml, load_yaml, sha256_file, utc_now


def _id(prefix: str, *parts: Any) -> str:
    raw = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(raw).hexdigest()[:16].upper()}"


def _jsonl(values: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n" for value in values)


class GraphManager:
    def __init__(self, project_root: Path, context_root: Path):
        self.project_root = project_root
        self.context_root = context_root.resolve()
        self.analysis = AnalysisManager(project_root, context_root)
        self.contracts = ContractValidator(project_root)

    @property
    def root(self) -> Path:
        return self.context_root / "graphs"

    @contextmanager
    def lock(self) -> Iterator[None]:
        lock = self.context_root / "runtime" / "locks" / "graph.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        try:
            lock.mkdir()
        except FileExistsError as exc:
            raise TUnderstandError("GRF-LOCK-001", "Application graph mutation is already active") from exc
        try:
            yield
        finally:
            lock.rmdir()

    def _dir(self, graph_id: str) -> Path:
        if not ID_RE.fullmatch(graph_id):
            raise TUnderstandError("GRF-ID-001", "graph_id must match ^[A-Z][A-Z0-9_-]{2,63}$")
        return self.root / graph_id

    def create(self, graph_id: str, analysis_id: str) -> dict[str, Any]:
        final = self._dir(graph_id)
        if final.exists():
            raise TUnderstandError("GRF-ID-002", f"Graph already exists and is immutable: {graph_id}")
        validation = self.analysis.validate(analysis_id)
        if validation["status"] != "PASS":
            raise TUnderstandError("GRF-INPUT-001", f"Analysis validation failed: {analysis_id}")
        analysis_doc = self.analysis.show(analysis_id)
        entities = self.analysis._load_artifact(analysis_id, "entities")
        intra = self.analysis._load_artifact(analysis_id, "relations")
        cross, candidates = self._link(analysis_doc["snapshot_id"], entities, intra)

        with self.lock():
            if final.exists():
                raise TUnderstandError("GRF-ID-002", f"Graph already exists and is immutable: {graph_id}")
            temp = self.root / f".{graph_id}.{uuid.uuid4().hex}.tmp"
            temp.mkdir(parents=True)
            try:
                artifacts = {}
                for name, values, contract in (
                    ("cross_relations", cross, "cross-repository-relation"),
                    ("unresolved_candidates", candidates, "relationship-candidate"),
                ):
                    for value in values:
                        self.contracts.validate(contract, value)
                    path = temp / f"{name.replace('_', '-')}.jsonl"
                    atomic_write_text(path, _jsonl(values))
                    artifacts[name] = {"path": path.name, "sha256": sha256_file(path), "records": len(values)}
                repositories = len({e["repository_id"] for e in entities})
                base = {
                    "schema_id": "https://t-understand.dev/schemas/application-graph.schema.json",
                    "schema_version": "1.0.0", "graph_id": graph_id,
                    "application_id": analysis_doc["application_id"], "snapshot_id": analysis_doc["snapshot_id"],
                    "analysis_id": analysis_id, "status": "LINKED", "artifacts": artifacts,
                    "coverage": {"repositories": repositories, "entities": len(entities), "intra_relations": len(intra),
                                 "cross_relations": len(cross), "unresolved_candidates": len(candidates)},
                    "generated_at": utc_now(),
                }
                doc = {**base, "content_digest": _canonical_digest(base)}
                self.contracts.validate("application-graph", doc)
                atomic_write_yaml(temp / "application-graph.yaml", doc)
                os.replace(temp, final)
            except Exception:
                shutil.rmtree(temp, ignore_errors=True)
                raise
        return self.show(graph_id)

    def _link(self, snapshot_id: str, entities: list[dict[str, Any]], intra: list[dict[str, Any]]):
        by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for entity in entities:
            q = entity["qualified_name"]
            if q.startswith(("event:", "http:", "data:")):
                by_key[q].append(entity)

        cross: list[dict[str, Any]] = []
        matched: set[str] = set()
        for key, values in sorted(by_key.items()):
            if key.startswith("event:"):
                producers = [e for e in values if e["kind"] == "event-producer"]
                consumers = [e for e in values if e["kind"] == "event-consumer"]
                self._connect(snapshot_id, "PRODUCES_FOR", key, producers, consumers, cross, matched, "FACT", "high",
                              "Producer and consumer name the same exact event topic in different repositories.")
            elif key.startswith("http:"):
                providers = [e for e in values if e["kind"] in {"http-provider", "interface"}]
                consumers = [e for e in values if e["kind"] == "http-consumer"]
                providers_by_repo: dict[str, list[dict[str, Any]]] = defaultdict(list)
                for provider in providers:
                    providers_by_repo[provider["repository_id"]].append(provider)
                if len(providers_by_repo) == 1:
                    only = next(iter(providers_by_repo.values()))
                    # Prefer an implementation route over a contract-only surface, then stable ID.
                    provider = sorted(only, key=lambda e: (0 if e["kind"] == "http-provider" else 1, e["id"]))[0]
                    self._connect(snapshot_id, "CALLS", key, consumers, [provider], cross, matched, "FACT", "high",
                                  "Consumer and the sole provider repository name the same exact HTTP method and path.")
                # More than one provider repository is intentionally left unresolved as ambiguous.
            elif key.startswith("data:"):
                writers = [e for e in values if e["kind"] == "data-writer"]
                readers = [e for e in values if e["kind"] == "data-reader"]
                self._connect(snapshot_id, "SHARES_DATA_WITH", key, writers, readers, cross, matched, "INFERENCE", "medium",
                              "Both repositories reference the same exact data relation; deployment ownership is not inferred.")

        # Exact dependency-to-declaration matching. Only promote unique, cross-repository matches.
        declarations: dict[str, list[dict[str, Any]]] = defaultdict(list)
        by_id = {e["id"]: e for e in entities}
        for entity in entities:
            declarations[entity["name"]].append(entity)
            declarations[entity["qualified_name"]].append(entity)
        for rel in intra:
            if rel["type"] != "DEPENDS_ON" or not rel["target_key"].startswith("dependency:"):
                continue
            name = rel["target_key"].split(":", 1)[1]
            source = by_id.get(rel["source_entity"])
            if not source:
                continue
            matches = [e for e in declarations.get(name, []) if e["repository_id"] != source["repository_id"]]
            unique = {e["id"]: e for e in matches}
            if len(unique) == 1:
                target = next(iter(unique.values()))
                x = self._cross(snapshot_id, "DEPENDS_ON", rel["target_key"], source, target,
                                sorted(set(rel["evidence"] + target["evidence"])), "FACT", "high",
                                "An explicit dependency name exactly matches one declaration in another repository.")
                cross.append(x); matched.add(source["id"]); matched.add(target["id"])

        candidates = []
        eligible = [e for e in entities if e["qualified_name"].startswith(("event:", "http:", "data:"))]
        for entity in eligible:
            if entity["id"] in matched:
                continue
            candidates.append({
                "schema_id": "https://t-understand.dev/schemas/relationship-candidate.schema.json",
                "schema_version": "1.0.0", "id": _id("CAND", entity["id"], entity["qualified_name"]),
                "application_snapshot": snapshot_id, "repository_id": entity["repository_id"],
                "relation_type": self._candidate_type(entity), "contract_key": entity["qualified_name"],
                "entity_id": entity["id"], "evidence": entity["evidence"], "status": "UNRESOLVED",
                "reason": "No exact complementary endpoint with evidence was found in another repository.",
            })
        return sorted({x["id"]: x for x in cross}.values(), key=lambda x: x["id"]), sorted(candidates, key=lambda x: x["id"])

    def _connect(self, snapshot_id, rel_type, key, sources, targets, output, matched, classification, confidence, reasoning):
        for source in sources:
            for target in targets:
                if source["repository_id"] == target["repository_id"]:
                    continue
                evidence = sorted(set(source["evidence"] + target["evidence"]))
                if len(evidence) < 2:
                    continue
                output.append(self._cross(snapshot_id, rel_type, key, source, target, evidence, classification, confidence, reasoning))
                matched.add(source["id"]); matched.add(target["id"])

    def _cross(self, snapshot_id, rel_type, key, source, target, evidence, classification, confidence, reasoning):
        return {
            "schema_id": "https://t-understand.dev/schemas/cross-repository-relation.schema.json",
            "schema_version": "1.0.0", "id": _id("XREL", rel_type, source["id"], target["id"], key),
            "application_snapshot": snapshot_id, "type": rel_type,
            "source_repository": source["repository_id"], "source_entity": source["id"],
            "target_repository": target["repository_id"], "target_entity": target["id"],
            "contract_key": key, "evidence": evidence, "classification": classification,
            "confidence": confidence, "reasoning": reasoning, "freshness": "current",
        }

    @staticmethod
    def _candidate_type(entity):
        if entity["qualified_name"].startswith("event:"):
            return "PRODUCES_FOR"
        if entity["qualified_name"].startswith("http:"):
            return "CALLS"
        return "SHARES_DATA_WITH"

    def show(self, graph_id: str) -> dict[str, Any]:
        return load_yaml(self._dir(graph_id) / "application-graph.yaml")

    def list(self) -> dict[str, Any]:
        values = []
        if self.root.exists():
            for path in sorted(self.root.glob("*/application-graph.yaml")):
                doc = load_yaml(path)
                values.append({"graph_id": doc["graph_id"], "analysis_id": doc["analysis_id"], "snapshot_id": doc["snapshot_id"], "status": doc["status"]})
        return {"graphs": values}

    def _load_artifact(self, graph_id: str, name: str) -> list[dict[str, Any]]:
        doc = self.show(graph_id); path = self._dir(graph_id) / doc["artifacts"][name]["path"]
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    def validate(self, graph_id: str) -> dict[str, Any]:
        errors = []; checks = 0
        try:
            doc = self.show(graph_id); self.contracts.validate("application-graph", doc); checks += 1
            if _canonical_digest({k: v for k, v in doc.items() if k != "content_digest"}) != doc["content_digest"]:
                errors.append("application graph content_digest mismatch")
            analysis = self.analysis.show(doc["analysis_id"]); checks += 1
            if analysis["snapshot_id"] != doc["snapshot_id"]:
                errors.append("graph and analysis snapshot mismatch")
            evidence_ids = {x["id"] for x in self.analysis._load_artifact(doc["analysis_id"], "evidence")}
            entity_ids = {x["id"] for x in self.analysis._load_artifact(doc["analysis_id"], "entities")}
            for name, contract in (("cross_relations", "cross-repository-relation"), ("unresolved_candidates", "relationship-candidate")):
                meta = doc["artifacts"][name]; path = self._dir(graph_id) / meta["path"]; checks += 2
                if sha256_file(path) != meta["sha256"]:
                    errors.append(f"{name} checksum mismatch")
                values = self._load_artifact(graph_id, name)
                if len(values) != meta["records"]:
                    errors.append(f"{name} count mismatch")
                for value in values:
                    self.contracts.validate(contract, value); checks += 1
                    if set(value["evidence"]) - evidence_ids:
                        errors.append(f"{value['id']} references missing evidence")
                    for field in ("source_entity", "target_entity", "entity_id"):
                        if field in value and value[field] not in entity_ids:
                            errors.append(f"{value['id']} references missing entity {value[field]}")
                    if name == "cross_relations" and value["source_repository"] == value["target_repository"]:
                        errors.append(f"{value['id']} is not cross-repository")
        except Exception as exc:
            errors.append(str(exc))
        report = {"status": "PASS" if not errors else "FAIL", "graph_id": graph_id, "checks": checks, "errors": errors, "validated_at": utc_now()}
        atomic_write_yaml(self._dir(graph_id) / "validation-report.yaml", report)
        return report
