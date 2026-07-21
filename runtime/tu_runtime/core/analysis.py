from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

from .contracts import ContractValidator
from .discovery import AdapterManager, DiscoveryManager, _canonical_digest, _decode_text
from .errors import TUnderstandError
from .io import atomic_write_text, atomic_write_yaml, load_yaml, sha256_file, utc_now

ID_RE = re.compile(r"^[A-Z][A-Z0-9_-]{2,63}$")
CALL_STOP = {
    "if", "for", "while", "switch", "catch", "return", "new", "throw", "sizeof", "typeof",
    "class", "interface", "function", "def", "fn", "func", "println", "print", "log", "debug",
    "warn", "error", "assert", "super", "this", "self", "require", "import",
}


def _id(prefix: str, *parts: Any) -> str:
    raw = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(raw).hexdigest()[:16].upper()}"


def _jsonl(values: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n" for value in values)


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, max(0, offset)) + 1


def _evidence_kind(classification: str) -> str:
    return {
        "test": "test", "configuration": "configuration", "contract": "contract",
        "migration": "migration", "deployment": "deployment", "documentation": "secondary-documentation",
    }.get(classification, "source")


def _scope_match(repository_id: str, path: str, scopes: set[str] | None) -> bool:
    if not scopes:
        return True
    exact = f"{repository_id}:{path}"
    return exact in scopes or any(exact.startswith(scope.rstrip("/") + "/") for scope in scopes)


