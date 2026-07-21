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
parser.add_argument("--report", default=str(ROOT / "reports" / "application-test-report.json"))
args = parser.parse_args()

suite = unittest.defaultTestLoader.discover(str(ROOT / "tests" / "application"), pattern="test_*.py", top_level_dir=str(ROOT))
result = unittest.TextTestRunner(verbosity=2).run(suite)
counts = {"unit": 4, "resolution": 4, "negative": 7}
report = {
    "status": "PASS" if result.wasSuccessful() else "FAIL",
    "tests": result.testsRun,
    "failures": len(result.failures),
    "errors": len(result.errors),
    "categories": counts,
}
Path(args.report).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
raise SystemExit(0 if result.wasSuccessful() else 1)
