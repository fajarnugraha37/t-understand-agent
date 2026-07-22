import argparse
import json
import unittest
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--report", default="reports/ponytail-test-report.json")
args = parser.parse_args()
suite = unittest.defaultTestLoader.discover("tests/ponytail")
result = unittest.TextTestRunner(verbosity=2).run(suite)
report = {
    "status": "PASS" if result.wasSuccessful() else "FAIL",
    "tests_run": result.testsRun,
    "failures": len(result.failures),
    "errors": len(result.errors),
}
path = Path(args.report)
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
raise SystemExit(0 if result.wasSuccessful() else 1)
