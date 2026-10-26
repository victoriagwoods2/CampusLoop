"""Run local deterministic checks and write their actual outcomes to output/."""
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from test_core import CampusLoopChecks

suite = unittest.defaultTestLoader.loadTestsFromTestCase(CampusLoopChecks)
result = unittest.TestResult()
suite.run(result)
cases = []
for test in result.testsRun and list(unittest.defaultTestLoader.loadTestsFromTestCase(CampusLoopChecks)) or []:
    name = test._testMethodName
    failure = next((message for failed, message in result.failures + result.errors if failed == test), None)
    cases.append({"test": name, "status": "failed" if failure else "passed", "failure": failure})

report = {
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "suite": "Python standard-library unittest; deterministic checks only",
    "tests_run": result.testsRun,
    "failures": len(result.failures),
    "errors": len(result.errors),
    "cases": cases,
    "limitations": [
        "No live Portkey request has been made; prompt-injection resistance by the model is unverified.",
        "The frontend was production-built but not exercised in a real browser session.",
        "Donation-source acceptance details remain unverified and are labeled in the app.",
    ],
}
out = ROOT / "output" / "safety_tests.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"tests_run": report["tests_run"], "failures": report["failures"], "errors": report["errors"], "evidence": str(out)}, indent=2))
sys.exit(0 if result.wasSuccessful() else 1)
