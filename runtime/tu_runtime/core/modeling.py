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
    "application-model", "architecture-model", "dependency-model", "data-model",
    "event-model", "deployment-model", "security-model", "business-capabilities",
    "business-rules", "actors", "state-model", "flows", "terminology",
)


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
        app=memory["application_id"]; snap=memory["snapshot_id"]; mid=memory["memory_id"]
        grouped: dict[str, list[dict[str, Any]]] = {x: [] for x in MODEL_TYPES}
        by_repo: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for e in entities: by_repo[e["repository_id"]].append(e)
        for repo, ents in sorted(by_repo.items()):
            eids=[e["id"] for e in ents]; cs,ev=self._support(eids,[],claim_by_entity,claim_by_relation)
            grouped["application-model"].append(self._record(model_id,"application-model",repo,"FACT",repo,
                f"Repository {repo} is present in the analyzed application snapshot with {len(ents)} extracted entities.",cs,ev,eids,attributes={"repository_id":repo,"entity_count":len(ents),"entity_kinds":sorted({e['kind'] for e in ents})}))
            grouped["architecture-model"].append(self._record(model_id,"architecture-model",repo,"IMPLEMENTED_BEHAVIOR",f"Component {repo}",
                f"The implementation surface for {repo} exposes the recorded entry points and contracts listed in its attributes.",cs,ev,eids,attributes={"repository_id":repo,"entry_points":[e['qualified_name'] for e in ents if e['kind']=='entry-point'],"contracts":[e['qualified_name'] for e in ents if e['kind'] in {'http-provider','interface','event-producer','event-consumer'}]}))
        for rel in relations:
            rid=rel["id"]; cs,ev=self._support([], [rid], claim_by_entity, claim_by_relation)
            classification="BUSINESS_INFERENCE" if rel.get("classification") in {"INFERENCE","INFERRED"} else "IMPLEMENTED_BEHAVIOR"
            target=rel.get("target_repository") or rel.get("target_entity") or rel.get("target_key") or rel.get("contract_key")
            rec=self._record(model_id,"dependency-model",rid,classification,rel["type"],f"{rel.get('source_repository') or rel.get('source_entity')} {rel['type']} {target}.",cs or [c['id'] for c in claims if set(c.get('evidence',[])) & set(rel.get('evidence',[]))],ev or rel.get('evidence',[]),[x for x in (rel.get('source_entity'),rel.get('target_entity')) if x],[rid],{"contract_key":rel.get('contract_key') or rel.get('target_key'),"source_repository":rel.get('source_repository'),"target_repository":rel.get('target_repository')},limitations=["Relationship semantics are inferred from exact complementary source surfaces; runtime execution was not observed."] if classification=="BUSINESS_INFERENCE" else None)
            grouped["dependency-model"].append(rec)
            if rel["type"] in {"PRODUCES_FOR"}:
                grouped["event-model"].append({**rec,"id":_id('MODREC','event-model',rid),"model_type":"event-model"})
            if rel["type"] in {"SHARES_DATA_WITH","READS","WRITES"}:
                grouped["data-model"].append({**rec,"id":_id('MODREC','data-model',rid),"model_type":"data-model"})
            if rel["type"] in {"CALLS","PRODUCES_FOR"}:
                grouped["flows"].append({**rec,"id":_id('MODREC','flows',rid),"model_type":"flows"})
        for e in entities:
            cs,ev=self._support([e["id"]],[],claim_by_entity,claim_by_relation)
            if e["kind"] in {"event-producer","event-consumer"}:
                grouped["event-model"].append(self._record(model_id,"event-model",e["id"],"IMPLEMENTED_BEHAVIOR",e["qualified_name"],f"{e['repository_id']} contains {e['kind']} {e['qualified_name']}.",cs,ev or e['evidence'],[e['id']],attributes={"repository_id":e['repository_id'],"kind":e['kind']}))
            if e["kind"] in {"data-reader","data-writer","table","view"}:
                grouped["data-model"].append(self._record(model_id,"data-model",e["id"],"IMPLEMENTED_BEHAVIOR",e["qualified_name"],f"{e['repository_id']} contains the recorded data access surface {e['qualified_name']}.",cs,ev or e['evidence'],[e['id']],attributes={"repository_id":e['repository_id'],"kind":e['kind']}))
            if e["kind"] in {"http-provider","interface","entry-point"}:
                grouped["business-capabilities"].append(self._record(model_id,"business-capabilities",e["id"],"BUSINESS_INFERENCE",e["name"],f"The implemented surface {e['qualified_name']} indicates a candidate application capability; its business intent is not asserted.",cs,ev or e['evidence'],[e['id']],attributes={"repository_id":e['repository_id'],"technical_surface":e['qualified_name']},limitations=["Capability name and intent require human confirmation."]))
            if e["kind"] in {"http-provider","interface","event-consumer","event-producer"}:
                grouped["actors"].append(self._record(model_id,"actors",e["id"],"BUSINESS_INFERENCE",f"Actor interacting with {e['name']}",f"An external or internal actor interacts with {e['qualified_name']}; actor identity is not derivable from source alone.",cs,ev or e['evidence'],[e['id']],limitations=["Actor identity and organizational ownership are unknown."]))
            if any(x in e["kind"] for x in ("deploy","kubernetes","terraform","docker")):
                grouped["deployment-model"].append(self._record(model_id,"deployment-model",e["id"],"IMPLEMENTED_BEHAVIOR",e["qualified_name"],f"Deployment-related source surface {e['qualified_name']} is present.",cs,ev or e['evidence'],[e['id']]))
            if any(x in e["kind"] for x in ("security","authorization","authentication")):
                grouped["security-model"].append(self._record(model_id,"security-model",e["id"],"IMPLEMENTED_BEHAVIOR",e["qualified_name"],f"Security-related source surface {e['qualified_name']} is present.",cs,ev or e['evidence'],[e['id']]))
        # conservative unknowns rather than invented knowledge
        unknowns={
            "deployment-model":"No complete deployment topology can be proven from the current evidence.",
            "security-model":"No complete security architecture can be proven from the current evidence.",
            "business-rules":"Business rules are not promoted from implementation unless an explicit validated rule is evidenced.",
            "state-model":"No complete domain state machine can be proven from the current evidence.",
        }
        for typ,msg in unknowns.items():
            if not grouped[typ]:
                grouped[typ].append(self._record(model_id,typ,"unknown","UNKNOWN",typ.replace('-',' ').title(),msg,[],[],limitations=[msg]))
        terms={}
        for e in entities:
            q=e["qualified_name"]
            if q.startswith(("http:","event:","table:")):
                terms[q]=e
        for term,e in sorted(terms.items()):
            cs,ev=self._support([e['id']],[],claim_by_entity,claim_by_relation)
            grouped["terminology"].append(self._record(model_id,"terminology",term,"IMPLEMENTED_BEHAVIOR",term,f"Canonical technical term observed in {e['repository_id']}.",cs,ev or e['evidence'],[e['id']],attributes={"term":term,"repository_id":e['repository_id']}))
        if conflicts:
            for c in conflicts:
                grouped["architecture-model"].append(self._record(model_id,"architecture-model",c['id'],"CONFLICT","Conflicting architecture evidence",c['statement'],c.get('conflicting_claims',[]),c.get('evidence',[]),attributes={"conflict_id":c['id']}))
        result={}
        for typ in MODEL_TYPES:
            result[typ]={"schema_id":"https://t-understand.dev/schemas/model-artifact.schema.json","schema_version":"1.0.0","model_id":model_id,"model_type":typ,"application_id":app,"snapshot_id":snap,"memory_id":mid,"status":"CONFLICTED" if conflicts else "CURRENT","records":sorted(grouped[typ],key=lambda x:x['id']),"limitations":[]}
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
