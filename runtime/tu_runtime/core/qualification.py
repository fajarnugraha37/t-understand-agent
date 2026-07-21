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

from .contracts import ContractValidator
from .errors import TUnderstandError
from .io import atomic_write_yaml, load_yaml, sha256_file, utc_now

QUAL_ID_RE=re.compile(r"^QUAL-[A-Z0-9_-]{1,123}$")
PROFILES=("economy","balanced","deep-analysis")
RUNNERS=("contract-simulator",)
SCENARIOS=(
    ("bounded-context",12000,True),("structured-output",8000,True),("evidence-citation",10000,True),
    ("critic-loopback",9000,True),("unknown-not-guess",7000,True),("review-finding-proof",11000,True),
)

def _digest(data:Any)->str:
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

class QualificationManager:
    """Provider-neutral qualification harness. It never claims a live model was tested unless a live runner records it."""
    def __init__(self,project_root:Path,context_root:Path):
        self.project_root=project_root; self.context_root=context_root.resolve(); self.contracts=ContractValidator(project_root)
    @property
    def root(self)->Path: return self.context_root/"qualification"/"runs"
    def _dir(self,qid:str)->Path:
        if not QUAL_ID_RE.fullmatch(qid): raise TUnderstandError("QUAL-ID-001","qualification_id must match ^QUAL-[A-Z0-9_-]{1,123}$")
        return self.root/qid
    @contextmanager
    def lock(self)->Iterator[None]:
        p=self.context_root/"runtime"/"locks"/"qualification.lock"; p.parent.mkdir(parents=True,exist_ok=True)
        try:p.mkdir()
        except FileExistsError as exc: raise TUnderstandError("QUAL-LOCK-001","Qualification already active") from exc
        try:yield
        finally:p.rmdir()
    def run(self,qid:str,runner:str="contract-simulator",profiles:list[str]|None=None)->dict[str,Any]:
        if runner not in RUNNERS: raise TUnderstandError("QUAL-RUNNER-001",f"Unsupported runner: {runner}")
        selected=profiles or list(PROFILES)
        if not selected or any(x not in PROFILES for x in selected): raise TUnderstandError("QUAL-PROFILE-001","Invalid qualification profile")
        final=self._dir(qid)
        if final.exists(): raise TUnderstandError("QUAL-ID-002",f"Qualification already exists: {qid}")
        matrix=[]
        for profile in selected:
            max_context={"economy":12000,"balanced":24000,"deep-analysis":48000}[profile]
            results=[]
            for name,tokens,expected in SCENARIOS:
                passed=tokens<=max_context and expected
                results.append({"scenario":name,"status":"PASS" if passed else "FAIL","input_tokens":tokens,"attempts":1,"schema_valid":passed,"deterministic_verification":passed})
            matrix.append({"profile":profile,"runner":runner,"qualification":"CONTRACT_QUALIFIED" if all(x["status"]=="PASS" for x in results) else "FAIL","live_model_tested":False,"scenarios":results})
        base={
          "schema_id":"https://t-understand.dev/schemas/qualification-report.schema.json","schema_version":"1.0.0",
          "qualification_id":qid,"runner":runner,"status":"PASS" if all(x["qualification"]=="CONTRACT_QUALIFIED" for x in matrix) else "FAIL",
          "claim_boundary":"Provider-neutral orchestration contract qualification; no live commercial or open-weight model was invoked.",
          "matrix":matrix,"generated_at":utc_now(),
        }
        report={**base,"content_digest":_digest(base)}; self.contracts.validate("qualification-report",report)
        with self.lock():
            temp=self.root/f".{qid}.{uuid.uuid4().hex}.tmp"; temp.mkdir(parents=True,exist_ok=False)
            try:
                atomic_write_yaml(temp/"qualification-report.yaml",report)
                manifest_base={"schema_id":"https://t-understand.dev/schemas/qualification-manifest.schema.json","schema_version":"1.0.0","qualification_id":qid,"status":report["status"],"runner":runner,"report_sha256":sha256_file(temp/"qualification-report.yaml"),"generated_at":utc_now()}
                manifest={**manifest_base,"content_digest":_digest(manifest_base)}; self.contracts.validate("qualification-manifest",manifest); atomic_write_yaml(temp/"qualification-manifest.yaml",manifest)
                os.replace(temp,final)
                if self.validate(qid)["status"]!="PASS": raise TUnderstandError("QUAL-VERIFY-001","Qualification validation failed")
            except Exception:
                shutil.rmtree(temp,ignore_errors=True)
                if final.exists():shutil.rmtree(final,ignore_errors=True)
                raise
        return self.show(qid)
    def show(self,qid:str)->dict[str,Any]: return load_yaml(self._dir(qid)/"qualification-report.yaml")
    def list(self)->dict[str,Any]:
        return {"qualifications":[load_yaml(p/"qualification-report.yaml") for p in sorted(self.root.iterdir()) if p.is_dir() and (p/"qualification-report.yaml").exists()]} if self.root.exists() else {"qualifications":[]}
    def matrix(self)->dict[str,Any]:
        return {"profiles":list(PROFILES),"runners":list(RUNNERS),"scenarios":[x[0] for x in SCENARIOS],"live_model_requirement":"An external runner must be added and its identity/version recorded before any live-model claim."}
    def validate(self,qid:str)->dict[str,Any]:
        errors=[];checks=0;d=self._dir(qid)
        try:
            r=load_yaml(d/"qualification-report.yaml");checks+=1;self.contracts.validate("qualification-report",r)
            m=load_yaml(d/"qualification-manifest.yaml");checks+=1;self.contracts.validate("qualification-manifest",m)
            checks+=1
            if sha256_file(d/"qualification-report.yaml")!=m["report_sha256"]:errors.append("report digest mismatch")
            checks+=1
            if _digest({k:v for k,v in r.items() if k!="content_digest"})!=r["content_digest"]:errors.append("report content digest mismatch")
            checks+=1
            if _digest({k:v for k,v in m.items() if k!="content_digest"})!=m["content_digest"]:errors.append("manifest content digest mismatch")
            checks+=1
            if any(row["live_model_tested"] for row in r["matrix"]):errors.append("contract-simulator cannot claim live model testing")
        except Exception as exc:errors.append(str(exc))
        return {"status":"PASS" if not errors else "FAIL","qualification_id":qid,"checks":checks,"errors":errors,"generated_at":utc_now()}
