from __future__ import annotations

import argparse
import json
import unittest
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--report", default="reports/installation-test-report.json")
args = parser.parse_args()

suite = unittest.defaultTestLoader.discover("tests/installation")
result = unittest.TextTestRunner(verbosity=2).run(suite)
report = {
    "status": "PASS" if result.wasSuccessful() else "FAIL",
    "tests_run": result.testsRun,
    "failures": [
        {"test": str(test), "detail": detail}
        for test, detail in result.failures
    ],
    "errors": [
        {"test": str(test), "detail": detail}
        for test, detail in result.errors
    ],
}
Path(args.report).parent.mkdir(parents=True, exist_ok=True)
Path(args.report).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
raise SystemExit(0 if result.wasSuccessful() else 1)
