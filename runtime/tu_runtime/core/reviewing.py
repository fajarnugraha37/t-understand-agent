from __future__ import annotations

import difflib
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
from .discovery import DiscoveryManager, _canonical_digest, _classification, _decode_text, _language
from .errors import TUnderstandError
from .io import atomic_write_text, atomic_write_yaml, load_yaml, sha256_bytes, sha256_file, utc_now
from .memory import MemoryManager
from .snapshot import SnapshotManager

REVIEW_RUN_RE = re.compile(r"^RVW-[A-Z0-9_-]{2,123}$")
EXPORT_RE = re.compile(r"^RVX-[A-Z0-9_-]{2,123}$")
PROFILES = ("critical-only", "balanced", "assertive", "audit")
EXPORT_PROFILES = ("canonical", "github", "gitlab", "cli", "json")
SEVERITY_ORDER = {"BLOCKER": 6, "CRITICAL": 5, "MAJOR": 4, "MINOR": 3, "TRIVIAL": 2, "INFO": 1}


def _stable(prefix: str, *parts: Any) -> str:
    raw = "\x1f".join(str(p) for p in parts).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(raw).hexdigest()[:16].upper()}"


def _jsonl(values: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n" for v in values)


class ReviewManager:
    def __init__(self, project_root: Path, context_root: Path):
        self.project_root = project_root
        self.context_root = context_root.resolve()
        self.snapshots = SnapshotManager(project_root, context_root)
        self.discovery = DiscoveryManager(project_root, context_root)
        self.memory = MemoryManager(project_root, context_root)
        self.contracts = ContractValidator(project_root)

    @property
    def root(self) -> Path:
        return self.context_root / "review-runs"

    @property
    def reports_root(self) -> Path:
        return self.context_root / "reports" / "reviews"

    def _dir(self, run_id: str) -> Path:
        if not REVIEW_RUN_RE.fullmatch(run_id):
            raise TUnderstandError("REVIEW-ID-001", "review_run_id must match ^RVW-[A-Z0-9_-]{2,123}$")
        return self.root / run_id

    @contextmanager
    def lock(self) -> Iterator[None]:
        lock = self.context_root / "runtime" / "locks" / "review.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        try: lock.mkdir()
        except FileExistsError as exc: raise TUnderstandError("REVIEW-LOCK-001", "Review generation is already active") from exc
        try: yield
        finally: lock.rmdir()

    def run(self, run_id: str, review_target_id: str, profile: str = "balanced") -> dict[str, Any]:
        if profile not in PROFILES: raise TUnderstandError("REVIEW-PROFILE-001", f"Unsupported review profile: {profile}")
        final = self._dir(run_id)
        if final.exists(): raise TUnderstandError("REVIEW-ID-002", f"Review run already exists and is immutable: {run_id}")
        target_validation = self.snapshots.validate_review_target(review_target_id)
        if target_validation["status"] != "PASS": raise TUnderstandError("REVIEW-TARGET-001", "Review target failed validation")
        target = self.snapshots.show_review_target(review_target_id)
        candidate_id = target["candidate"]["snapshot_id"]
        baseline_id = target["baseline"]["snapshot_id"] if target["baseline"] else None
        candidate = self._snapshot_files(candidate_id)
        baseline = self._snapshot_files(baseline_id) if baseline_id else {}
        changed, coverage, diff_texts = self._compare(run_id, target["mode"], candidate, baseline)
        evidence, findings = self._review_rules(run_id, target, changed, candidate, baseline, diff_texts)
        findings = self._dedupe_and_filter(findings, profile)
        critique = self._critique(run_id, findings, evidence)
        critic_decisions = {item["finding_id"]: item["decision"] for item in critique["decisions"]}
        promoted = []
        for finding in findings:
            decision = critic_decisions.get(finding["id"], "NOT_REQUIRED")
            if decision == "REJECTED":
                continue
            if finding["severity"] in {"BLOCKER", "CRITICAL", "MAJOR"}:
                finding["critic_status"] = "survived"
                self.contracts.validate("review-finding", finding)
            promoted.append(finding)
        findings = promoted
        calibration = self._calibrate(run_id, findings)
        impacts = self._impact(candidate_id, changed)
        counts = Counter(f["severity"].lower() for f in findings)
        status = "BLOCKED" if any(f["severity"] in {"BLOCKER", "CRITICAL"} for f in findings) else "FINDINGS" if findings else "PASS"
        merge_gate = "BLOCK" if status == "BLOCKED" else "WARN" if findings else "PASS"
        analysis = {
            "schema_id": "https://t-understand.dev/schemas/review-analysis.schema.json", "schema_version": "1.0.0",
            "review_run_id": run_id, "review_target_id": review_target_id, "mode": target["mode"], "profile": profile,
            "status": status, "changed_files": len(changed), "finding_count": len(findings),
            "summary": self._summary_text(target["mode"], changed, findings, merge_gate), "generated_at": utc_now(),
        }
        self.contracts.validate("review-analysis", analysis)

        with self.lock():
            if final.exists(): raise TUnderstandError("REVIEW-ID-002", f"Review run already exists and is immutable: {run_id}")
            temp = self.root / f".{run_id}.{uuid.uuid4().hex}.tmp"; temp.mkdir(parents=True, exist_ok=False)
            try:
                atomic_write_yaml(temp / "review-analysis.yaml", analysis)
                atomic_write_yaml(temp / "coverage.yaml", coverage)
                atomic_write_text(temp / "changed-files.jsonl", _jsonl(changed))
                atomic_write_text(temp / "review-evidence.jsonl", _jsonl(evidence))
                atomic_write_text(temp / "findings.jsonl", _jsonl(findings))
                atomic_write_yaml(temp / "finding-critique.yaml", critique)
                atomic_write_yaml(temp / "severity-calibration.yaml", calibration)
                atomic_write_yaml(temp / "merge-gate.yaml", {"review_run_id": run_id, "gate": merge_gate, "blocking_findings": [f["id"] for f in findings if f["severity"] in {"BLOCKER", "CRITICAL"}], "warning_findings": [f["id"] for f in findings if f["severity"] not in {"BLOCKER", "CRITICAL"}]})
                atomic_write_yaml(temp / "traceability.yaml", {"review_run_id": run_id, "review_target_id": review_target_id, "candidate_snapshot": candidate_id, "baseline_snapshot": baseline_id, "finding_evidence": {f["id"]: f["evidence"] for f in findings}})
                atomic_write_text(temp / "review-summary.md", self._render_summary(analysis, counts, merge_gate))
                atomic_write_text(temp / "walkthrough.md", self._render_walkthrough(changed))
                atomic_write_text(temp / "changed-files.md", self._render_changed_files(changed))
                atomic_write_text(temp / "sequence-diagrams.md", self._render_sequences(changed, impacts))
                atomic_write_text(temp / "impact-analysis.md", self._render_impact(impacts))
                atomic_write_text(temp / "cross-repository-impact.md", self._render_cross_repo(impacts))
                atomic_write_text(temp / "issue-assessment.md", self._render_issue_assessment(findings))
                atomic_write_text(temp / "test-gap-analysis.md", self._render_test_gaps(findings))
                atomic_write_text(temp / "findings.md", self._render_findings(findings, evidence))
                atomic_write_text(temp / "suggested-fixes.patch", self._suggested_patch(findings))
                atomic_write_text(temp / "inline-comments.json", json.dumps(self._inline_comments(findings), indent=2, ensure_ascii=False) + "\n")
                pre_verify = self._verify_documents(run_id, temp, findings, evidence, changed, target)
                atomic_write_yaml(temp / "review-verification.yaml", pre_verify)
                artifacts = {}
                for p in sorted(temp.iterdir()):
                    if p.is_file(): artifacts[p.name] = {"path": p.name, "sha256": sha256_file(p)}
                count_doc = {"changed_files": len(changed), "findings": len(findings), **{s.lower(): counts.get(s.lower(), 0) for s in ["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "TRIVIAL", "INFO"]}}
                base = {
                    "schema_id": "https://t-understand.dev/schemas/review-manifest.schema.json", "schema_version": "1.0.0",
                    "review_run_id": run_id, "review_target_id": review_target_id, "application_id": target["application_id"],
                    "candidate_snapshot": candidate_id, "baseline_snapshot": baseline_id, "mode": target["mode"], "profile": profile,
                    "status": status, "artifacts": artifacts, "counts": count_doc, "merge_gate": merge_gate, "generated_at": utc_now(),
                }
                manifest = {**base, "content_digest": _canonical_digest(base)}
                self.contracts.validate("review-manifest", manifest)
                atomic_write_yaml(temp / "review-manifest.yaml", manifest)
                os.replace(temp, final)
                report = self.validate(run_id)
                if report["status"] != "PASS": raise TUnderstandError("REVIEW-VERIFY-001", "Generated review failed verification")
            except Exception:
                shutil.rmtree(temp, ignore_errors=True)
                if final.exists(): shutil.rmtree(final, ignore_errors=True)
                raise
        return self.show(run_id)

    def _snapshot_files(self, snapshot_id: str | None) -> dict[tuple[str, str], dict[str, Any]]:
        if not snapshot_id: return {}
        snap = self.snapshots.show_snapshot(snapshot_id)
        result = {}
        for repo_ref in snap["repositories"]:
            repo = repo_ref["repository_id"]
            desc = load_yaml(self.context_root / "snapshots" / snapshot_id / repo_ref["descriptor_path"])
            view = self.discovery.view(snapshot_id, repo)
            revision = desc["resolved"]["commit"]
            for rec in view.list_files():
                key = (repo, rec["path"])
                if rec.get("special"):
                    result[key] = {"repository": repo, "path": rec["path"], "revision": revision, "data": None, "special": rec["special"], "sha256": None}
                    continue
                data = view.read(rec)
                result[key] = {"repository": repo, "path": rec["path"], "revision": revision, "data": data, "special": None, "sha256": sha256_bytes(data)}
        return result

    def _compare(self, run_id: str, mode: str, candidate: dict, baseline: dict):
        changed = []; exclusions = []; reviewed = 0; diffs = {}
        keys = sorted(set(candidate) | set(baseline)) if mode == "DIFF" else sorted(candidate)
        for key in keys:
            c = candidate.get(key); b = baseline.get(key); repo, path = key
            if mode == "STATIC_AUDIT": status = "AUDITED"
            elif b is None: status = "ADDED"
            elif c is None: status = "REMOVED"
            elif c["sha256"] != b["sha256"]: status = "MODIFIED"
            else: continue
            source = c or b
            if source.get("special"):
                exclusions.append({"repository": repo, "path": path, "reason": source["special"]}); binary = True; additions = deletions = 0
            else:
                ctext = _decode_text(c["data"]) if c else ""
                btext = _decode_text(b["data"]) if b else ""
                binary = (c is not None and ctext is None) or (b is not None and btext is None)
                if binary:
                    exclusions.append({"repository": repo, "path": path, "reason": "binary"}); additions = deletions = 0
                else:
                    reviewed += 1
                    c_lines = (ctext or "").splitlines(); b_lines = (btext or "").splitlines()
                    if mode == "STATIC_AUDIT": additions = len(c_lines); deletions = 0; diffs[key] = {"candidate": ctext or "", "baseline": "", "added_lines": set(range(1, len(c_lines)+1)), "removed_lines": set()}
                    else:
                        matcher = difflib.SequenceMatcher(a=b_lines, b=c_lines)
                        add = set(); rem = set()
                        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                            if tag in {"insert", "replace"}: add.update(range(j1+1, j2+1))
                            if tag in {"delete", "replace"}: rem.update(range(i1+1, i2+1))
                        additions = len(add); deletions = len(rem); diffs[key] = {"candidate": ctext or "", "baseline": btext or "", "added_lines": add, "removed_lines": rem}
            item = {
                "schema_id": "https://t-understand.dev/schemas/review-changed-file.schema.json", "schema_version": "1.0.0",
                "id": _stable("CHG", run_id, repo, path), "repository": repo, "path": path, "status": status,
                "additions": additions, "deletions": deletions, "binary": binary,
                "candidate_revision": c["revision"] if c else b["revision"], "baseline_revision": b["revision"] if b else None,
                "language": _language(path), "classification": _classification(path, False, False),
            }
            self.contracts.validate("review-changed-file", item); changed.append(item)
        considered = len(keys); excluded = len(exclusions)
        coverage = {
            "schema_id": "https://t-understand.dev/schemas/review-coverage.schema.json", "schema_version": "1.0.0",
            "review_run_id": run_id, "mode": mode, "repositories": len({k[0] for k in keys}) or 1,
            "files_considered": considered, "files_reviewed": reviewed, "files_excluded": excluded,
            "coverage": round(reviewed / max(1, considered), 6), "exclusions": exclusions,
        }
        self.contracts.validate("review-coverage", coverage)
        return changed, coverage, diffs

    def _review_rules(self, run_id, target, changed, candidate, baseline, diffs):
        evidence = []; findings = []; evidence_seen = {}
        def ev(repo, path, revision, text, line, rule, snapshot):
            key=(repo,path,revision,line,rule)
            if key in evidence_seen: return evidence_seen[key]
            lines=text.splitlines(); excerpt=lines[line-1].strip() if 0 < line <= len(lines) else ""
            eid=_stable("EVD-REVIEW",run_id,*key)
            doc={"schema_id":"https://t-understand.dev/schemas/evidence-record.schema.json","schema_version":"1.0.0","id":eid,"application_snapshot":snapshot,"repository":repo,"revision":revision,"path":path,"content_sha256":"sha256:"+hashlib.sha256(text.encode()).hexdigest(),"locator":{"start_line":line,"rule":rule},"kind":"source","captured_at":utc_now(),"excerpt":excerpt,"freshness":"current"}
            self.contracts.validate("evidence-record",doc); evidence.append(doc); evidence_seen[key]=eid; return eid
        def add(rule, typ, severity, title, observation, failure, impact, recommendation, repo, path, line, text, revision, snapshot, confidence="high", business=None):
            eid=ev(repo,path,revision,text,line,rule,snapshot)
            fid=_stable("FND",run_id,rule,repo,path,line)
            critic="challenged" if severity in {"BLOCKER","CRITICAL","MAJOR"} else "not-required"
            doc={"schema_id":"https://t-understand.dev/schemas/review-finding.schema.json","schema_version":"1.0.0","id":fid,"review_snapshot":snapshot,"type":typ,"severity":severity,"confidence":confidence,"location":{"repository":repo,"revision":revision,"path":path,"start_line":line,"end_line":line},"title":title,"observation":observation,"evidence":[eid],"failure_scenario":[failure],"technical_impact":[impact],"business_impact":business or [],"recommendation":recommendation,"required_verification":["Run the affected test suite and verify the exact path under the immutable candidate snapshot."],"critic_status":critic}
            self.contracts.validate("review-finding",doc); findings.append(doc)
        rules=[
          ("TLS_VERIFY_DISABLED",re.compile(r"(?i)(verify\s*=\s*false|rejectUnauthorized\s*:\s*false|trustAll\s*\([^)]*\)\s*;?)"),"SECURITY","CRITICAL","TLS certificate verification is disabled","The changed code disables peer certificate verification.","An attacker on the network can impersonate the upstream service.","Confidentiality and integrity of service-to-service traffic can be lost.","Use platform trust stores and explicit certificate validation; never disable verification."),
          ("HARDCODED_SECRET",re.compile(r"(?i)\b(password|secret|api[_-]?key|access[_-]?token)\b\s*[:=]\s*[\"'][^\"'${}]{6,}[\"']"),"SECURITY","MAJOR","Credential-like value is hardcoded","A credential-like literal is committed in source or configuration.","The value can be exposed through repository access, logs, packages, or images.","Credential rotation and incident response may be required.","Move the value to an approved secret store and rotate any real credential."),
          ("EMPTY_CATCH",re.compile(r"catch\s*\([^)]*\)\s*\{\s*\}",re.S),"RELIABILITY","MAJOR","Exception is silently swallowed","An empty catch block discards the failure without recovery or telemetry.","The operation can fail while callers observe apparent success.","Failures become difficult to diagnose and may leave partial state.","Handle the exception, propagate it, or record structured telemetry with an explicit recovery decision."),
          ("DESTRUCTIVE_MIGRATION",re.compile(r"(?im)^\s*(drop\s+table|drop\s+column|truncate\s+table)\b"),"DATABASE_MIGRATION","MAJOR","Destructive database operation is introduced","The changed migration contains a destructive DDL operation.","Deployment can irreversibly remove production data or break older application versions.","Data loss or deployment rollback failure can occur.","Use an expand-and-contract migration with backups, compatibility windows, and explicit operational approval."),
        ]
        candidate_snapshot=target["candidate"]["snapshot_id"]
        for item in changed:
            key=(item["repository"],item["path"]); diff=diffs.get(key)
            if not diff or item["binary"]: continue
            text=diff["candidate"] if item["status"]!="REMOVED" else diff["baseline"]
            active=diff["added_lines"] if item["status"]!="REMOVED" else diff["removed_lines"]
            rev=item["candidate_revision"] if item["status"]!="REMOVED" else item["baseline_revision"] or item["candidate_revision"]
            snapshot=candidate_snapshot if item["status"]!="REMOVED" else target["baseline"]["snapshot_id"] if target["baseline"] else candidate_snapshot
            for rule,regex,typ,sev,title,obs,fail,impact,rec in rules:
                for match in regex.finditer(text):
                    line=text.count("\n",0,match.start())+1
                    if target["mode"]=="DIFF" and line not in active: continue
                    add(rule,typ,sev,title,obs,fail,impact,rec,item["repository"],item["path"],line,text,rev,snapshot)
            if target["mode"]=="DIFF" and item["status"]=="REMOVED" and self._contract_path(item["path"]):
                line=next(iter(active),1)
                add("CONTRACT_REMOVAL","BREAKING_CHANGE","MAJOR","Contract file or operation was removed","A contract-bearing file or operation is removed in the candidate snapshot.","Existing clients or consumers can continue calling the removed contract.","Consumers can fail at runtime or during generation/deployment.","Confirm all consumers are migrated and publish a compatibility/deprecation plan before removal.",item["repository"],item["path"],line,text,rev,snapshot,"medium")
        if target["mode"]=="DIFF":
            changed_source=[x for x in changed if x["classification"]=="source" and x["status"]!="REMOVED" and not x["binary"]]
            changed_tests=[x for x in changed if x["classification"]=="test"]
            if changed_source and not changed_tests:
                item=changed_source[0]; key=(item["repository"],item["path"]); text=diffs[key]["candidate"]
                add("TEST_GAP","TEST_GAP","MINOR","Production code changed without corresponding test changes","The candidate changes production source files but no test file changed in the review target.","Behavior can regress without a focused automated check covering the changed path.","Regression risk is higher and review confidence is lower.","Add or update focused tests, or document why existing tests already cover the changed behavior.",item["repository"],item["path"],1,text,item["candidate_revision"],candidate_snapshot,"medium")
        return evidence, findings

    @staticmethod
    def _contract_path(path: str) -> bool:
        name=PurePosixPath(path).name.lower(); suffix=PurePosixPath(path).suffix.lower()
        return name.startswith(("openapi","asyncapi")) or suffix in {".proto",".graphql",".gql",".bpmn",".dmn"}

    def _dedupe_and_filter(self, findings, profile):
        unique={}
        for f in findings:
            key=(f["type"],f["location"]["repository"],f["location"]["path"],f["title"])
            old=unique.get(key)
            if old is None or SEVERITY_ORDER[f["severity"]]>SEVERITY_ORDER[old["severity"]]: unique[key]=f
        vals=sorted(unique.values(),key=lambda f:(-SEVERITY_ORDER[f["severity"]],f["location"]["repository"],f["location"]["path"],f["location"]["start_line"],f["id"]))
        if profile=="critical-only": vals=[f for f in vals if f["severity"] in {"BLOCKER","CRITICAL"}]
        elif profile=="balanced": vals=[f for f in vals if SEVERITY_ORDER[f["severity"]]>=3 and f["confidence"]!="low"]
        elif profile=="assertive": vals=[f for f in vals if f["severity"]!="INFO"]
        return vals

    def _critique(self, run_id, findings, evidence):
        evidence_ids={e["id"] for e in evidence}; decisions=[]; failed=False
        for f in findings:
            required=f["severity"] in {"BLOCKER","CRITICAL","MAJOR"}
            survives=bool(f["evidence"]) and all(e in evidence_ids for e in f["evidence"]) and bool(f["failure_scenario"]) and bool(f["technical_impact"])
            decision="SURVIVED" if required and survives else "REJECTED" if required else "NOT_REQUIRED"
            if required and not survives: failed=True
            decisions.append({"finding_id":f["id"],"decision":decision,"reason":"Exact evidence, failure scenario, and impact are present." if survives else "Finding did not satisfy the required evidence challenge."})
        doc={"schema_id":"https://t-understand.dev/schemas/finding-critique.schema.json","schema_version":"1.0.0","review_run_id":run_id,"status":"FAIL" if failed else "PASS","decisions":decisions,"generated_at":utc_now()}
        self.contracts.validate("finding-critique",doc); return doc

    def _calibrate(self, run_id, findings):
        items=[{"finding_id":f["id"],"severity":f["severity"],"confidence":f["confidence"],"rationale":"Severity follows the deterministic rule taxonomy and observed failure mode."} for f in findings]
        doc={"schema_id":"https://t-understand.dev/schemas/severity-calibration.schema.json","schema_version":"1.0.0","review_run_id":run_id,"status":"PASS","items":items,"generated_at":utc_now()}
        self.contracts.validate("severity-calibration",doc); return doc

    def _impact(self, snapshot_id, changed):
        result={"snapshot_id":snapshot_id,"changed_paths":[],"affected_entities":[],"affected_relations":[],"cross_repository":[]}
        changed_keys={(x["repository"],x["path"]) for x in changed}
        result["changed_paths"]=[{"repository":r,"path":p} for r,p in sorted(changed_keys)]
        current=self.context_root/"memory"/"current.yaml"
        if not current.exists(): return result
        pointer=load_yaml(current); memory_id=pointer.get("memory_id")
        try:
            manifest=self.memory.show(memory_id)
            if manifest["snapshot_id"]!=snapshot_id: return result
            entities=self.memory._load_artifact(memory_id,"entities"); relations=self.memory._load_artifact(memory_id,"relations")
            affected_ids=set()
            for e in entities:
                evs=[]
                for eid in e.get("evidence",[]):
                    ev=next((x for x in self.memory._load_artifact(memory_id,"evidence") if x["id"]==eid),None)
                    if ev and (ev["repository"],ev["path"]) in changed_keys: evs.append(eid)
                if evs: result["affected_entities"].append({"id":e["id"],"kind":e["kind"],"repository":e["repository_id"],"evidence":evs}); affected_ids.add(e["id"])
            for rel in relations:
                if rel.get("source_entity") in affected_ids or rel.get("target_entity") in affected_ids:
                    result["affected_relations"].append({"id":rel["id"],"type":rel["type"],"source":rel.get("source_entity"),"target":rel.get("target_entity") or rel.get("contract_key")})
                    if rel["id"].startswith("XREL-"): result["cross_repository"].append(rel["id"])
        except Exception:
            return result
        return result

    @staticmethod
    def _summary_text(mode, changed, findings, gate): return f"{mode} reviewed {len(changed)} files and produced {len(findings)} evidence-backed findings. Merge gate: {gate}."
    def _render_summary(self,a,counts,gate):
        return f"# Review summary\n\n**Mode:** `{a['mode']}`  \n**Profile:** `{a['profile']}`  \n**Merge gate:** `{gate}`\n\n{a['summary']}\n\n## Findings by severity\n\n"+"\n".join(f"- {s}: {counts.get(s.lower(),0)}" for s in ["BLOCKER","CRITICAL","MAJOR","MINOR","TRIVIAL","INFO"])+"\n"
    def _render_walkthrough(self,changed):
        lines=["# Change walkthrough",""]
        for x in changed: lines.append(f"- **{x['status']}** `{x['repository']}:{x['path']}` (+{x['additions']} / -{x['deletions']})")
        return "\n".join(lines)+"\n"
    def _render_changed_files(self,changed):
        lines=["# Changed files","","| Repository | Path | Status | + | - | Classification |","|---|---|---:|---:|---:|---|"]
        lines += [f"| {x['repository']} | `{x['path']}` | {x['status']} | {x['additions']} | {x['deletions']} | {x['classification']} |" for x in changed]
        return "\n".join(lines)+"\n"
    def _render_sequences(self,changed,impacts):
        repos=sorted({x['repository'] for x in changed}); lines=["# Sequence diagrams",""]
        if len(repos)>1:
            lines += ["```mermaid","sequenceDiagram",f"    participant A as {repos[0]}",f"    participant B as {repos[1]}","    A->>B: Review cross-repository contracts and impacts","```",""]
        else: lines += ["No evidenced cross-repository sequence was derived for this review target.",""]
        return "\n".join(lines)
    def _render_impact(self,i): return "# Impact analysis\n\n"+f"Changed paths: {len(i['changed_paths'])}; affected entities: {len(i['affected_entities'])}; affected relations: {len(i['affected_relations'])}.\n\n```json\n{json.dumps(i,indent=2)}\n```\n"
    def _render_cross_repo(self,i): return "# Cross-repository impact\n\n"+("\n".join(f"- `{x}`" for x in i['cross_repository']) if i['cross_repository'] else "No evidenced cross-repository relation was affected.")+"\n"
    def _render_issue_assessment(self,findings): return "# Issue assessment\n\n"+("\n".join(f"- `{f['id']}` {f['severity']} {f['title']}" for f in findings) if findings else "No findings survived evidence validation and profile filtering.")+"\n"
    def _render_test_gaps(self,findings):
        gaps=[f for f in findings if f['type']=='TEST_GAP']; return "# Test-gap analysis\n\n"+("\n".join(f"- {f['observation']} (`{f['location']['path']}`)" for f in gaps) if gaps else "No deterministic test-gap finding was produced.")+"\n"
    def _render_findings(self,findings,evidence):
        ev={e['id']:e for e in evidence}; lines=["# Review findings",""]
        for f in findings:
            loc=f['location']; lines += [f"## {f['severity']} · {f['title']}","",f"`{loc['repository']}@{loc['revision'][:12]}:{loc['path']}:{loc['start_line']}`", "",f['observation'],"",f"**Failure scenario:** {f['failure_scenario'][0]}","",f"**Impact:** {f['technical_impact'][0]}","",f"**Recommendation:** {f['recommendation']}","",f"**Evidence:** {', '.join(f['evidence'])}",""]
        if not findings: lines.append("No findings survived evidence validation and profile filtering.")
        return "\n".join(lines)+"\n"
    def _suggested_patch(self,findings):
        lines=["# Suggested fixes are advisory and are never applied by t-understand."]
        for f in findings:
            lines += [f"# {f['id']} {f['location']['repository']}:{f['location']['path']}:{f['location']['start_line']}",f"# {f['recommendation']}"]
        return "\n".join(lines)+"\n"
    def _inline_comments(self,findings):
        return [{"finding_id":f['id'],"path":f['location']['path'],"line":f['location']['start_line'],"repository":f['location']['repository'],"severity":f['severity'],"body":f"**{f['title']}**\n\n{f['observation']}\n\nRecommendation: {f['recommendation']}"} for f in findings]

    def _verify_documents(self,run_id,temp,findings,evidence,changed,target):
        errors=[]; checks=0; evidence_ids={e['id'] for e in evidence}
        for f in findings:
            try: self.contracts.validate('review-finding',f); checks+=1
            except Exception as exc: errors.append(str(exc))
            if not all(e in evidence_ids for e in f['evidence']): errors.append(f"{f['id']} references missing evidence")
            if f['severity'] in {'BLOCKER','CRITICAL','MAJOR'} and f['critic_status'] not in {'challenged','survived','rejected'}: errors.append(f"{f['id']} lacks critic challenge")
        for c in changed:
            try: self.contracts.validate('review-changed-file',c); checks+=1
            except Exception as exc: errors.append(str(exc))
        return {"schema_id":"https://t-understand.dev/schemas/review-verification.schema.json","schema_version":"1.0.0","review_run_id":run_id,"status":"PASS" if not errors else "FAIL","checks":checks,"errors":errors,"generated_at":utc_now()}

    def show(self,run_id):
        doc=load_yaml(self._dir(run_id)/'review-manifest.yaml'); self.contracts.validate('review-manifest',doc); return doc
    def list(self):
        vals=[]
        if self.root.exists():
            for p in sorted(self.root.iterdir()):
                if p.is_dir() and (p/'review-manifest.yaml').exists(): vals.append(self.show(p.name))
        return {'reviews':vals}
    def findings(self,run_id): return [json.loads(x) for x in (self._dir(run_id)/'findings.jsonl').read_text().splitlines() if x]
    def validate(self,run_id):
        errors=[]; checks=0
        try:
            m=self.show(run_id); checks+=1
            if _canonical_digest({k:v for k,v in m.items() if k!='content_digest'})!=m['content_digest']: errors.append('review manifest content digest mismatch')
            for name,meta in m['artifacts'].items():
                p=self._dir(run_id)/meta['path']; checks+=1
                if not p.is_file() or sha256_file(p)!=meta['sha256']: errors.append(f'artifact checksum mismatch: {name}')
            fs=self.findings(run_id)
            for f in fs: self.contracts.validate('review-finding',f); checks+=1
            target=self.snapshots.validate_review_target(m['review_target_id']); checks+=1
            if target['status']!='PASS': errors.append('review target validation failed')
            critique=load_yaml(self._dir(run_id)/'finding-critique.yaml'); self.contracts.validate('finding-critique',critique); checks+=1
            if critique['status']!='PASS': errors.append('finding critique failed')
            rv=load_yaml(self._dir(run_id)/'review-verification.yaml'); self.contracts.validate('review-verification',rv); checks+=1
            if rv['status']!='PASS': errors.extend(rv['errors'])
        except Exception as exc: errors.append(str(exc))
        report={"schema_id":"https://t-understand.dev/schemas/review-verification.schema.json","schema_version":"1.0.0","review_run_id":run_id,"status":"PASS" if not errors else "FAIL","checks":checks,"errors":errors,"generated_at":utc_now()}
        self.reports_root.mkdir(parents=True,exist_ok=True); atomic_write_yaml(self.reports_root/f'{run_id}-verification.yaml',report); return report


class ReviewExportManager:
    def __init__(self,project_root:Path,context_root:Path):
        self.project_root=project_root; self.context_root=context_root.resolve(); self.reviews=ReviewManager(project_root,context_root); self.contracts=ContractValidator(project_root)
    @property
    def root(self): return self.context_root/'review-exports'
    def _dir(self,export_id):
        if not EXPORT_RE.fullmatch(export_id): raise TUnderstandError('RVX-ID-001','export_id must match ^RVX-[A-Z0-9_-]{2,123}$')
        return self.root/export_id
    def create(self,export_id,run_id,profile):
        if profile not in EXPORT_PROFILES: raise TUnderstandError('RVX-PROFILE-001',f'Unsupported profile: {profile}')
        final=self._dir(export_id)
        if final.exists(): raise TUnderstandError('RVX-ID-002','Review export already exists and is immutable')
        if self.reviews.validate(run_id)['status']!='PASS': raise TUnderstandError('RVX-INPUT-001','Review run failed validation')
        source=self.reviews._dir(run_id); manifest=self.reviews.show(run_id); temp=self.root/f'.{export_id}.{uuid.uuid4().hex}.tmp'; temp.mkdir(parents=True)
        try:
            if profile=='canonical':
                for p in source.iterdir():
                    if p.is_file(): shutil.copy2(p,temp/p.name)
            elif profile=='github':
                shutil.copy2(source/'review-summary.md',temp/'summary.md'); shutil.copy2(source/'findings.md',temp/'review.md'); shutil.copy2(source/'inline-comments.json',temp/'inline-comments.json'); shutil.copy2(source/'suggested-fixes.patch',temp/'suggested-fixes.patch')
            elif profile=='gitlab':
                shutil.copy2(source/'review-summary.md',temp/'summary.md'); comments=json.loads((source/'inline-comments.json').read_text()); atomic_write_text(temp/'discussions.json',json.dumps({'discussions':comments},indent=2)+'\n')
            elif profile=='cli':
                text=(source/'review-summary.md').read_text()+"\n"+(source/'findings.md').read_text(); atomic_write_text(temp/'review.txt',re.sub(r'[`#*]','',text))
            else:
                payload={'manifest':manifest,'findings':self.reviews.findings(run_id),'inline_comments':json.loads((source/'inline-comments.json').read_text())}; atomic_write_text(temp/'review.json',json.dumps(payload,indent=2,ensure_ascii=False)+'\n')
            artifacts={p.name:{'path':p.name,'sha256':sha256_file(p)} for p in sorted(temp.iterdir()) if p.is_file()}
            base={'schema_id':'https://t-understand.dev/schemas/review-export-manifest.schema.json','schema_version':'1.0.0','export_id':export_id,'review_run_id':run_id,'profile':profile,'status':'EXPORTED','artifacts':artifacts,'source_manifest_sha256':sha256_file(source/'review-manifest.yaml'),'generated_at':utc_now()}
            doc={**base,'content_digest':_canonical_digest(base)}; self.contracts.validate('review-export-manifest',doc); atomic_write_yaml(temp/'review-export-manifest.yaml',doc); os.replace(temp,final)
            if self.validate(export_id)['status']!='PASS': raise TUnderstandError('RVX-VERIFY-001','Review export failed validation')
        except Exception:
            shutil.rmtree(temp,ignore_errors=True)
            if final.exists(): shutil.rmtree(final,ignore_errors=True)
            raise
        return self.show(export_id)
    def show(self,export_id):
        d=load_yaml(self._dir(export_id)/'review-export-manifest.yaml'); self.contracts.validate('review-export-manifest',d); return d
    def list(self):
        vals=[]
        if self.root.exists():
            for p in sorted(self.root.iterdir()):
                if p.is_dir() and (p/'review-export-manifest.yaml').exists(): vals.append(self.show(p.name))
        return {'exports':vals}
    def validate(self,export_id):
        errors=[];checks=0
        try:
            m=self.show(export_id); checks+=1
            if _canonical_digest({k:v for k,v in m.items() if k!='content_digest'})!=m['content_digest']: errors.append('export manifest content digest mismatch')
            source=self.reviews._dir(m['review_run_id'])/'review-manifest.yaml'; checks+=1
            if sha256_file(source)!=m['source_manifest_sha256']: errors.append('source review manifest checksum mismatch')
            for name,meta in m['artifacts'].items():
                p=self._dir(export_id)/meta['path']; checks+=1
                if not p.is_file() or sha256_file(p)!=meta['sha256']: errors.append(f'artifact checksum mismatch: {name}')
        except Exception as exc: errors.append(str(exc))
        return {'status':'PASS' if not errors else 'FAIL','export_id':export_id,'checks':checks,'errors':errors,'generated_at':utc_now()}
