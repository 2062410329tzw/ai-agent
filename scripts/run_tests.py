"""Run offline unit tests and write actual results for review."""
import json
import platform
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
target = root / "examples/test-results.txt"
suite = unittest.defaultTestLoader.discover(str(root / "tests"))
with target.open("w", encoding="utf-8") as stream:
    stream.write("Python " + platform.python_version() + "\n")
    stream.write("UTC " + datetime.now(timezone.utc).isoformat() + "\n")
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
summary = {"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
           "successful": result.wasSuccessful(), "python": platform.python_version()}
(root / "examples/test-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary))
if not result.wasSuccessful():
    print(target.read_text(encoding="utf-8"))
raise SystemExit(0 if result.wasSuccessful() else 1)
