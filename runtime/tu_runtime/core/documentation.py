from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from contextlib import contextmanager
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
    raw = "\x1f".join(str(x) for x in parts).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(raw).hexdigest()[:16].upper()}"


def _jsonl(values: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n" for x in values)


DOCUMENT_CATALOG = (
    ("application-overview", "index.md", "mixed", ["application-model"]),
    ("system-context", "architecture/system-context.md", "technical", ["architecture-model"]),
    ("dependencies", "architecture/dependencies.md", "technical", ["dependency-model", "flows"]),
    ("repositories", "repositories/index.md", "technical", ["application-model"]),
    ("interfaces", "interfaces/http-and-events.md", "technical", ["event-model", "architecture-model"]),
    ("data-model", "data/data-model.md", "technical", ["data-model"]),
    ("deployment-security", "operations/deployment-and-security.md", "technical", ["deployment-model", "security-model"]),
    ("business-overview", "business/overview.md", "business", ["business-capabilities"]),
    ("business-capabilities", "business/capabilities.md", "business", ["business-capabilities"]),
    ("actors", "business/actors.md", "business", ["actors"]),
    ("business-rules", "business/business-rules.md", "business", ["business-rules"]),
    ("lifecycle-states", "business/lifecycle-and-states.md", "business", ["state-model", "flows"]),
    ("terminology", "reference/terminology.md", "mixed", ["terminology"]),
)


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
        try: lock.mkdir()
        except FileExistsError as exc: raise TUnderstandError("DOC-LOCK-001", "Documentation mutation is already active") from exc
        try: yield
        finally: lock.rmdir()

    def _dir(self, docset_id: str) -> Path:
        if not ID_RE.fullmatch(docset_id): raise TUnderstandError("DOC-ID-001", "docset_id must match canonical ID pattern")
        return self.root / docset_id

    def generate(self, docset_id: str, model_id: str, make_current: bool = True) -> dict[str, Any]:
        final=self._dir(docset_id)
        if final.exists(): raise TUnderstandError("DOC-ID-002", f"Documentation set already exists and is immutable: {docset_id}")
        if self.models.validate(model_id)["status"]!='PASS': raise TUnderstandError("DOC-INPUT-001", "Model validation failed")
        model=self.models.show(model_id); memory=self.memory.show(model['memory_id'])
        model_docs={name:self.models.artifact(model_id,name) for name in MODEL_TYPES}
        plan={"schema_id":"https://t-understand.dev/schemas/document-plan.schema.json","schema_version":"1.0.0","docset_id":docset_id,"model_id":model_id,
              "documents":[{"document_id":x[0],"path":x[1],"audience":x[2],"source_models":x[3]} for x in DOCUMENT_CATALOG],"generated_at":utc_now()}
        self.contracts.validate('document-plan',plan)
        status='CONFLICTED' if model['status']=='CONFLICTED' else 'CURRENT'
        with self.lock():
            temp=self.root/f".{docset_id}.{uuid.uuid4().hex}.tmp"; temp.mkdir(parents=True)
            try:
                atomic_write_yaml(temp/'document-plan.yaml',plan)
                info={"docset_id":docset_id,"title":f"{model['application_id']} documentation","navigation":[{"group":"Overview","pages":["index"]},{"group":"Architecture","pages":["architecture/system-context","architecture/dependencies"]},{"group":"Repositories","pages":["repositories/index"]},{"group":"Interfaces and Data","pages":["interfaces/http-and-events","data/data-model"]},{"group":"Operations","pages":["operations/deployment-and-security"]},{"group":"Business","pages":["business/overview","business/capabilities","business/actors","business/business-rules","business/lifecycle-and-states"]},{"group":"Reference","pages":["reference/terminology"]}],"generated_at":utc_now()}
                atomic_write_yaml(temp/'information-architecture.yaml',info)
                sections=[]; traces=[]; docs=[]; covered=set(); all_record_ids={r['id'] for d in model_docs.values() for r in d['records']}
                for document_id,path,audience,sources in DOCUMENT_CATALOG:
                    title=document_id.replace('-',' ').title()
                    selected=[]
                    for source in sources: selected.extend(model_docs[source]['records'])
                    body,doc_sections=self._render_document(docset_id,document_id,title,audience,model,selected)
                    docpath=temp/'docs'/path; atomic_write_text(docpath,body)
                    docs.append({"document_id":document_id,"path":f"docs/{path}","audience":audience,"sha256":sha256_file(docpath),"sections":len(doc_sections)})
                    for section,record_ids in doc_sections:
                        sections.append(section); covered.update(record_ids)
                        trace={"schema_id":"https://t-understand.dev/schemas/documentation-trace.schema.json","schema_version":"1.0.0","docset_id":docset_id,"document_id":document_id,"section_id":section['section_id'],"model_record_ids":record_ids,"claim_ids":section['claims'],"evidence_ids":section['evidence'],"generated_at":utc_now()}
                        self.contracts.validate('documentation-trace',trace); traces.append(trace)
                for section in sections: self.contracts.validate('documentation-section',section)
                atomic_write_text(temp/'sections.jsonl',_jsonl(sections)); atomic_write_text(temp/'traceability.jsonl',_jsonl(traces))
                coverage=len(covered)/len(all_record_ids) if all_record_ids else 1.0
                gaps=sorted(all_record_ids-covered)
                ledger={"schema_id":"https://t-understand.dev/schemas/coverage-ledger.schema.json","schema_version":"1.0.0","docset_id":docset_id,"expected_documents":len(DOCUMENT_CATALOG),"generated_documents":len(docs),"covered_model_records":len(covered),"total_model_records":len(all_record_ids),"coverage":round(coverage,6),"gaps":gaps,"generated_at":utc_now()}
                self.contracts.validate('coverage-ledger',ledger); atomic_write_yaml(temp/'coverage-ledger.yaml',ledger)
                refs={}
                for name,path,records in (("document-plan",temp/'document-plan.yaml',len(plan['documents'])),("information-architecture",temp/'information-architecture.yaml',len(info['navigation'])),("sections",temp/'sections.jsonl',len(sections)),("traceability",temp/'traceability.jsonl',len(traces)),("coverage-ledger",temp/'coverage-ledger.yaml',1)):
                    refs[name]={"path":path.relative_to(temp).as_posix(),"sha256":sha256_file(path),"records":records}
                supported=[s for s in sections if s['classification'] not in {'LIMITATION','UNKNOWN_INTENT'}]
                traced=sum(1 for s in supported if s['claims'] and s['evidence'])
                base={"schema_id":"https://t-understand.dev/schemas/documentation-manifest.schema.json","schema_version":"1.0.0","docset_id":docset_id,"application_id":model['application_id'],"snapshot_id":model['snapshot_id'],"memory_id":model['memory_id'],"model_id":model_id,"status":status,"artifacts":refs,"documents":docs,"quality":{"section_traceability":round(traced/len(supported),6) if supported else 1.0,"unsupported_sections":sum(1 for s in supported if not s['claims'] or not s['evidence']),"stale_sections":sum(1 for s in sections if s['freshness']=='stale'),"catalog_coverage":round(len(docs)/len(DOCUMENT_CATALOG),6)},"generated_at":utc_now()}
                manifest={**base,"content_digest":_canonical_digest(base)}; self.contracts.validate('documentation-manifest',manifest); atomic_write_yaml(temp/'documentation-manifest.yaml',manifest)
                os.replace(temp,final)
                if self.validate(docset_id)['status']!='PASS' or self.critique(docset_id)['status']!='PASS': raise TUnderstandError("DOC-VERIFY-001","Generated documentation failed validation or critique")
                self._publish_user_view(docset_id)
                if self.validate_user_view()['status']!='PASS': raise TUnderstandError("DOC-VIEW-001","Generated user-facing documentation view failed validation")
                if make_current: atomic_write_yaml(self.root/'current.yaml',{"docset_id":docset_id,"model_id":model_id,"snapshot_id":model['snapshot_id'],"manifest_sha256":sha256_file(final/'documentation-manifest.yaml'),"updated_at":utc_now()})
            except Exception:
                shutil.rmtree(temp, ignore_errors=True)
                if final.exists():
                    shutil.rmtree(final, ignore_errors=True)
                raise
        return self.show(docset_id)


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
                "documentation-manifest.yaml": "manifest.yaml",
                "document-plan.yaml": "document-plan.yaml",
                "information-architecture.yaml": "information-architecture.yaml",
                "coverage-ledger.yaml": "coverage-ledger.yaml",
                "sections.jsonl": "sections.jsonl",
                "traceability.jsonl": "traceability.jsonl",
            }
            for source_name, target_name in mapping.items():
                shutil.copy2(source / source_name, meta / target_name)
            reports = self.reports_root / docset_id
            shutil.copy2(reports / "verification.yaml", meta / "validation.yaml")
            shutil.copy2(reports / "critique.yaml", meta / "critique.yaml")
            files = []
            for path in sorted(item for item in temp.rglob("*") if item.is_file()):
                files.append({"path": path.relative_to(temp).as_posix(), "sha256": sha256_file(path)})
            atomic_write_yaml(meta / "user-view.yaml", {
                "docset_id": docset_id,
                "entrypoint": "index.md",
                "documents": len([item for item in files if item["path"].endswith(".md") and not item["path"].startswith("_meta/")]),
                "files": files,
                "generated_at": utc_now(),
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
        required = [
            "index.md",
            "_meta/manifest.yaml",
            "_meta/document-plan.yaml",
            "_meta/coverage-ledger.yaml",
            "_meta/traceability.jsonl",
            "_meta/validation.yaml",
            "_meta/critique.yaml",
            "_meta/user-view.yaml",
        ]
        for rel in required:
            checks += 1
            if not (self.latest_output / rel).is_file():
                errors.append(f"missing user-facing documentation artifact: {rel}")
        if not errors:
            view = load_yaml(self.latest_output / "_meta/user-view.yaml")
            checks += 1
            if view.get("documents", 0) < 5:
                errors.append("comprehensive documentation requires at least five documents")
            for item in view.get("files", []):
                checks += 1
                path = self.latest_output / item["path"]
                if not path.is_file() or sha256_file(path) != item["sha256"]:
                    errors.append(f"user-facing documentation checksum mismatch: {item['path']}")
        return {"status": "PASS" if not errors else "FAIL", "checks": checks, "errors": errors}

    def _render_document(self,docset_id,document_id,title,audience,model,records):
        lines=["---",f"title: {title}",f"document_id: {document_id}",f"docset_id: {docset_id}",f"snapshot_id: {model['snapshot_id']}",f"memory_id: {model['memory_id']}",f"model_id: {model['model_id']}",f"audience: {audience}","---","",f"# {title}","",f"> Generated from immutable model `{model['model_id']}` and snapshot `{model['snapshot_id']}`. Classifications below are part of the factual contract.",""]
        sections=[]
        if not records:
            records=[]
        for idx,r in enumerate(records or [{"id":"","classification":"LIMITATION","title":"Coverage limitation","description":"No supported model records are available for this declared documentation scope.","claim_ids":[],"evidence_ids":[],"limitations":["Additional source evidence or human confirmation is required."]}],1):
            classification={"FACT":"TECHNICAL_FACT","IMPLEMENTED_BEHAVIOR":"IMPLEMENTED_BEHAVIOR","BUSINESS_INFERENCE":"BUSINESS_INFERENCE","HUMAN_CONFIRMED":"HUMAN_CONFIRMED_RULE","UNKNOWN":"UNKNOWN_INTENT","CONFLICT":"LIMITATION","LIMITATION":"LIMITATION"}[r['classification']]
            section_id=f"{document_id}-s{idx:03d}"
            claims=r.get('claim_ids',[]); evidence=r.get('evidence_ids',[])
            content=r['description']
            section={"schema_id":"https://t-understand.dev/schemas/documentation-section.schema.json","schema_version":"1.0.0","document_id":document_id,"section_id":section_id,"title":r['title'],"classification":classification,"application_snapshot":model['snapshot_id'],"content":content,"claims":claims,"evidence":evidence,"freshness":"current","coverage":"complete-for-declared-scope" if classification not in {'UNKNOWN_INTENT','LIMITATION'} else "partial","limitations":r.get('limitations',[])}
            lines += [f"## {r['title']}","",f"**Classification:** `{classification}`", "",content,"",f"**Traceability:** model record `{r.get('id') or 'none'}`; claims `{', '.join(claims) or 'none'}`; evidence `{', '.join(evidence) or 'none'}`.",""]
            if r.get('attributes'):
                lines += ["```yaml", self._yaml_fragment(r['attributes']).rstrip(), "```",""]
            for limitation in r.get('limitations',[]): lines += [f"> Limitation: {limitation}",""]
            sections.append((section,[r['id']] if r.get('id') else []))
        lines += ["## Scope limitations","","This document describes implemented and evidenced behavior only. Product intent, organizational ownership, and requirements not represented in evidence remain unknown.",""]
        return "\n".join(lines),sections

    @staticmethod
    def _yaml_fragment(value):
        import yaml
        return yaml.safe_dump(value,sort_keys=True,allow_unicode=True)

    def show(self,docset_id): return load_yaml(self._dir(docset_id)/'documentation-manifest.yaml')
    def list(self):
        current=load_yaml(self.root/'current.yaml') if (self.root/'current.yaml').exists() else None; vals=[]
        if self.root.exists():
            for p in sorted(self.root.iterdir()):
                if p.is_dir() and (p/'documentation-manifest.yaml').exists(): vals.append(self.show(p.name))
        return {"current":current,"docsets":vals}
    def _jsonl(self,docset_id,name): return [json.loads(x) for x in (self._dir(docset_id)/name).read_text().splitlines() if x]

    def validate(self,docset_id):
        errors=[]; checks=0
        try:
            m=self.show(docset_id); self.contracts.validate('documentation-manifest',m); checks+=1
            if _canonical_digest({k:v for k,v in m.items() if k!='content_digest'})!=m['content_digest']: errors.append('documentation manifest digest mismatch')
            for name,meta in m['artifacts'].items():
                p=self._dir(docset_id)/meta['path']; checks+=2
                if sha256_file(p)!=meta['sha256']: errors.append(f'{name} checksum mismatch')
            sections=self._jsonl(docset_id,'sections.jsonl'); traces=self._jsonl(docset_id,'traceability.jsonl')
            trace_keys={(t['document_id'],t['section_id']) for t in traces}
            for s in sections:
                self.contracts.validate('documentation-section',s); checks+=1
                if (s['document_id'],s['section_id']) not in trace_keys: errors.append(f"{s['section_id']} missing trace")
                if s['classification'] in {'TECHNICAL_FACT','IMPLEMENTED_BEHAVIOR','BUSINESS_INFERENCE','HUMAN_CONFIRMED_RULE'} and (not s['claims'] or not s['evidence']): errors.append(f"{s['section_id']} unsupported")
            for t in traces: self.contracts.validate('documentation-trace',t); checks+=1
            for d in m['documents']:
                p=self._dir(docset_id)/d['path']; checks+=1
                if sha256_file(p)!=d['sha256']: errors.append(f"{d['document_id']} checksum mismatch")
                if self._broken_links(p): errors.append(f"{d['document_id']} contains broken relative links")
        except Exception as exc: errors.append(str(exc))
        report={"schema_id":"https://t-understand.dev/schemas/documentation-verification.schema.json","schema_version":"1.0.0","id":docset_id,"status":"PASS" if not errors else "FAIL","checks":checks,"errors":errors,"generated_at":utc_now()}
        self.contracts.validate('documentation-verification',report); atomic_write_yaml(self.reports_root/docset_id/'verification.yaml',report); return report

    def critique(self,docset_id):
        issues=[]; checks=0; m=self.show(docset_id)
        sections=self._jsonl(docset_id,'sections.jsonl')
        for s in sections:
            checks+=1
            if s['classification']=='BUSINESS_INFERENCE' and not s.get('limitations'): issues.append({'code':'DOC-INFERENCE-DISCLOSURE','severity':'MAJOR','section_id':s['section_id']})
            if s['freshness']!='current': issues.append({'code':'DOC-STALE','severity':'MAJOR','section_id':s['section_id']})
            if s['classification'] in {'TECHNICAL_FACT','IMPLEMENTED_BEHAVIOR'} and not s['evidence']: issues.append({'code':'DOC-UNSUPPORTED','severity':'BLOCKER','section_id':s['section_id']})
        if m['quality']['catalog_coverage']<1.0: issues.append({'code':'DOC-CATALOG','severity':'BLOCKER'})
        report={"schema_id":"https://t-understand.dev/schemas/documentation-critique.schema.json","schema_version":"1.0.0","id":docset_id,"status":"PASS" if not issues else "FAIL","checks":checks,"issues":issues,"generated_at":utc_now()}
        self.contracts.validate('documentation-critique',report); atomic_write_yaml(self.reports_root/docset_id/'critique.yaml',report); return report

    def invalidate(self,invalidation_id,docset_id,memory_invalidation_id):
        if not ID_RE.fullmatch(invalidation_id): raise TUnderstandError('DOC-INV-001','Invalid invalidation ID')
        target=self.invalidations_root/f'{invalidation_id}.yaml'
        if target.exists(): raise TUnderstandError('DOC-INV-002','Document invalidation already exists')
        inv=load_yaml(self.context_root/'memory'/'invalidations'/f'{memory_invalidation_id}.yaml')
        affected_claims=set(inv.get('affected_claims',[])); affected_sections=[]; affected_docs=set()
        for s in self._jsonl(docset_id,'sections.jsonl'):
            if set(s['claims']) & affected_claims: affected_sections.append(s['section_id']); affected_docs.add(s['document_id'])
        report={"schema_id":"https://t-understand.dev/schemas/document-invalidation.schema.json","schema_version":"1.0.0","invalidation_id":invalidation_id,"docset_id":docset_id,"memory_invalidation_id":memory_invalidation_id,"status":"INVALIDATED" if affected_sections else "UNCHANGED","affected_documents":sorted(affected_docs),"affected_sections":sorted(affected_sections),"generated_at":utc_now()}
        self.contracts.validate('document-invalidation',report); atomic_write_yaml(target,report); return report

    @staticmethod
    def _broken_links(path:Path):
        text=path.read_text(encoding='utf-8'); broken=[]
        for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)',text):
            if target.startswith(('http://','https://','#','mailto:')): continue
            target=target.split('#',1)[0]
            if target and not (path.parent/target).resolve().exists(): broken.append(target)
        return broken
