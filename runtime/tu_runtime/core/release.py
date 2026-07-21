from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from .contracts import ContractValidator
from .errors import TUnderstandError
from .io import atomic_write_text, utc_now, sha256_file

class ReleaseManager:
 def __init__(self,project_root:Path):self.project_root=project_root;self.contracts=ContractValidator(project_root)
 def _read_report(self,name:str)->dict[str,Any]:
  p=self.project_root/"reports"/name
  if not p.exists():return {"status":"MISSING"}
  return json.loads(p.read_text())
 def audit(self)->dict[str,Any]:
  version=(self.project_root/"VERSION").read_text().strip();gates=[]
  def gate(i,status,evidence):gates.append({"id":i,"status":"PASS" if status else "FAIL","evidence":evidence})
  gate("version-1.1.0",version=="1.1.0",[f"VERSION={version}"])
  required=["quality-test-report.json","qualification-test-report.json","installation-test-report.json","integration-test-report.json","documentation-test-report.json","agent-native-test-report.json","agent-native-cli-report.json"]
  for name in required:
   r=self._read_report(name);gate(name.removesuffix('.json'),r.get("status")=="PASS",[f"reports/{name}",f"status={r.get('status')}"])
  pycache=list(self.project_root.rglob("__pycache__"));pyc=list(self.project_root.rglob("*.pyc"));gate("clean-source-tree",not pycache and not pyc,[f"pycache={len(pycache)}",f"pyc={len(pyc)}"])
  schema_count=len(list((self.project_root/"schemas").glob("*.schema.json")))
  skill_count=len(list((self.project_root/"skills").rglob("SKILL.md")))
  adapter_count=len(list((self.project_root/"adapters").glob("*/adapter.yaml")))
  gate("complete-platform-adapters",adapter_count==4,[f"adapters={adapter_count}"])
  canonical_skills=list((self.project_root/"skills").rglob("SKILL.md"))
  aggregate=self.project_root/"adapters"/"codex"/"tu-understand"/"SKILL.md"
  namespace_ok=all(p.parent.name.startswith("tu-") and f"name: {p.parent.name}\n" in p.read_text() for p in canonical_skills)
  namespace_ok=namespace_ok and aggregate.exists() and "name: tu-understand\n" in aggregate.read_text() and not (self.project_root/"adapters"/"codex"/"t-understand").exists()
  gate("skill-tu-namespace",namespace_ok,[f"canonical_skills={skill_count}","aggregate=tu-understand"])
  permission_policy=self.project_root/"orchestrator"/"tool-permission-policy.yaml"
  gate("no-prompt-permission-policy",permission_policy.exists(),[str(permission_policy.relative_to(self.project_root)) if permission_policy.exists() else "missing"])
  capability=self.project_root/"orchestrator"/"capabilities.yaml"
  conversation=self.project_root/"runtime"/"tu_runtime"/"core"/"conversation.py"
  gate("capability-catalog",capability.exists(),["orchestrator/capabilities.yaml"])
  conversation_text=conversation.read_text() if conversation.exists() else ""
  workspace_discovery=self.project_root/"runtime"/"tu_runtime"/"core"/"workspace_discovery.py"
  documentation=self.project_root/"runtime"/"tu_runtime"/"core"/"documentation.py"
  modeling=self.project_root/"runtime"/"tu_runtime"/"core"/"modeling.py"
  gate("artifact-first-documentation",conversation.exists() and "generate_documentation" in conversation_text,["runtime/tu_runtime/core/conversation.py",".t-understand/output/documentation/latest/"])
  gate("agent-native-multi-repository",workspace_discovery.exists() and "resolve_workspace" in workspace_discovery.read_text() and "multi-repo" in conversation_text,["runtime/tu_runtime/core/workspace_discovery.py","application-root=.t-understand"])
  gate("adaptive-documentation-plan",documentation.exists() and "documentation-requirements" in documentation.read_text() and "repository_coverage" in documentation.read_text(),["runtime/tu_runtime/core/documentation.py","base_documents=41","dynamic=repository+flow"])
  gate("deep-business-domain-flow-model",modeling.exists() and "bounded-contexts" in modeling.read_text() and "flow-failures" in modeling.read_text(),["runtime/tu_runtime/core/modeling.py","model_types=31"])
  inventory={"schemas":schema_count,"skill_packages":skill_count,"aggregate_skills":1 if aggregate.exists() else 0,"platform_adapters":adapter_count,"files":sum(1 for p in self.project_root.rglob('*') if p.is_file())}
  report={"schema_id":"https://t-understand.dev/schemas/release-qualification.schema.json","schema_version":"1.0.0","version":version,"status":"PASS" if all(x["status"]=="PASS" for x in gates) else "FAIL","gates":gates,"inventory":inventory,"limitations":["No live commercial or open-weight model was invoked by the provider-neutral qualification harness.","Hosted third-party documentation renderers and remote code-host review APIs were not invoked.","Platform permission profiles were structurally validated but the external OpenCode, Codex, Claude Code, and Cursor executables were not invoked by release qualification."],"generated_at":utc_now()}
  self.contracts.validate("release-qualification",report)
  atomic_write_text(self.project_root/"reports"/"release-qualification.json",json.dumps(report,indent=2)+"\n")
  self._sbom(version)
  return report
 def _sbom(self,version:str)->dict[str,Any]:
  excluded={"CHECKSUMS.sha256","reports/software-bill-of-materials.json","reports/release-qualification.json"};files=[]
  for p in sorted(self.project_root.rglob('*')):
   if p.is_file() and "__pycache__" not in p.parts and p.suffix!=".pyc":
    rel=p.relative_to(self.project_root).as_posix()
    if rel in excluded:continue
    files.append({"path":rel,"sha256":sha256_file(p),"size":p.stat().st_size})
  d={"schema_id":"https://t-understand.dev/schemas/software-bill-of-materials.schema.json","schema_version":"1.0.0","name":"t-understand","version":version,"files":files,"python_dependencies":["PyYAML>=6.0","jsonschema>=4.20"],"generated_at":utc_now()}
  self.contracts.validate("software-bill-of-materials",d);atomic_write_text(self.project_root/"reports"/"software-bill-of-materials.json",json.dumps(d,indent=2)+"\n");return d
 def show(self)->dict[str,Any]:
  p=self.project_root/"reports"/"release-qualification.json"
  if not p.exists():raise TUnderstandError("RELEASE-001","Release qualification has not been generated")
  d=json.loads(p.read_text());self.contracts.validate("release-qualification",d);return d
