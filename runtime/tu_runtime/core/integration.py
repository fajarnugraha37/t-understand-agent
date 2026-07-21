from __future__ import annotations
from pathlib import Path
from typing import Any
from .contracts import ContractValidator
from .errors import TUnderstandError
import json

SCENARIOS=[
 {"id":"single-repo-complete-pipeline","scope":"snapshot through QnA, documentation, export, and static review"},
 {"id":"monorepo-module-coverage","scope":"module discovery, adapter extraction, analysis, and coverage"},
 {"id":"multi-repo-contract-graph","scope":"event and HTTP links with ambiguity suppression"},
 {"id":"diff-review-matrix","scope":"branch/commit/HEAD/index/worktree comparative review"},
 {"id":"freshness-invalidation-refresh","scope":"change detection through memory/document invalidation and refresh"},
 {"id":"platform-package-install-uninstall","scope":"four platform packages, safe install, doctor, and uninstall"},
 {"id":"cheap-model-contract-qualification","scope":"economy/balanced/deep profile contract simulation"},
]
class IntegrationManager:
 def __init__(self,project_root:Path): self.project_root=project_root;self.contracts=ContractValidator(project_root)
 def matrix(self)->dict[str,Any]:return {"scenarios":SCENARIOS,"required_status":"PASS","source_repository_write":"denied"}
 def report(self)->dict[str,Any]:
  p=self.project_root/"reports"/"integration-test-report.json"
  if not p.exists():raise TUnderstandError("INTEGRATION-REPORT-001","Integration report has not been generated")
  d=json.loads(p.read_text());self.contracts.validate("integration-report",d);return d
