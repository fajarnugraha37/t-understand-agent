from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import uuid
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .analysis import AnalysisManager, ID_RE
from .contracts import ContractValidator
from .discovery import DiscoveryManager, _canonical_digest
from .errors import TUnderstandError
from .graph import GraphManager
from .io import atomic_write_text, atomic_write_yaml, load_yaml, sha256_file, utc_now
from .snapshot import SnapshotManager


def _id(prefix: str, *parts: Any) -> str:
    raw = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(raw).hexdigest()[:16].upper()}"


def _jsonl(values: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n" for value in values)


class MemoryManager:
    def __init__(self, project_root: Path, context_root: Path):
        self.project_root = project_root
        self.context_root = context_root.resolve()
        self.graphs = GraphManager(project_root, context_root)
        self.analysis = AnalysisManager(project_root, context_root)
        self.discovery = DiscoveryManager(project_root, context_root)
        self.snapshots = SnapshotManager(project_root, context_root)
        self.contracts = ContractValidator(project_root)

    @property
    def root(self) -> Path:
        return self.context_root / "memory"

    @property
    def versions_root(self) -> Path:
        return self.root / "versions"

    @property
    def invalidations_root(self) -> Path:
        return self.root / "invalidations"

    @property
    def reports_root(self) -> Path:
        return self.context_root / "reports" / "memory"

    @property
    def runtime_root(self) -> Path:
        return self.context_root / "runtime" / "memory"

    @contextmanager
    def lock(self) -> Iterator[None]:
        lock = self.context_root / "runtime" / "locks" / "memory.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        try:
            lock.mkdir()
        except FileExistsError as exc:
            raise TUnderstandError("MEM-LOCK-001", "Canonical memory mutation is already active") from exc
        try:
            yield
        finally:
            lock.rmdir()

    def _dir(self, memory_id: str) -> Path:
        if not ID_RE.fullmatch(memory_id):
            raise TUnderstandError("MEM-ID-001", "memory_id must match ^[A-Z][A-Z0-9_-]{2,63}$")
        return self.versions_root / memory_id

    def build(self, memory_id: str, graph_id: str, make_current: bool = True) -> dict[str, Any]:
        final = self._dir(memory_id)
        if final.exists():
            raise TUnderstandError("MEM-ID-002", f"Memory version already exists and is immutable: {memory_id}")
        graph_validation = self.graphs.validate(graph_id)
        if graph_validation["status"] != "PASS":
            raise TUnderstandError("MEM-INPUT-001", f"Graph validation failed: {graph_id}")
        graph = self.graphs.show(graph_id)
        analysis_id = graph["analysis_id"]
        evidence = self.analysis._load_artifact(analysis_id, "evidence")
        entities = self.analysis._load_artifact(analysis_id, "entities")
        intra = self.analysis._load_artifact(analysis_id, "relations")
        cross = self.graphs._load_artifact(graph_id, "cross_relations")
        relations = sorted(intra + cross, key=lambda x: x["id"])
        claims, conflicts = self._claims(graph["snapshot_id"], entities, relations)

        with self.lock():
            if final.exists():
                raise TUnderstandError("MEM-ID-002", f"Memory version already exists and is immutable: {memory_id}")
            temp = self.versions_root / f".{memory_id}.{uuid.uuid4().hex}.tmp"
            temp.mkdir(parents=True)
            try:
                artifacts = {}
                for name, values, contract in (
                    ("evidence", evidence, "evidence-record"),
                    ("entities", entities, "analysis-entity"),
                    ("relations", relations, None),
                    ("claims", claims, "claim"),
                    ("conflicts", conflicts, "claim"),
                    ("invalidations", [], None),
                ):
                    if contract:
                        for value in values:
                            self.contracts.validate(contract, value)
                    elif name == "relations":
                        for value in values:
                            self.contracts.validate("cross-repository-relation" if value["id"].startswith("XREL-") else "analysis-relation", value)
                    path = temp / f"{name}.jsonl"
                    atomic_write_text(path, _jsonl(values))
                    artifacts[name] = {"path": path.name, "sha256": sha256_file(path), "records": len(values)}
                unsupported = sum(1 for claim in claims if claim["classification"] == "FACT" and not claim["evidence"])
                duplicate_ids = self._duplicate_count(evidence + entities + relations + claims + conflicts)
                coverage = 1.0 if not (entities or relations or claims) else self._evidence_coverage(entities, relations, claims)
                status = "CONFLICTED" if conflicts else "CURRENT"
                base = {
                    "schema_id": "https://t-understand.dev/schemas/memory-manifest.schema.json",
                    "schema_version": "1.0.0", "memory_id": memory_id,
                    "application_id": graph["application_id"], "snapshot_id": graph["snapshot_id"],
                    "graph_id": graph_id, "status": status, "artifacts": artifacts,
                    "counts": {"evidence": len(evidence), "entities": len(entities), "relations": len(relations),
                               "claims": len(claims), "conflicts": len(conflicts)},
                    "quality": {"evidence_coverage": round(coverage, 6), "unsupported_fact_claims": unsupported,
                                "duplicate_ids": duplicate_ids},
                    "generated_at": utc_now(),
                }
                doc = {**base, "content_digest": _canonical_digest(base)}
                self.contracts.validate("memory-manifest", doc)
                atomic_write_yaml(temp / "memory-manifest.yaml", doc)
                os.replace(temp, final)
                self.rebuild_index(memory_id)
                report = self.validate(memory_id)
                if report["status"] != "PASS":
                    raise TUnderstandError("MEM-VERIFY-001", f"New memory failed verification: {report['errors']}")
                critique = self.critique(memory_id)
                if critique["status"] != "PASS":
                    raise TUnderstandError("MEM-CRITIQUE-001", "New memory failed independent deterministic critique")
                if make_current:
                    atomic_write_yaml(self.root / "current.yaml", {"memory_id": memory_id, "snapshot_id": doc["snapshot_id"], "manifest_sha256": sha256_file(final / "memory-manifest.yaml"), "updated_at": utc_now()})
            except Exception:
                if temp.exists():
                    shutil.rmtree(temp, ignore_errors=True)
                if final.exists() and not (final / "memory-manifest.yaml").exists():
                    shutil.rmtree(final, ignore_errors=True)
                raise
        return self.show(memory_id)

    def _claims(self, snapshot_id: str, entities: list[dict[str, Any]], relations: list[dict[str, Any]]):
        claims: list[dict[str, Any]] = []
        entity_claims: dict[str, str] = {}
        contract_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for entity in entities:
            if entity["kind"] in {"http-provider", "interface", "event-producer", "event-consumer", "data-reader", "data-writer", "entry-point"}:
                cid = _id("CLM", "entity", entity["id"])
                claim = {
                    "schema_id": "https://t-understand.dev/schemas/claim.schema.json", "schema_version": "1.0.0",
                    "id": cid, "application_snapshot": snapshot_id, "classification": "FACT",
                    "statement": f"Repository {entity['repository_id']} contains {entity['kind']} {entity['qualified_name']}.",
                    "evidence": entity["evidence"], "confidence": "high", "freshness": "current",
                    "reasoning": "The canonical entity was extracted from an exact source location and file digest.",
                }
                claims.append(claim); entity_claims[entity["id"]] = cid
                if entity["kind"] in {"http-provider", "interface"} and entity["qualified_name"].startswith("http:"):
                    contract_groups[("http-provider", entity["qualified_name"])].append(entity)
        for relation in relations:
            classification = "INFERENCE" if relation.get("classification") == "INFERRED" else "FACT"
            confidence = relation.get("confidence", "high")
            source = relation.get("source_entity")
            target = relation.get("target_entity") or relation.get("target_key") or relation.get("contract_key")
            cid = _id("CLM", "relation", relation["id"])
            claims.append({
                "schema_id": "https://t-understand.dev/schemas/claim.schema.json", "schema_version": "1.0.0",
                "id": cid, "application_snapshot": snapshot_id, "classification": classification,
                "statement": f"{source} {relation['type']} {target}.", "evidence": relation["evidence"],
                "confidence": confidence, "freshness": "current", "reasoning": relation["reasoning"],
            })
        conflicts = []
        for (_, key), group in sorted(contract_groups.items()):
            repositories = {e["repository_id"] for e in group}
            if len(repositories) < 2:
                continue
            refs = sorted(entity_claims[e["id"]] for e in group)
            conflicts.append({
                "schema_id": "https://t-understand.dev/schemas/claim.schema.json", "schema_version": "1.0.0",
                "id": _id("CLM", "conflict", key), "application_snapshot": snapshot_id,
                "classification": "CONFLICT", "statement": f"Multiple repositories expose the same HTTP contract {key}.",
                "evidence": sorted({ev for e in group for ev in e["evidence"]}), "confidence": "not-applicable",
                "freshness": "conflicted", "conflicting_claims": refs,
            })
        return sorted(claims, key=lambda x: x["id"]), sorted(conflicts, key=lambda x: x["id"])

    @staticmethod
    def _duplicate_count(values: list[dict[str, Any]]) -> int:
        counts = Counter(value["id"] for value in values)
        return sum(count - 1 for count in counts.values() if count > 1)

    @staticmethod
    def _evidence_coverage(entities, relations, claims) -> float:
        values = entities + relations + claims
        return sum(1 for value in values if value.get("evidence")) / len(values) if values else 1.0

    def show(self, memory_id: str) -> dict[str, Any]:
        return load_yaml(self._dir(memory_id) / "memory-manifest.yaml")

    def list(self) -> dict[str, Any]:
        values = []
        if self.versions_root.exists():
            for path in sorted(self.versions_root.glob("*/memory-manifest.yaml")):
                doc = load_yaml(path)
                values.append({"memory_id": doc["memory_id"], "snapshot_id": doc["snapshot_id"], "status": doc["status"], "counts": doc["counts"]})
        current = load_yaml(self.root / "current.yaml") if (self.root / "current.yaml").exists() else None
        return {"current": current, "versions": values}

    def _load_artifact(self, memory_id: str, name: str) -> list[dict[str, Any]]:
        doc = self.show(memory_id); path = self._dir(memory_id) / doc["artifacts"][name]["path"]
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    def critique(self, memory_id: str) -> dict[str, Any]:
        issues = []; checks = 0
        doc = self.show(memory_id)
        evidence = self._load_artifact(memory_id, "evidence"); checks += len(evidence)
        entities = self._load_artifact(memory_id, "entities"); checks += len(entities)
        relations = self._load_artifact(memory_id, "relations"); checks += len(relations)
        claims = self._load_artifact(memory_id, "claims"); checks += len(claims)
        evidence_ids = {e["id"] for e in evidence}
        for claim in claims:
            if claim["classification"] in {"FACT", "INFERENCE"} and not claim["evidence"]:
                issues.append({"code": "MEM-UNSUPPORTED", "severity": "BLOCKER", "message": f"{claim['id']} has no evidence"})
            if set(claim["evidence"]) - evidence_ids:
                issues.append({"code": "MEM-MISSING-EVIDENCE", "severity": "BLOCKER", "message": f"{claim['id']} references missing evidence"})
            if claim["freshness"] != "current":
                issues.append({"code": "MEM-NONCURRENT", "severity": "MAJOR", "message": f"{claim['id']} is not current"})
        duplicates = self._duplicate_count(evidence + entities + relations + claims)
        if duplicates:
            issues.append({"code": "MEM-DUPLICATE-ID", "severity": "BLOCKER", "message": f"{duplicates} duplicate canonical IDs"})
        if doc["quality"]["evidence_coverage"] < 1.0:
            issues.append({"code": "MEM-COVERAGE", "severity": "MAJOR", "message": "Evidence coverage is below 100%"})
        report = {
            "schema_id": "https://t-understand.dev/schemas/memory-critique.schema.json", "schema_version": "1.0.0",
            "memory_id": memory_id, "status": "PASS" if not [i for i in issues if i["severity"] in {"BLOCKER", "MAJOR"}] else "FAIL",
            "checks": checks, "issues": issues, "generated_at": utc_now(),
        }
        self.contracts.validate("memory-critique", report)
        atomic_write_yaml(self.reports_root / memory_id / "critique.yaml", report)
        return report

    def validate(self, memory_id: str) -> dict[str, Any]:
        errors = []; checks = 0; sqlite_status = "NOT_BUILT"
        try:
            doc = self.show(memory_id); self.contracts.validate("memory-manifest", doc); checks += 1
            if _canonical_digest({k: v for k, v in doc.items() if k != "content_digest"}) != doc["content_digest"]:
                errors.append("memory content_digest mismatch")
            loaded = {}
            for name in ("evidence", "entities", "relations", "claims", "conflicts", "invalidations"):
                meta = doc["artifacts"][name]; path = self._dir(memory_id) / meta["path"]; checks += 2
                if sha256_file(path) != meta["sha256"]:
                    errors.append(f"{name} checksum mismatch")
                values = self._load_artifact(memory_id, name)
                if len(values) != meta["records"]:
                    errors.append(f"{name} count mismatch")
                for value in values:
                    contract = "evidence-record" if name == "evidence" else "analysis-entity" if name == "entities" else "claim" if name in {"claims", "conflicts"} else None
                    if name == "relations":
                        contract = "cross-repository-relation" if value["id"].startswith("XREL-") else "analysis-relation"
                    if contract:
                        self.contracts.validate(contract, value); checks += 1
                loaded[name] = values
            evidence_ids = {x["id"] for x in loaded["evidence"]}; entity_ids = {x["id"] for x in loaded["entities"]}
            claim_ids = {x["id"] for x in loaded["claims"]}
            for value in loaded["entities"] + loaded["relations"] + loaded["claims"] + loaded["conflicts"]:
                if set(value.get("evidence", [])) - evidence_ids:
                    errors.append(f"{value['id']} has missing evidence references")
            for value in loaded["relations"]:
                for field in ("source_entity", "target_entity"):
                    if value.get(field) and value[field] not in entity_ids:
                        errors.append(f"{value['id']} has missing entity reference")
            for conflict in loaded["conflicts"]:
                if set(conflict.get("conflicting_claims", [])) - claim_ids:
                    errors.append(f"{conflict['id']} has missing conflicting claim references")
            db = self.runtime_root / memory_id / "index.sqlite"
            if db.exists():
                with sqlite3.connect(db) as conn:
                    counts = {table: conn.execute(f"select count(*) from {table}").fetchone()[0] for table in ("evidence", "entities", "relations", "claims")}
                expected = {"evidence": len(loaded["evidence"]), "entities": len(loaded["entities"]), "relations": len(loaded["relations"]), "claims": len(loaded["claims"]) + len(loaded["conflicts"])}
                sqlite_status = "PASS" if counts == expected else "FAIL"
                if sqlite_status == "FAIL": errors.append("SQLite index counts differ from canonical records")
        except Exception as exc:
            errors.append(str(exc)); sqlite_status = "FAIL"
        report = {
            "schema_id": "https://t-understand.dev/schemas/memory-verification.schema.json", "schema_version": "1.0.0",
            "memory_id": memory_id, "status": "PASS" if not errors else "FAIL", "checks": checks,
            "errors": errors, "sqlite_index": sqlite_status, "verified_at": utc_now(),
        }
        self.contracts.validate("memory-verification", report)
        atomic_write_yaml(self.reports_root / memory_id / "verification.yaml", report)
        return report

    def rebuild_index(self, memory_id: str) -> dict[str, Any]:
        target = self.runtime_root / memory_id
        target.mkdir(parents=True, exist_ok=True)
        temp = target / f"index.{uuid.uuid4().hex}.tmp.sqlite"
        final = target / "index.sqlite"
        if temp.exists(): temp.unlink()
        with sqlite3.connect(temp) as conn:
            conn.executescript("""
                PRAGMA journal_mode=OFF;
                CREATE TABLE evidence(id TEXT PRIMARY KEY, repository TEXT, path TEXT, body TEXT);
                CREATE TABLE entities(id TEXT PRIMARY KEY, repository_id TEXT, kind TEXT, qualified_name TEXT, body TEXT);
                CREATE TABLE relations(id TEXT PRIMARY KEY, relation_type TEXT, source_entity TEXT, target_key TEXT, body TEXT);
                CREATE TABLE claims(id TEXT PRIMARY KEY, classification TEXT, statement TEXT, freshness TEXT, body TEXT);
            """)
            for value in self._load_artifact(memory_id, "evidence"):
                conn.execute("insert into evidence values (?,?,?,?)", (value["id"], value["repository"], value["path"], json.dumps(value, sort_keys=True)))
            for value in self._load_artifact(memory_id, "entities"):
                conn.execute("insert into entities values (?,?,?,?,?)", (value["id"], value["repository_id"], value["kind"], value["qualified_name"], json.dumps(value, sort_keys=True)))
            for value in self._load_artifact(memory_id, "relations"):
                conn.execute("insert into relations values (?,?,?,?,?)", (value["id"], value["type"], value.get("source_entity"), value.get("target_key") or value.get("contract_key"), json.dumps(value, sort_keys=True)))
            for value in self._load_artifact(memory_id, "claims") + self._load_artifact(memory_id, "conflicts"):
                conn.execute("insert into claims values (?,?,?,?,?)", (value["id"], value["classification"], value["statement"], value["freshness"], json.dumps(value, sort_keys=True)))
            try:
                conn.executescript("""
                    CREATE VIRTUAL TABLE search USING fts5(kind, record_id, text);
                    INSERT INTO search SELECT 'entity', id, qualified_name || ' ' || body FROM entities;
                    INSERT INTO search SELECT 'claim', id, statement || ' ' || body FROM claims;
                    INSERT INTO search SELECT 'relation', id, relation_type || ' ' || coalesce(target_key,'') || ' ' || body FROM relations;
                """)
            except sqlite3.OperationalError:
                conn.execute("CREATE TABLE search(kind TEXT, record_id TEXT, text TEXT)")
                conn.execute("INSERT INTO search SELECT 'entity', id, qualified_name || ' ' || body FROM entities")
                conn.execute("INSERT INTO search SELECT 'claim', id, statement || ' ' || body FROM claims")
                conn.execute("INSERT INTO search SELECT 'relation', id, relation_type || ' ' || coalesce(target_key,'') || ' ' || body FROM relations")
            conn.commit()
        os.replace(temp, final)
        return {"status": "PASS", "memory_id": memory_id, "path": str(final), "sha256": sha256_file(final)}

    def search(self, memory_id: str, query: str, limit: int = 20) -> dict[str, Any]:
        if not query.strip():
            raise TUnderstandError("MEM-SEARCH-001", "Search query cannot be empty")
        db = self.runtime_root / memory_id / "index.sqlite"
        if not db.exists(): self.rebuild_index(memory_id)
        with sqlite3.connect(db) as conn:
            try:
                rows = conn.execute("select kind, record_id, text from search where search match ? limit ?", (query, limit)).fetchall()
            except sqlite3.OperationalError:
                rows = conn.execute("select kind, record_id, text from search where lower(text) like ? limit ?", (f"%{query.lower()}%", limit)).fetchall()
        return {"memory_id": memory_id, "query": query, "results": [{"kind": a, "id": b, "text": c[:1000]} for a, b, c in rows]}

    def freshness(self, memory_id: str, snapshot_id: str) -> dict[str, Any]:
        memory = self.show(memory_id)
        try:
            self.snapshots.show_snapshot(snapshot_id)
            known = True
        except Exception:
            known = False
        if not known:
            status, reason = "UNKNOWN", "The requested snapshot is not available in this context repository."
        elif memory["snapshot_id"] == snapshot_id and memory["status"] == "CURRENT":
            status, reason = "CURRENT", "Memory and requested application snapshot are identical and the memory has no conflicts."
        elif memory["snapshot_id"] == snapshot_id:
            status, reason = "STALE", f"Memory status is {memory['status']}; it cannot support an unqualified current fact."
        else:
            status, reason = "STALE", "Memory was built from a different application snapshot; invalidation or refresh is required."
        report = {
            "schema_id": "https://t-understand.dev/schemas/freshness-assessment.schema.json", "schema_version": "1.0.0",
            "memory_id": memory_id, "memory_snapshot_id": memory["snapshot_id"], "requested_snapshot_id": snapshot_id,
            "status": status, "reason": reason, "assessed_at": utc_now(),
        }
        self.contracts.validate("freshness-assessment", report)
        return report

    def invalidate(self, invalidation_id: str, memory_id: str, candidate_discovery_id: str) -> dict[str, Any]:
        if not ID_RE.fullmatch(invalidation_id):
            raise TUnderstandError("MEM-INV-001", "invalidation_id must match canonical ID pattern")
        target = self.invalidations_root / f"{invalidation_id}.yaml"
        if target.exists():
            raise TUnderstandError("MEM-INV-002", f"Invalidation already exists: {invalidation_id}")
        memory = self.show(memory_id)
        if self.discovery.validate(candidate_discovery_id)["status"] != "PASS":
            raise TUnderstandError("MEM-INV-003", "Candidate discovery is invalid")
        candidate = self.discovery.show(candidate_discovery_id)
        candidate_files = self._discovery_file_map(candidate_discovery_id)
        evidence = self._load_artifact(memory_id, "evidence")
        base_files = {(e["repository"], e["path"]): e["content_sha256"].removeprefix("sha256:") for e in evidence}
        changes = []
        for key in sorted(set(base_files) | set(candidate_files)):
            before, after = base_files.get(key), candidate_files.get(key)
            if before == after: continue
            change = "added" if before is None else "deleted" if after is None else "modified"
            changes.append({"repository_id": key[0], "path": key[1], "change": change})
        changed_keys = {(x["repository_id"], x["path"]) for x in changes}
        invalid_evidence = sorted(e["id"] for e in evidence if (e["repository"], e["path"]) in changed_keys)
        invalid_set = set(invalid_evidence)
        entities = self._load_artifact(memory_id, "entities"); relations = self._load_artifact(memory_id, "relations")
        claims = self._load_artifact(memory_id, "claims") + self._load_artifact(memory_id, "conflicts")
        affected_entities = sorted(e["id"] for e in entities if set(e["evidence"]) & invalid_set)
        affected_relations = sorted(r["id"] for r in relations if set(r["evidence"]) & invalid_set or r.get("source_entity") in set(affected_entities) or r.get("target_entity") in set(affected_entities))
        affected_claims = sorted(c["id"] for c in claims if set(c.get("evidence", [])) & invalid_set)
        report = {
            "schema_id": "https://t-understand.dev/schemas/memory-invalidation.schema.json", "schema_version": "1.0.0",
            "invalidation_id": invalidation_id, "memory_id": memory_id, "base_snapshot_id": memory["snapshot_id"],
            "candidate_snapshot_id": candidate["snapshot_id"], "status": "INVALIDATED" if changes else "UNCHANGED",
            "changed_paths": changes, "invalidated_evidence": invalid_evidence, "affected_entities": affected_entities,
            "affected_relations": affected_relations, "affected_claims": affected_claims, "generated_at": utc_now(),
        }
        self.contracts.validate("memory-invalidation", report)
        atomic_write_yaml(target, report)
        return report

    def _discovery_file_map(self, discovery_id: str) -> dict[tuple[str, str], str]:
        app = self.discovery.show(discovery_id); root = self.discovery._dir(discovery_id); result = {}
        for ref in app["repositories"]:
            repo = load_yaml(root / ref["descriptor_path"])
            for line in (root / repo["files_path"]).read_text(encoding="utf-8").splitlines():
                item = json.loads(line)
                if item["status"] == "INCLUDED": result[(item["repository_id"], item["path"])] = item["sha256"]
        return result
