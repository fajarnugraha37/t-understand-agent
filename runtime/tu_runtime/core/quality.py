from __future__ import annotations

import hashlib
import os
import re
import shutil
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .contracts import ContractValidator
from .documentation import DocumentationManager
from .errors import TUnderstandError
from .exporting import ExportManager
from .io import atomic_write_yaml, load_yaml, sha256_file, utc_now
from .memory import MemoryManager
from .modeling import ModelManager
from .qna import QnAManager
from .reviewing import ReviewManager, ReviewExportManager

QUALITY_ID_RE = re.compile(r"^QLTY-[A-Z0-9_-]{1,123}$")
SUPPORTED_TARGETS = ("memory", "model", "documentation", "export", "qna", "review", "review-export")


def _digest(data: Any) -> str:
    import json
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


class QualityManager:
    """Consolidated, fail-closed verification over immutable artifact families."""

    def __init__(self, project_root: Path, context_root: Path):
        self.project_root = project_root
        self.context_root = context_root.resolve()
        self.contracts = ContractValidator(project_root)

    @property
    def root(self) -> Path:
        return self.context_root / "quality" / "reports"

    def _dir(self, quality_id: str) -> Path:
        if not QUALITY_ID_RE.fullmatch(quality_id):
            raise TUnderstandError("QUALITY-ID-001", "quality_id must match ^QLTY-[A-Z0-9_-]{1,123}$")
        return self.root / quality_id

    @contextmanager
    def lock(self) -> Iterator[None]:
        lock = self.context_root / "runtime" / "locks" / "quality.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        try:
            lock.mkdir()
        except FileExistsError as exc:
            raise TUnderstandError("QUALITY-LOCK-001", "Quality verification is already active") from exc
        try:
            yield
        finally:
            lock.rmdir()

    @staticmethod
    def parse_targets(values: list[str]) -> list[dict[str, str]]:
        if not values:
            raise TUnderstandError("QUALITY-TARGET-001", "At least one --target KIND:ID is required")
        parsed=[]
        seen=set()
        for value in values:
            if ":" not in value:
                raise TUnderstandError("QUALITY-TARGET-002", "Target must use KIND:ID")
            kind, artifact_id = value.split(":", 1)
            if kind not in SUPPORTED_TARGETS or not artifact_id:
                raise TUnderstandError("QUALITY-TARGET-003", f"Unsupported or empty target: {value}")
            key=(kind,artifact_id)
            if key in seen:
                raise TUnderstandError("QUALITY-TARGET-004", f"Duplicate target: {value}")
            seen.add(key); parsed.append({"kind":kind,"id":artifact_id})
        return sorted(parsed, key=lambda x:(x["kind"],x["id"]))

    def _manager(self, kind: str):
        return {
            "memory": MemoryManager,
            "model": ModelManager,
            "documentation": DocumentationManager,
            "export": ExportManager,
            "qna": QnAManager,
            "review": ReviewManager,
            "review-export": ReviewExportManager,
        }[kind](self.project_root, self.context_root)

    def run(self, quality_id: str, target_values: list[str], profile: str = "comprehensive") -> dict[str, Any]:
        if profile not in {"comprehensive", "release"}:
            raise TUnderstandError("QUALITY-PROFILE-001", "profile must be comprehensive or release")
        targets=self.parse_targets(target_values)
        final=self._dir(quality_id)
        if final.exists():
            raise TUnderstandError("QUALITY-ID-002", f"Quality report already exists and is immutable: {quality_id}")
        results=[]; errors=[]; total_checks=0
        for target in targets:
            manager=self._manager(target["kind"])
            report=manager.validate(target["id"])
            status=report.get("status", "FAIL")
            checks=int(report.get("checks", 1)); total_checks += max(checks,1)
            target_errors=[str(x) for x in report.get("errors", [])]
            critique_status=None
            if hasattr(manager,"critique") and target["kind"] in {"memory","model","documentation","qna"}:
                critique=manager.critique(target["id"])
                critique_status=critique.get("status", "FAIL")
                total_checks += max(int(critique.get("checks",1)),1)
                if critique_status != "PASS":
                    target_errors += [f"critique: {x}" for x in critique.get("errors", ["critique failed"])]
            effective="PASS" if status=="PASS" and (critique_status in {None,"PASS"}) else "FAIL"
            if effective!="PASS": errors += [f"{target['kind']}:{target['id']}: {x}" for x in (target_errors or ["verification failed"])]
            results.append({
                "kind":target["kind"],"artifact_id":target["id"],"status":effective,
                "validation_status":status,"critique_status":critique_status,"checks":checks,"errors":target_errors,
            })
        base={
            "schema_id":"https://t-understand.dev/schemas/quality-report.schema.json",
            "schema_version":"1.0.0","quality_id":quality_id,"profile":profile,
            "status":"PASS" if not errors else "FAIL","targets":results,"checks":total_checks,
            "errors":errors,"generated_at":utc_now(),
        }
        report={**base,"content_digest":_digest(base)}
        self.contracts.validate("quality-report",report)
        with self.lock():
            temp=self.root/f".{quality_id}.{uuid.uuid4().hex}.tmp"; temp.mkdir(parents=True,exist_ok=False)
            try:
                atomic_write_yaml(temp/"quality-report.yaml",report)
                artifact_sha=sha256_file(temp/"quality-report.yaml")
                manifest_base={
                    "schema_id":"https://t-understand.dev/schemas/quality-manifest.schema.json",
                    "schema_version":"1.0.0","quality_id":quality_id,"profile":profile,
                    "status":report["status"],"target_count":len(targets),"report_sha256":artifact_sha,
                    "generated_at":utc_now(),
                }
                manifest={**manifest_base,"content_digest":_digest(manifest_base)}
                self.contracts.validate("quality-manifest",manifest)
                atomic_write_yaml(temp/"quality-manifest.yaml",manifest)
                os.replace(temp,final)
                if self.validate(quality_id)["status"]!="PASS":
                    raise TUnderstandError("QUALITY-VERIFY-001","Published quality report failed validation")
            except Exception:
                shutil.rmtree(temp,ignore_errors=True)
                if final.exists(): shutil.rmtree(final,ignore_errors=True)
                raise
        return self.show(quality_id)

    def show(self, quality_id: str) -> dict[str, Any]:
        return load_yaml(self._dir(quality_id)/"quality-report.yaml")

    def list(self) -> dict[str, Any]:
        values=[]
        if self.root.exists():
            for p in sorted(self.root.iterdir()):
                if p.is_dir() and (p/"quality-report.yaml").exists(): values.append(load_yaml(p/"quality-report.yaml"))
        return {"quality_reports":values}

    def validate(self, quality_id: str) -> dict[str, Any]:
        errors=[]; checks=0; directory=self._dir(quality_id)
        try:
            report=load_yaml(directory/"quality-report.yaml"); checks+=1; self.contracts.validate("quality-report",report)
            manifest=load_yaml(directory/"quality-manifest.yaml"); checks+=1; self.contracts.validate("quality-manifest",manifest)
            checks+=1
            if sha256_file(directory/"quality-report.yaml") != manifest["report_sha256"]: errors.append("quality-report digest mismatch")
            base={k:v for k,v in report.items() if k!="content_digest"}; checks+=1
            if _digest(base)!=report["content_digest"]: errors.append("quality-report content digest mismatch")
            base={k:v for k,v in manifest.items() if k!="content_digest"}; checks+=1
            if _digest(base)!=manifest["content_digest"]: errors.append("quality-manifest content digest mismatch")
            checks+=1
            expected="PASS" if not report["errors"] and all(x["status"]=="PASS" for x in report["targets"]) else "FAIL"
            if report["status"]!=expected or manifest["status"]!=expected: errors.append("quality status inconsistent with target results")
        except Exception as exc:
            errors.append(str(exc))
        return {"status":"PASS" if not errors else "FAIL","quality_id":quality_id,"checks":checks,"errors":errors,"generated_at":utc_now()}