class AnalysisManager:
    def __init__(self, project_root: Path, context_root: Path):
        self.project_root = project_root
        self.context_root = context_root.resolve()
        self.adapters = AdapterManager(project_root, context_root)
        self.discovery = DiscoveryManager(project_root, context_root)
        self.contracts = ContractValidator(project_root)

    @property
    def root(self) -> Path:
        return self.context_root / "analysis"

    @contextmanager
    def lock(self) -> Iterator[None]:
        lock = self.context_root / "runtime" / "locks" / "analysis.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        try:
            lock.mkdir()
        except FileExistsError as exc:
            raise TUnderstandError("ANL-LOCK-001", "Analysis mutation is already active") from exc
        try:
            yield
        finally:
            lock.rmdir()

    def _dir(self, analysis_id: str) -> Path:
        if not ID_RE.fullmatch(analysis_id):
            raise TUnderstandError("ANL-ID-001", "analysis_id must match ^[A-Z][A-Z0-9_-]{2,63}$")
        return self.root / analysis_id

    def run(self, analysis_id: str, extraction_id: str, scopes: list[str] | None = None) -> dict[str, Any]:
        scope_set = set(scopes or [])
        return self._execute(analysis_id, extraction_id, scope_set, None)

    def refresh(self, analysis_id: str, base_analysis_id: str, extraction_id: str) -> dict[str, Any]:
        base = self.show(base_analysis_id)
        extraction = self.adapters.show(extraction_id)
        if base["application_id"] != self.discovery.show(extraction["discovery_id"])["application_id"]:
            raise TUnderstandError("ANL-REFRESH-001", "Base analysis and candidate extraction belong to different applications")
        base_files = self._file_digest_map(base_analysis_id)
        candidate_files = self._extraction_digest_map(extraction_id)
        changed = sorted({key for key in set(base_files) | set(candidate_files) if base_files.get(key) != candidate_files.get(key)})
        return self._execute(analysis_id, extraction_id, set(changed), base_analysis_id)

    def _execute(self, analysis_id: str, extraction_id: str, scopes: set[str], base_analysis_id: str | None) -> dict[str, Any]:
        final = self._dir(analysis_id)
        if final.exists():
            raise TUnderstandError("ANL-ID-002", f"Analysis already exists and is immutable: {analysis_id}")
        extraction_validation = self.adapters.validate(extraction_id)
        if extraction_validation["status"] != "PASS":
            raise TUnderstandError("ANL-INPUT-001", f"Adapter extraction validation failed: {extraction_id}")
        extraction = self.adapters.show(extraction_id)
        discovery = self.discovery.show(extraction["discovery_id"])
        snapshot = self.discovery.snapshots.show_snapshot(extraction["snapshot_id"])
        revisions = {item["repository_id"]: item["resolved_commit"] for item in snapshot["repositories"]}
        records = self._load_extractions(extraction_id)
        selected = [r for r in records if _scope_match(r["repository_id"], r["path"], scopes)] if (scopes or base_analysis_id) else records
        candidate_keys = {f"{r['repository_id']}:{r['path']}" for r in records}

        with self.lock():
            if final.exists():
                raise TUnderstandError("ANL-ID-002", f"Analysis already exists and is immutable: {analysis_id}")
            temp = self.root / f".{analysis_id}.{uuid.uuid4().hex}.tmp"
            temp.mkdir(parents=True)
            try:
                evidence: list[dict[str, Any]] = []
                entities: list[dict[str, Any]] = []
                relations: list[dict[str, Any]] = []
                observations: list[dict[str, Any]] = []
                analyzed_files: dict[str, str] = {}

                if base_analysis_id:
                    changed = {f"{r['repository_id']}:{r['path']}" for r in selected}
                    removed = set(self._file_digest_map(base_analysis_id)) - candidate_keys
                    changed |= removed
                    evidence, entities, relations, observations = self._reuse_base(
                        base_analysis_id, changed, extraction["snapshot_id"], revisions
                    )

                for record in selected:
                    key = f"{record['repository_id']}:{record['path']}"
                    analyzed_files[key] = record["file_sha256"]
                    self._analyze_record(record, discovery, revisions[record["repository_id"]], evidence, entities, relations, observations)

                evidence = self._dedupe(evidence, "id")
                entities = self._dedupe(entities, "id")
                relations = self._dedupe(relations, "id")
                observations = self._dedupe(observations, "id")
                self._validate_references(evidence, entities, relations, observations)

                artifacts = {}
                for name, values, contract in (
                    ("evidence", evidence, "evidence-record"),
                    ("entities", entities, "analysis-entity"),
                    ("relations", relations, "analysis-relation"),
                    ("observations", observations, "analysis-observation"),
                ):
                    for value in values:
                        self.contracts.validate(contract, value)
                    path = temp / f"{name}.jsonl"
                    atomic_write_text(path, _jsonl(values))
                    artifacts[name] = {"path": path.name, "sha256": sha256_file(path), "records": len(values)}

                structural = {
                    "schema_id": "https://t-understand.dev/schemas/analysis-summary.schema.json",
                    "schema_version": "1.0.0", "analysis_id": analysis_id,
                    "snapshot_id": extraction["snapshot_id"], "kind": "structural",
                    "counts": {
                        "entities": len(entities),
                        "declarations": sum(1 for x in relations if x["type"] == "DECLARES"),
                        "dependencies": sum(1 for x in relations if x["type"] == "DEPENDS_ON"),
                        "interfaces": sum(1 for x in entities if x["kind"] in {"interface", "http-provider", "http-consumer", "event-producer", "event-consumer"}),
                        "evidence": len(evidence),
                    },
                    "limitations": ["Phase 7 structural identities are syntax and exact-contract based; dynamic loading and generated runtime types are not executed."],
                    "generated_at": utc_now(),
                }
                behavioral = {
                    "schema_id": "https://t-understand.dev/schemas/analysis-summary.schema.json",
                    "schema_version": "1.0.0", "analysis_id": analysis_id,
                    "snapshot_id": extraction["snapshot_id"], "kind": "behavioral",
                    "counts": {key.lower(): value for key, value in sorted(Counter(x["type"] for x in relations if x["type"] not in {"DECLARES", "DEPENDS_ON"}).items())},
                    "limitations": ["Lexical call targets remain conservative and are never represented as business intent.", "Runtime reflection, generated code, and external deployment state are not executed."],
                    "generated_at": utc_now(),
                }
                for summary_name, summary in (("structural_summary", structural), ("behavioral_summary", behavioral)):
                    self.contracts.validate("analysis-summary", summary)
                    summary_path = temp / ("structural-analysis.yaml" if summary_name == "structural_summary" else "behavior-analysis.yaml")
                    atomic_write_yaml(summary_path, summary)
                    artifacts[summary_name] = {"path": summary_path.name, "sha256": sha256_file(summary_path), "records": 1}

                file_map = self._extraction_digest_map(extraction_id)
                coverage = {
                    "repositories": len({r["repository_id"] for r in records}),
                    "files_available": len(records),
                    "files_analyzed": len(selected),
                    "files_reused": max(0, len(file_map) - len(selected)) if base_analysis_id else 0,
                    "files_skipped": max(0, len(records) - len(selected)) if scopes and not base_analysis_id else 0,
                    "observations": len(observations),
                }
                mode = "incremental" if base_analysis_id else ("scoped" if scopes else "full")
                base = {
                    "schema_id": "https://t-understand.dev/schemas/analysis-run.schema.json",
                    "schema_version": "1.0.0",
                    "analysis_id": analysis_id,
                    "application_id": discovery["application_id"],
                    "snapshot_id": extraction["snapshot_id"],
                    "extraction_id": extraction_id,
                    "status": "ANALYZED",
                    "mode": mode,
                    "artifacts": artifacts,
                    "coverage": coverage,
                    "scopes": sorted(scopes),
                    "generated_at": utc_now(),
                }
                if base_analysis_id:
                    base["base_analysis_id"] = base_analysis_id
                doc = {**base, "content_digest": _canonical_digest(base)}
                self.contracts.validate("analysis-run", doc)
                atomic_write_yaml(temp / "analysis-run.yaml", doc)
                os.replace(temp, final)
            except Exception:
                shutil.rmtree(temp, ignore_errors=True)
                raise
        return self.show(analysis_id)

    def _load_extractions(self, extraction_id: str) -> list[dict[str, Any]]:
        run = self.adapters.show(extraction_id)
        path = self.context_root / "extractions" / extraction_id / run["records_path"]
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    def _extraction_digest_map(self, extraction_id: str) -> dict[str, str]:
        return {f"{r['repository_id']}:{r['path']}": r["file_sha256"] for r in self._load_extractions(extraction_id)}

    def _file_digest_map(self, analysis_id: str) -> dict[str, str]:
        values = self._load_artifact(analysis_id, "evidence")
        result = {}
        for item in values:
            result[f"{item['repository']}:{item['path']}"] = item["content_sha256"].removeprefix("sha256:")
        return result

    def _reuse_base(self, base_id: str, changed: set[str], snapshot_id: str, revisions: dict[str, str]):
        base_evidence = self._load_artifact(base_id, "evidence")
        invalid_evidence = {
            value["id"] for value in base_evidence
            if f"{value['repository']}:{value['path']}" in changed
        }
        reused = []
        for artifact in ("evidence", "entities", "relations", "observations"):
            values = base_evidence if artifact == "evidence" else self._load_artifact(base_id, artifact)
            filtered = []
            for value in values:
                repo = value.get("repository") or value.get("repository_id")
                path = value.get("path")
                if artifact == "evidence" and value["id"] in invalid_evidence:
                    continue
                if artifact != "evidence" and set(value.get("evidence", [])) & invalid_evidence:
                    continue
                if path and f"{repo}:{path}" in changed:
                    continue
                copy = dict(value)
                if "application_snapshot" in copy:
                    copy["application_snapshot"] = snapshot_id
                if artifact == "evidence":
                    copy["revision"] = revisions[repo]
                    copy["freshness"] = "current"
                elif artifact in {"entities", "relations"}:
                    copy["freshness"] = "current"
                filtered.append(copy)
            reused.append(filtered)
        return tuple(reused)

    def _analyze_record(self, record: dict[str, Any], discovery: dict[str, Any], revision: str,
                        evidence: list[dict[str, Any]], entities: list[dict[str, Any]],
                        relations: list[dict[str, Any]], observations: list[dict[str, Any]]) -> None:
        repo, path = record["repository_id"], record["path"]
        file_evidence = self._evidence(discovery["snapshot_id"], repo, revision, path, record["file_sha256"], 1, "file", path, "source")
        evidence.append(file_evidence)
        file_entity = self._entity(discovery["snapshot_id"], repo, "file", PurePosixPath(path).name, f"file:{path}", path, 1, file_evidence["id"])
        entities.append(file_entity)

        for category, entity_kind in (("declarations", None), ("interfaces", "interface"), ("entry_points", "entry-point"), ("configuration_keys", "configuration-key")):
            for item in record.get(category, []):
                kind = entity_kind or item["kind"]
                detail = item.get("detail", "")
                qname = self._qualified(kind, item["name"], detail)
                ev = self._evidence(discovery["snapshot_id"], repo, revision, path, record["file_sha256"], item["line"], kind, item["name"], "contract" if category == "interfaces" else "source")
                evidence.append(ev)
                entity = self._entity(discovery["snapshot_id"], repo, kind, item["name"], qname, path, item["line"], ev["id"], detail)
                entities.append(entity)
                relations.append(self._relation(discovery["snapshot_id"], repo, "DECLARES", file_entity["id"], qname, ev["id"], "OBSERVED", "high", "The adapter recorded this declaration at the exact source location.", entity["id"]))
                observations.append(self._observation(discovery["snapshot_id"], repo, "structure", kind, path, item["line"], file_entity["qualified_name"], qname, ev["id"], "high", detail))

        for item in record.get("dependencies", []):
            ev = self._evidence(discovery["snapshot_id"], repo, revision, path, record["file_sha256"], item["line"], "dependency", item["name"], "source")
            evidence.append(ev)
            target = f"dependency:{item['name']}"
            relations.append(self._relation(discovery["snapshot_id"], repo, "DEPENDS_ON", file_entity["id"], target, ev["id"], "OBSERVED", "high", "The source contains an explicit dependency/import declaration."))
            observations.append(self._observation(discovery["snapshot_id"], repo, "structure", "dependency", path, item["line"], file_entity["qualified_name"], target, ev["id"], "high", item.get("detail")))

        # Source-bound behavioral extraction. Read only the captured snapshot view.
        try:
            view = self.discovery.view(discovery["snapshot_id"], repo)
            source = {r["path"]: r for r in view.list_files()}.get(path)
            if source is None:
                return
            data = view.read(source)
            if hashlib.sha256(data).hexdigest() != record["file_sha256"]:
                raise TUnderstandError("ANL-HASH-001", f"Analysis source digest mismatch: {repo}:{path}")
            text = _decode_text(data)
            if text is not None:
                self._behavior(text, discovery["snapshot_id"], repo, revision, path, record["file_sha256"], file_entity, evidence, entities, relations, observations)
        except TUnderstandError:
            raise

    def _behavior(self, text: str, snapshot_id: str, repo: str, revision: str, path: str, digest: str,
                  file_entity: dict[str, Any], evidence: list[dict[str, Any]], entities: list[dict[str, Any]],
                  relations: list[dict[str, Any]], observations: list[dict[str, Any]]) -> None:
        def add(category: str, kind: str, rel_type: str, target: str, match: re.Match[str], confidence: str, reasoning: str, entity_kind: str | None = None):
            line = _line(text, match.start())
            ev = self._evidence(snapshot_id, repo, revision, path, digest, line, kind, target, "source")
            evidence.append(ev)
            target_entity = None
            if entity_kind:
                target_entity = self._entity(snapshot_id, repo, entity_kind, target.split(":")[-1], target, path, line, ev["id"])
                entities.append(target_entity)
            relations.append(self._relation(snapshot_id, repo, rel_type, file_entity["id"], target, ev["id"], "OBSERVED" if confidence == "high" else "INFERRED", confidence, reasoning, target_entity["id"] if target_entity else None))
            observations.append(self._observation(snapshot_id, repo, category, kind, path, line, file_entity["qualified_name"], target, ev["id"], confidence, match.group(0)[:500]))

        # Event producers and consumers.
        event_patterns = [
            ("producer", "PRODUCES", r"(?:kafkaTemplate|producer|publisher|eventBus)\s*\.\s*(?:send|publish|emit)\s*\(\s*[\"']([^\"']+)", 1),
            ("consumer", "CONSUMES", r"@KafkaListener\s*\([^)]*topics?\s*=\s*[\"']([^\"']+)", 1),
            ("consumer", "CONSUMES", r"(?:subscribe|consume)\s*\(\s*\{?\s*(?:topic\s*:\s*)?[\"']([^\"']+)", 1),
        ]
        for role, rel, pattern, group in event_patterns:
            for m in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                topic = m.group(group).strip()
                add("event", f"event-{role}", rel, f"event:{topic}", m, "high", "An explicit event API call or listener annotation names this topic.", f"event-{role}")

        # HTTP provider/consumer candidates.
        for m in re.finditer(r"@(?:Get|Post|Put|Patch|Delete)Mapping\s*\(\s*[\"']([^\"']+)", text):
            method = re.search(r"@(Get|Post|Put|Patch|Delete)Mapping", m.group(0)).group(1).upper()
            add("http", "http-provider", "EXPOSES", f"http:{method}:{m.group(1)}", m, "high", "A framework route annotation explicitly exposes this method and path.", "http-provider")
        for m in re.finditer(r"\b(get|post|put|patch|delete)\s*\(\s*[\"'](/[^\"']*)", text, re.IGNORECASE):
            add("http", "http-consumer", "CALLS", f"http:{m.group(1).upper()}:{m.group(2)}", m, "medium", "A client-style method call contains an explicit HTTP method and relative path.", "http-consumer")

        # Data access from literal SQL.
        for m in re.finditer(r"\b(?:select\b.*?\bfrom|join)\s+([A-Za-z_][\w.]*)", text, re.IGNORECASE | re.DOTALL):
            add("data", "data-reader", "READS", f"data:{m.group(1).lower()}", m, "high", "A literal SQL read names this relation.", "data-reader")
        for m in re.finditer(r"\b(?:insert\s+into|update|delete\s+from)\s+([A-Za-z_][\w.]*)", text, re.IGNORECASE):
            add("data", "data-writer", "WRITES", f"data:{m.group(1).lower()}", m, "high", "A literal SQL mutation names this relation.", "data-writer")

        # Configuration keys.
        for m in re.finditer(r"(?:getenv|System\.getenv|System\.getProperty|@Value)\s*\(\s*[\"']([^\"']+)", text):
            add("configuration", "configuration-use", "USES_CONFIG", f"config:{m.group(1)}", m, "high", "A configuration API call explicitly names this key.", "configuration-use")

        # Transaction and failure boundaries.
        for m in re.finditer(r"@Transactional\b|\bBEGIN\s+TRANSACTION\b|\btransaction\s*\(", text, re.IGNORECASE):
            add("transaction", "transaction-boundary", "TRANSACTION_BOUNDARY", f"transaction:{path}:{_line(text,m.start())}", m, "high", "An explicit transaction annotation or API marks this boundary.", "transaction-boundary")
        for m in re.finditer(r"\bthrow\s+new\s+([A-Za-z_][\w.]*)|\braise\s+([A-Za-z_][\w.]*)", text):
            name = next(group for group in m.groups() if group)
            add("failure", "failure", "THROWS", f"failure:{name}", m, "high", "The source explicitly raises or throws this failure type.", "failure")

        # Conservative call candidates. Medium confidence because lexical calls may be dynamic or shadowed.
        for m in re.finditer(r"\b([A-Za-z_][\w.]*)\s*\(", text):
            name = m.group(1).split(".")[-1]
            if name.lower() in CALL_STOP or name in {"String", "Integer", "Long", "List", "Map", "Set"}:
                continue
            add("call", "call", "CALLS", f"call:{name}", m, "medium", "A lexical invocation was observed; target resolution remains conservative in Phase 7.")

    def _qualified(self, kind: str, name: str, detail: str) -> str:
        if kind == "interface" and detail:
            first = detail.split()[0].upper()
            if first in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE"}:
                return f"http:{first}:{name}"
        if kind in {"channel", "message", "topic"}:
            return f"event:{name}"
        if kind in {"table", "view", "materialized view"}:
            return f"data:{name.lower()}"
        return f"{kind}:{name}"

    def _evidence(self, snapshot: str, repo: str, revision: str, path: str, digest: str, line: int,
                  kind: str, name: str, source_kind: str) -> dict[str, Any]:
        eid = _id("EVD", repo, path, line, kind, name, digest)
        return {
            "schema_id": "https://t-understand.dev/schemas/evidence-record.schema.json",
            "schema_version": "1.0.0", "id": eid, "application_snapshot": snapshot,
            "repository": repo, "revision": revision, "path": path,
            "content_sha256": f"sha256:{digest}", "locator": {"line": max(1, line), "symbol": name},
            "kind": _evidence_kind(source_kind), "captured_at": utc_now(), "freshness": "current",
        }

    def _entity(self, snapshot: str, repo: str, kind: str, name: str, qualified: str, path: str,
                line: int, evidence_id: str, detail: str | None = None) -> dict[str, Any]:
        result = {
            "schema_id": "https://t-understand.dev/schemas/analysis-entity.schema.json",
            "schema_version": "1.0.0", "id": _id("ENT", repo, kind, qualified),
            "application_snapshot": snapshot, "repository_id": repo, "kind": kind,
            "name": name, "qualified_name": qualified, "path": path, "line": max(1, line),
            "evidence": [evidence_id], "freshness": "current",
        }
        if detail:
            result["detail"] = detail[:2000]
        return result

    def _relation(self, snapshot: str, repo: str, rel_type: str, source: str, target_key: str,
                  evidence_id: str, classification: str, confidence: str, reasoning: str,
                  target_entity: str | None = None) -> dict[str, Any]:
        result = {
            "schema_id": "https://t-understand.dev/schemas/analysis-relation.schema.json",
            "schema_version": "1.0.0", "id": _id("REL", repo, rel_type, source, target_key),
            "application_snapshot": snapshot, "repository_id": repo, "type": rel_type,
            "source_entity": source, "target_key": target_key, "evidence": [evidence_id],
            "classification": classification, "confidence": confidence, "reasoning": reasoning,
            "freshness": "current",
        }
        if target_entity:
            result["target_entity"] = target_entity
        return result

    def _observation(self, snapshot: str, repo: str, category: str, kind: str, path: str, line: int,
                     subject: str, obj: str, evidence_id: str, confidence: str, detail: str | None = None) -> dict[str, Any]:
        result = {
            "schema_id": "https://t-understand.dev/schemas/analysis-observation.schema.json",
            "schema_version": "1.0.0", "id": _id("OBS", repo, path, line, category, kind, obj),
            "application_snapshot": snapshot, "repository_id": repo, "category": category,
            "kind": kind, "path": path, "line": max(1, line), "subject": subject, "object": obj,
            "evidence": [evidence_id], "confidence": confidence,
        }
        if detail:
            result["detail"] = detail[:2000]
        return result

    @staticmethod
    def _dedupe(values: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for value in values:
            identity = value[key]
            if identity not in merged:
                merged[identity] = value
            else:
                for field in ("evidence",):
                    if field in value:
                        merged[identity][field] = sorted(set(merged[identity].get(field, [])) | set(value[field]))
        return sorted(merged.values(), key=lambda value: value[key])

    @staticmethod
    def _validate_references(evidence, entities, relations, observations):
        evidence_ids = {x["id"] for x in evidence}
        entity_ids = {x["id"] for x in entities}
        for collection in (entities, relations, observations):
            for value in collection:
                missing = set(value.get("evidence", [])) - evidence_ids
                if missing:
                    raise TUnderstandError("ANL-REF-001", f"Missing evidence references: {sorted(missing)}")
        for value in relations:
            if value["source_entity"] not in entity_ids:
                raise TUnderstandError("ANL-REF-002", f"Missing source entity: {value['source_entity']}")
            if value.get("target_entity") and value["target_entity"] not in entity_ids:
                raise TUnderstandError("ANL-REF-003", f"Missing target entity: {value['target_entity']}")

    def _load_artifact(self, analysis_id: str, name: str) -> list[dict[str, Any]]:
        doc = self.show(analysis_id)
        path = self._dir(analysis_id) / doc["artifacts"][name]["path"]
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    def show(self, analysis_id: str) -> dict[str, Any]:
        return load_yaml(self._dir(analysis_id) / "analysis-run.yaml")

    def list(self) -> dict[str, Any]:
        values = []
        if self.root.exists():
            for path in sorted(self.root.glob("*/analysis-run.yaml")):
                doc = load_yaml(path)
                values.append({"analysis_id": doc["analysis_id"], "snapshot_id": doc["snapshot_id"], "mode": doc["mode"], "status": doc["status"]})
        return {"analyses": values}

    def validate(self, analysis_id: str) -> dict[str, Any]:
        errors: list[str] = []
        checks = 0
        try:
            doc = self.show(analysis_id); checks += 1
            self.contracts.validate("analysis-run", doc)
            base = {k: v for k, v in doc.items() if k != "content_digest"}; checks += 1
            if _canonical_digest(base) != doc["content_digest"]:
                errors.append("analysis content_digest mismatch")
            loaded = {}
            for name, contract in (("evidence", "evidence-record"), ("entities", "analysis-entity"), ("relations", "analysis-relation"), ("observations", "analysis-observation")):
                meta = doc["artifacts"][name]; path = self._dir(analysis_id) / meta["path"]; checks += 2
                if sha256_file(path) != meta["sha256"]:
                    errors.append(f"{name} checksum mismatch")
                values = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
                if len(values) != meta["records"]:
                    errors.append(f"{name} record count mismatch")
                for value in values:
                    self.contracts.validate(contract, value); checks += 1
                loaded[name] = values
            for summary_name in ("structural_summary", "behavioral_summary"):
                meta = doc["artifacts"][summary_name]; path = self._dir(analysis_id) / meta["path"]; checks += 2
                if sha256_file(path) != meta["sha256"]:
                    errors.append(f"{summary_name} checksum mismatch")
                self.contracts.validate("analysis-summary", load_yaml(path))
            self._validate_references(loaded["evidence"], loaded["entities"], loaded["relations"], loaded["observations"]); checks += 1
        except Exception as exc:
            errors.append(str(exc))
        report = {"status": "PASS" if not errors else "FAIL", "analysis_id": analysis_id, "checks": checks, "errors": errors, "validated_at": utc_now()}
        atomic_write_yaml(self._dir(analysis_id) / "validation-report.yaml", report)
        return report
