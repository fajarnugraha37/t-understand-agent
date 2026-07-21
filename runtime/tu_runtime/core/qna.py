from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .contracts import ContractValidator
from .discovery import DiscoveryManager, _canonical_digest
from .errors import TUnderstandError
from .io import atomic_write_text, atomic_write_yaml, load_yaml, sha256_bytes, sha256_file, utc_now
from .memory import MemoryManager
from .snapshot import SnapshotManager

ANSWER_ID_RE = re.compile(r"^QNA-[A-Z0-9_-]{2,123}$")
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "could", "do", "does", "for", "from",
    "how", "i", "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "what", "when",
    "where", "which", "who", "why", "with", "yang", "dan", "atau", "apa", "bagaimana", "di", "ke",
    "dari", "untuk", "ini", "itu", "adalah", "apakah", "pada", "dalam", "kode", "codebase",
}


def _jsonl(values: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n" for v in values)


def _stable(prefix: str, *parts: Any) -> str:
    raw = "\x1f".join(str(p) for p in parts).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(raw).hexdigest()[:16].upper()}"


def _terms(text: str) -> list[str]:
    return sorted({t for t in re.findall(r"[a-zA-Z0-9_.:/-]+", text.lower()) if len(t) > 1 and t not in STOPWORDS})


class QnAManager:
    def __init__(self, project_root: Path, context_root: Path):
        self.project_root = project_root
        self.context_root = context_root.resolve()
        self.memory = MemoryManager(project_root, context_root)
        self.snapshots = SnapshotManager(project_root, context_root)
        self.discovery = DiscoveryManager(project_root, context_root)
        self.contracts = ContractValidator(project_root)

    @property
    def root(self) -> Path:
        return self.context_root / "qna" / "answers"

    @property
    def reports_root(self) -> Path:
        return self.context_root / "reports" / "qna"

    def _dir(self, answer_id: str) -> Path:
        if not ANSWER_ID_RE.fullmatch(answer_id):
            raise TUnderstandError("QNA-ID-001", "answer_id must match ^QNA-[A-Z0-9_-]{2,123}$")
        return self.root / answer_id

    @contextmanager
    def lock(self) -> Iterator[None]:
        lock = self.context_root / "runtime" / "locks" / "qna.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        try:
            lock.mkdir()
        except FileExistsError as exc:
            raise TUnderstandError("QNA-LOCK-001", "QnA generation is already active") from exc
        try:
            yield
        finally:
            lock.rmdir()

    def ask(self, answer_id: str, memory_id: str, question: str, limit: int = 8) -> dict[str, Any]:
        if len(question.strip()) < 3:
            raise TUnderstandError("QNA-QUESTION-001", "Question must contain at least three characters")
        if limit < 1 or limit > 50:
            raise TUnderstandError("QNA-LIMIT-001", "limit must be between 1 and 50")
        final = self._dir(answer_id)
        if final.exists():
            raise TUnderstandError("QNA-ID-002", f"Answer bundle already exists and is immutable: {answer_id}")
        mem_validation = self.memory.validate(memory_id)
        if mem_validation["status"] != "PASS":
            raise TUnderstandError("QNA-MEMORY-001", f"Memory validation failed: {memory_id}")
        manifest = self.memory.show(memory_id)
        snap_validation = self.snapshots.validate_snapshot(manifest["snapshot_id"])
        if snap_validation["status"] != "PASS":
            raise TUnderstandError("QNA-SNAPSHOT-001", "Memory snapshot failed integrity validation")
        claims = self.memory._load_artifact(memory_id, "claims") + self.memory._load_artifact(memory_id, "conflicts")
        evidence = self.memory._load_artifact(memory_id, "evidence")
        evidence_by_id = {e["id"]: e for e in evidence}
        query_terms = _terms(question)
        ranked = self._rank(claims, evidence_by_id, query_terms)
        selected = ranked[:limit]
        retrieval = self._retrieval(answer_id, question, memory_id, manifest["snapshot_id"], query_terms, selected)
        verification = self._verify(answer_id, retrieval, claims, evidence_by_id)
        answer = self._synthesize(answer_id, question, manifest["snapshot_id"], selected, verification, claims)

        with self.lock():
            if final.exists():
                raise TUnderstandError("QNA-ID-002", f"Answer bundle already exists and is immutable: {answer_id}")
            temp = self.root / f".{answer_id}.{uuid.uuid4().hex}.tmp"
            temp.mkdir(parents=True, exist_ok=False)
            try:
                atomic_write_yaml(temp / "retrieval-set.yaml", retrieval)
                atomic_write_yaml(temp / "direct-source-verification.yaml", verification)
                atomic_write_yaml(temp / "answer.yaml", answer)
                atomic_write_text(temp / "retrieved-claims.jsonl", _jsonl([c for _, c in selected]))
                atomic_write_text(temp / "citations.jsonl", _jsonl([evidence_by_id[eid] for eid in answer["citations"]]))
                atomic_write_text(temp / "answer.md", self._render(answer, [c for _, c in selected], evidence_by_id))
                critique = self._critique_doc(answer, selected)
                citation = self._citation_doc(answer, evidence_by_id, manifest["snapshot_id"])
                atomic_write_yaml(temp / "answer-critique.yaml", critique)
                atomic_write_yaml(temp / "citation-validation.yaml", citation)
                artifacts: dict[str, dict[str, str]] = {}
                for path in sorted(temp.iterdir()):
                    if path.is_file():
                        artifacts[path.name] = {"path": path.name, "sha256": sha256_file(path)}
                verified_count = sum(1 for x in verification["verified_claims"] if x["status"] == "VERIFIED")
                cited = len(answer["citations"])
                supported_claims = len(answer["claims"])
                base = {
                    "schema_id": "https://t-understand.dev/schemas/qna-manifest.schema.json",
                    "schema_version": "1.0.0",
                    "answer_id": answer_id,
                    "memory_id": memory_id,
                    "snapshot_id": manifest["snapshot_id"],
                    "status": {"answered": "ANSWERED", "partially-answered": "PARTIAL", "unknown": "UNKNOWN"}[answer["answer_status"]],
                    "artifacts": artifacts,
                    "quality": {
                        "retrieval_count": len(selected),
                        "verified_claims": verified_count,
                        "citation_coverage": 1.0 if (not answer.get("claims") or cited > 0) else 0.0,
                        "unsupported_claims": sum(1 for x in verification["verified_claims"] if x["status"] != "VERIFIED"),
                    },
                    "generated_at": utc_now(),
                }
                qmanifest = {**base, "content_digest": _canonical_digest(base)}
                self.contracts.validate("qna-manifest", qmanifest)
                atomic_write_yaml(temp / "qna-manifest.yaml", qmanifest)
                os.replace(temp, final)
                validation = self.validate(answer_id)
                if validation["status"] != "PASS" or self.critique(answer_id)["status"] != "PASS":
                    raise TUnderstandError("QNA-VERIFY-001", "Generated answer failed validation or critique")
            except Exception:
                shutil.rmtree(temp, ignore_errors=True)
                if final.exists():
                    shutil.rmtree(final, ignore_errors=True)
                raise
        return self.show(answer_id)

    def _rank(self, claims: list[dict[str, Any]], evidence: dict[str, dict[str, Any]], query_terms: list[str]) -> list[tuple[float, dict[str, Any]]]:
        ranked: list[tuple[float, dict[str, Any]]] = []
        for claim in claims:
            haystack = [claim.get("statement", ""), claim.get("reasoning", "")]
            for eid in claim.get("evidence", []):
                item = evidence.get(eid)
                if item:
                    haystack += [item.get("path", ""), item.get("excerpt", ""), item.get("repository", "")]
            joined = " ".join(haystack).lower()
            statement = claim.get("statement", "").lower()
            score = sum((3 if term in statement else 1) * joined.count(term) for term in query_terms)
            if not query_terms:
                score = 0
            if score > 0:
                if claim["classification"] == "FACT": score += 0.5
                if claim["classification"] == "CONFLICT": score += 0.25
                ranked.append((float(score), claim))
        return sorted(ranked, key=lambda x: (-x[0], x[1]["id"]))

    def _retrieval(self, answer_id: str, question: str, memory_id: str, snapshot_id: str, terms: list[str], selected: list[tuple[float, dict[str, Any]]]) -> dict[str, Any]:
        status = "NO_MATCH" if not selected else "CONFLICTED" if any(c["classification"] == "CONFLICT" for _, c in selected) else "MATCHED"
        doc = {
            "schema_id": "https://t-understand.dev/schemas/qna-retrieval-set.schema.json", "schema_version": "1.0.0",
            "id": _stable("RET", answer_id), "question": question.strip(), "memory_id": memory_id, "snapshot_id": snapshot_id,
            "status": status, "query_terms": terms,
            "items": [{"claim_id": c["id"], "classification": c["classification"], "score": score, "evidence_ids": c.get("evidence", [])} for score, c in selected],
            "generated_at": utc_now(),
        }
        self.contracts.validate("qna-retrieval-set", doc)
        return doc

    def _verify(self, answer_id: str, retrieval: dict[str, Any], claims: list[dict[str, Any]], evidence: dict[str, dict[str, Any]]) -> dict[str, Any]:
        claim_by_id = {c["id"]: c for c in claims}
        verified = []
        errors = []
        view_cache: dict[str, tuple[Any, dict[str, dict[str, Any]]]] = {}
        for item in retrieval["items"]:
            claim = claim_by_id[item["claim_id"]]
            missing = [eid for eid in claim.get("evidence", []) if eid not in evidence]
            unsupported = not claim.get("evidence") or bool(missing)
            for eid in claim.get("evidence", []):
                if eid not in evidence:
                    continue
                ev = evidence[eid]
                try:
                    self.contracts.validate("evidence-record", ev)
                    repo = ev["repository"]
                    if repo not in view_cache:
                        view = self.discovery.view(retrieval["snapshot_id"], repo)
                        view_cache[repo] = (view, {r["path"]: r for r in view.list_files()})
                    view, records = view_cache[repo]
                    record = records.get(ev["path"])
                    if record is None or record.get("special"):
                        raise TUnderstandError("QNA-SOURCE-001", f"Evidence path is unavailable in snapshot: {repo}:{ev['path']}")
                    actual = "sha256:" + sha256_bytes(view.read(record))
                    if actual != ev["content_sha256"]:
                        raise TUnderstandError("QNA-SOURCE-002", f"Evidence digest differs from snapshot content: {eid}")
                except Exception as exc:
                    unsupported = True
                    errors.append(f"{eid}: {exc}")
            status = "VERIFIED"
            if claim["classification"] == "CONFLICT": status = "CONFLICTED"
            elif claim.get("freshness") == "stale" or claim["classification"] == "STALE": status = "STALE"
            elif unsupported: status = "UNSUPPORTED"
            if missing: errors.append(f"{claim['id']} missing evidence: {', '.join(missing)}")
            verified.append({"claim_id": claim["id"], "status": status, "evidence_ids": claim.get("evidence", [])})
        overall = "PASS" if all(v["status"] == "VERIFIED" for v in verified) else "PARTIAL" if verified else "PASS"
        if errors: overall = "FAIL"
        doc = {
            "schema_id": "https://t-understand.dev/schemas/direct-source-verification.schema.json", "schema_version": "1.0.0",
            "id": _stable("DSV", answer_id), "retrieval_id": retrieval["id"], "snapshot_id": retrieval["snapshot_id"],
            "status": overall, "verified_claims": verified, "errors": errors, "generated_at": utc_now(),
        }
        self.contracts.validate("direct-source-verification", doc)
        return doc

    def _synthesize(self, answer_id: str, question: str, snapshot_id: str, selected: list[tuple[float, dict[str, Any]]], verification: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, Any]:
        claim_by_id = {c["id"]: c for c in claims}
        usable = []
        for v in verification["verified_claims"]:
            if v["status"] in {"VERIFIED", "CONFLICTED"}:
                usable.append(claim_by_id[v["claim_id"]])
        if not usable:
            direct = "The available canonical memory does not contain enough source-grounded evidence to answer this question."
            answer_status = "unknown"
            limitations = ["No matching verified claims were found for the selected immutable snapshot."]
        else:
            facts = [c for c in usable if c["classification"] in {"FACT", "HUMAN_CONFIRMED"}]
            inferences = [c for c in usable if c["classification"] == "INFERENCE"]
            conflicts = [c for c in usable if c["classification"] == "CONFLICT"]
            parts = []
            if facts: parts.append("Verified facts: " + " ".join(c["statement"] for c in facts[:5]))
            if inferences: parts.append("Evidence-backed inferences: " + " ".join(c["statement"] for c in inferences[:3]))
            if conflicts: parts.append("Conflicting evidence exists: " + " ".join(c["statement"] for c in conflicts[:2]))
            direct = "\n\n".join(parts)
            answer_status = "partially-answered" if conflicts or verification["status"] != "PASS" else "answered"
            limitations = []
            if inferences: limitations.append("Inference statements describe evidence-backed relationships, not confirmed product intent.")
            if conflicts: limitations.append("Conflicting claims are preserved and require human resolution.")
        citations = sorted({eid for c in usable for eid in c.get("evidence", [])})
        doc = {
            "schema_id": "https://t-understand.dev/schemas/qna-answer.schema.json", "schema_version": "1.0.0",
            "id": answer_id, "question": question.strip(), "application_snapshot": snapshot_id, "direct_answer": direct,
            "claims": [c["id"] for c in usable], "citations": citations,
            "freshness_status": "mixed" if any(c.get("freshness") != "current" for c in usable) else "current",
            "limitations": limitations, "answer_status": answer_status,
        }
        self.contracts.validate("qna-answer", doc)
        return doc

    def _critique_doc(self, answer: dict[str, Any], selected: list[tuple[float, dict[str, Any]]]) -> dict[str, Any]:
        issues = []
        checks = 4
        if answer["answer_status"] != "unknown" and not answer["claims"]:
            issues.append({"code": "QNA-UNSUPPORTED", "severity": "BLOCKER", "message": "Non-unknown answer has no claims."})
        if answer["claims"] and not answer["citations"]:
            issues.append({"code": "QNA-NO-CITATIONS", "severity": "BLOCKER", "message": "Answer claims have no citations."})
        if any(c["classification"] == "INFERENCE" for _, c in selected) and not any("Inference" in x or "inference" in x for x in answer["limitations"]):
            issues.append({"code": "QNA-INFERENCE-DISCLOSURE", "severity": "MAJOR", "message": "Inference usage is not disclosed."})
        if answer["freshness_status"] == "stale" and not answer["limitations"]:
            issues.append({"code": "QNA-STALE-DISCLOSURE", "severity": "MAJOR", "message": "Stale answer lacks limitation disclosure."})
        doc = {"schema_id": "https://t-understand.dev/schemas/answer-critique.schema.json", "schema_version": "1.0.0", "id": _stable("ACR", answer["id"]), "answer_id": answer["id"], "status": "PASS" if not issues else "FAIL", "checks": checks, "issues": issues, "generated_at": utc_now()}
        self.contracts.validate("answer-critique", doc)
        return doc

    def _citation_doc(self, answer: dict[str, Any], evidence: dict[str, dict[str, Any]], snapshot_id: str) -> dict[str, Any]:
        errors = []
        for eid in answer["citations"]:
            item = evidence.get(eid)
            if not item: errors.append(f"Missing citation: {eid}")
            elif item["application_snapshot"] != snapshot_id: errors.append(f"Citation snapshot mismatch: {eid}")
        doc = {"schema_id": "https://t-understand.dev/schemas/citation-validation.schema.json", "schema_version": "1.0.0", "id": _stable("CIT", answer["id"]), "answer_id": answer["id"], "snapshot_id": snapshot_id, "status": "PASS" if not errors else "FAIL", "checked_citations": len(answer["citations"]), "errors": errors, "generated_at": utc_now()}
        self.contracts.validate("citation-validation", doc)
        return doc

    def _render(self, answer: dict[str, Any], claims: list[dict[str, Any]], evidence: dict[str, dict[str, Any]]) -> str:
        lines = [f"# Answer: {answer['question']}", "", f"**Snapshot:** `{answer['application_snapshot']}`", f"**Status:** `{answer['answer_status']}`", f"**Freshness:** `{answer['freshness_status']}`", "", answer["direct_answer"], ""]
        if claims:
            lines += ["## Supporting claims", ""]
            for claim in claims:
                lines += [f"- **{claim['classification']} · {claim['confidence']}** — {claim['statement']} (`{claim['id']}`)"]
        if answer["citations"]:
            lines += ["", "## Source citations", ""]
            for eid in answer["citations"]:
                e = evidence[eid]
                loc = e.get("locator", {})
                line = loc.get("start_line") or loc.get("line") or "?"
                lines += [f"- `{eid}` — `{e['repository']}@{e['revision'][:12]}:{e['path']}:{line}`"]
        if answer["limitations"]:
            lines += ["", "## Limitations", ""] + [f"- {x}" for x in answer["limitations"]]
        return "\n".join(lines) + "\n"

    def show(self, answer_id: str) -> dict[str, Any]:
        doc = load_yaml(self._dir(answer_id) / "qna-manifest.yaml")
        self.contracts.validate("qna-manifest", doc)
        return doc

    def answer(self, answer_id: str) -> dict[str, Any]:
        doc = load_yaml(self._dir(answer_id) / "answer.yaml")
        self.contracts.validate("qna-answer", doc)
        return doc

    def list(self) -> dict[str, Any]:
        answers = []
        if self.root.exists():
            for p in sorted(self.root.iterdir()):
                if p.is_dir() and (p / "qna-manifest.yaml").exists(): answers.append(self.show(p.name))
        return {"answers": answers}

    def validate(self, answer_id: str) -> dict[str, Any]:
        errors: list[str] = []
        checks = 0
        try:
            manifest = self.show(answer_id); checks += 1
            if _canonical_digest({k: v for k, v in manifest.items() if k != "content_digest"}) != manifest["content_digest"]:
                errors.append("qna manifest content digest mismatch")
            for name, meta in manifest["artifacts"].items():
                path = self._dir(answer_id) / meta["path"]; checks += 1
                if not path.is_file() or sha256_file(path) != meta["sha256"]: errors.append(f"artifact checksum mismatch: {name}")
            answer = self.answer(answer_id); checks += 1
            retrieval = load_yaml(self._dir(answer_id) / "retrieval-set.yaml"); self.contracts.validate("qna-retrieval-set", retrieval); checks += 1
            verification = load_yaml(self._dir(answer_id) / "direct-source-verification.yaml"); self.contracts.validate("direct-source-verification", verification); checks += 1
            critique = load_yaml(self._dir(answer_id) / "answer-critique.yaml"); self.contracts.validate("answer-critique", critique); checks += 1
            citations = load_yaml(self._dir(answer_id) / "citation-validation.yaml"); self.contracts.validate("citation-validation", citations); checks += 1
            if critique["status"] != "PASS": errors.append("answer critique failed")
            if citations["status"] != "PASS": errors.append("citation validation failed")
            if answer["answer_status"] != "unknown" and verification["status"] == "FAIL": errors.append("answer uses failed direct-source verification")
        except Exception as exc:
            errors.append(str(exc))
        report = {"status": "PASS" if not errors else "FAIL", "answer_id": answer_id, "checks": checks, "errors": errors, "generated_at": utc_now()}
        self.reports_root.mkdir(parents=True, exist_ok=True)
        atomic_write_yaml(self.reports_root / f"{answer_id}-verification.yaml", report)
        return report

    def critique(self, answer_id: str) -> dict[str, Any]:
        doc = load_yaml(self._dir(answer_id) / "answer-critique.yaml")
        self.contracts.validate("answer-critique", doc)
        return doc
