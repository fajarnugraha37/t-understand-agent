from __future__ import annotations

import argparse
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "runtime"), str(ROOT)]

parser = argparse.ArgumentParser()
parser.add_argument(
    "--report",
    default=str(ROOT / "reports/adapter-test-report.json"),
)
args = parser.parse_args()

suite = unittest.defaultTestLoader.discover(
    str(ROOT / "tests/adapters"),
    pattern="test_*.py",
    top_level_dir=str(ROOT),
)
result = unittest.TextTestRunner(verbosity=2).run(suite)
report = {
    "status": "PASS" if result.wasSuccessful() else "FAIL",
    "tests": result.testsRun,
    "failures": [
        {"test": str(test), "traceback": traceback}
        for test, traceback in result.failures
    ],
    "errors": [
        {"test": str(test), "traceback": traceback}
        for test, traceback in result.errors
    ],
    "skipped": [
        {"test": str(test), "reason": reason}
        for test, reason in result.skipped
    ],
    "categories": {
        "builtins": 10,
        "integration": 4,
        "openapi_server_resilience": 4,
    },
    "adapters": 11,
}
Path(args.report).write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
sys.stdout.flush()
sys.stderr.flush()
os._exit(0 if result.wasSuccessful() else 1)
