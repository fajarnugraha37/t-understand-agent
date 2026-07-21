from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
reports={}
for name in (
    "installation-contract-report.json",
    "installation-test-report.json",
    "final-cli-report.json",
    "release-contract-report.json",
    "release-qualification.json",
):
    path=ROOT/"reports"/name
    reports[name]=json.loads(path.read_text()) if path.exists() else {"status":"MISSING"}
report={
    "status":"PASS" if all(item.get("status")=="PASS" for item in reports.values()) else "FAIL",
    "version":"1.0.2",
    "changes":[
        "conversation-only human entry point",
        "automatic .t-understand workspace state",
        "simple platform installer without ContextRoot",
        "explicit Force replacement for managed and unmanaged installs",
        "packaged deterministic engine inside each platform payload",
    ],
    "reports":reports,
}
(ROOT/"reports/v1.0.2-agent-native-summary.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
raise SystemExit(0 if report["status"]=="PASS" else 1)
