from __future__ import annotations

import argparse
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ROOT))


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.records.append({"test": test.id(), "status": "PASS"})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.records.append({"test": test.id(), "status": "FAIL", "detail": self._exc_info_to_string(err, test)})

    def addError(self, test, err):
        super().addError(test, err)
        self.records.append({"test": test.id(), "status": "ERROR", "detail": self._exc_info_to_string(err, test)})

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.records.append({"test": test.id(), "status": "SKIP", "detail": reason})


class RecordingRunner(unittest.TextTestRunner):
    resultclass = RecordingResult


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="reports/runtime-test-report.json")
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests" / "runtime"), pattern="test_*.py", top_level_dir=str(ROOT))
    result = RecordingRunner(verbosity=2).run(suite)
    records = result.records
    categories = {"unit": 0, "negative": 0, "end_to_end": 0}
    for record in records:
        test = record["test"]
        if ".test_negative." in test:
            categories["negative"] += 1
        elif ".test_e2e." in test:
            categories["end_to_end"] += 1
        else:
            categories["unit"] += 1
    report = {
        "status": "PASS" if result.wasSuccessful() else "FAIL",
        "tests": len(records),
        "categories": categories,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "results": records,
    }
    path = ROOT / args.report
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    import os
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    raise SystemExit(code)
