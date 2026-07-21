from __future__ import annotations

import argparse
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ROOT))

parser = argparse.ArgumentParser()
parser.add_argument("--report", default=str(ROOT / "reports" / "snapshot-test-report.json"))
args = parser.parse_args()

loader = unittest.defaultTestLoader
module_counts = {}
suite = unittest.TestSuite()
for module_name, expected in (
    ("tests.snapshot.test_unit", 5),
    ("tests.snapshot.test_capture", 8),
    ("tests.snapshot.test_negative", 11),
    ("tests.snapshot.test_review_target", 5),
):
    module_suite = loader.loadTestsFromName(module_name)
    module_counts[module_name.rsplit(".", 1)[-1].replace("test_", "")] = module_suite.countTestCases()
    if module_suite.countTestCases() != expected:
        raise SystemExit(f"unexpected test count for {module_name}: {module_suite.countTestCases()} != {expected}")
    suite.addTests(module_suite)
result = unittest.TextTestRunner(verbosity=2).run(suite)
report = {
    "status": "PASS" if result.wasSuccessful() else "FAIL",
    "tests": result.testsRun,
    "failures": len(result.failures),
    "errors": len(result.errors),
    "categories": module_counts,
}
Path(args.report).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
raise SystemExit(0 if result.wasSuccessful() else 1)
