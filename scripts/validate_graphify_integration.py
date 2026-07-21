import argparse
import json
from pathlib import Path

from graphify_integration_lib import audit

parser = argparse.ArgumentParser()
parser.add_argument("--report", default="reports/graphify-integration-report.json")
args = parser.parse_args()
report = audit()
path = Path(args.report)
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["status"] == "PASS" else 1)
