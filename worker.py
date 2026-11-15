"""Runs only in an evaluation workspace; no model calls or patch application."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time


class Reports:
    def __init__(self):
        self.tests = {}
        self.collection_errors = []

    def pytest_runtest_logreport(self, report):
        key = report.nodeid.split("::", 1)[-1]
        if report.when == "call" or report.failed or report.skipped:
            self.tests[key] = {"outcome": report.outcome, "phase": report.when,
                               "seconds": report.duration}
            if report.failed:
                self.tests[key]["detail"] = str(report.longrepr)[-6000:]

    def pytest_collectreport(self, report):
        if report.failed:
            self.collection_errors.append(str(report.longrepr))


def analyze(root, source):
    profiles = {
        "ruff": ["ruff", "check", "--isolated", "--no-cache", "--select", "F821,F823",
                 "--output-format", "json", source],
        "pylint": ["pylint", "--rcfile=", "--disable=all", "--enable=E0601,E0602",
                   "--persistent=n", "--output-format=json", source],
        "bandit": ["bandit", "-q", "-f", "json", "-t",
                   "B102,B307,B602,B603,B604,B605,B606,B607,B608,B609", source],
    }
    result = {}
    for name, args in profiles.items():
        start = time.perf_counter()
        try:
            proc = subprocess.run([sys.executable, "-m", *args], cwd=root,
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=20)
        except subprocess.TimeoutExpired:
            result[name] = {"status": "infrastructure_error", "version": importlib.metadata.version(name),
                            "command": args, "error": "analyzer timeout", "diagnostics": [],
                            "seconds": time.perf_counter() - start}
            continue
        try:
            raw = json.loads(proc.stdout)
            records = raw.get("results", []) if name == "bandit" else raw
            diagnostics = []
            for rec in records:
                location = rec.get("location", {})
                end = rec.get("end_location", {})
                diagnostics.append({
                    "file": source,
                    "line_start": rec.get("line", rec.get("line_number", location.get("row"))),
                    "line_end": rec.get("endLine", end.get("row", rec.get("line_number", rec.get("line")))),
                    "rule_id": rec.get("code", rec.get("message-id", rec.get("test_id"))),
                    "text": rec.get("message", rec.get("issue_text")),
                    "category": "security" if name == "bandit" else "runtime",
                    "category_status": "rule_mapping_not_expert_confirmation",
                })
            # Findings have nonzero exits. Only analyzer-specific expected exits are valid.
            valid_exit = proc.returncode in (0, 1) if name != "pylint" else proc.returncode in (0, 2)
            status = "ok" if valid_exit else "infrastructure_error"
        except (ValueError, TypeError, AttributeError):
            raw, diagnostics, status = None, [], "infrastructure_error"
        result[name] = {"status": status, "version": importlib.metadata.version(name),
                        "command": args, "exit_code": proc.returncode,
                        "stdout": proc.stdout, "stderr": proc.stderr,
                        "diagnostics": diagnostics, "seconds": time.perf_counter() - start}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case")
    parser.add_argument("--correct", action="store_true")
    parser.add_argument("--timeout", type=float, default=2)
    parser.add_argument("--analyze", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("result.json"))
    args = parser.parse_args()
    # Case IDs are checked by the parent; defense in depth for direct invocation.
    if not args.case.replace("_", "").isalnum():
        parser.error("invalid case ID")
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    import pytest
    root = Path.cwd()
    sys.path.insert(0, str(root))
    reports = Reports()
    command = ["-q", "-p", "pytest_timeout", "-p", "no:cacheprovider",
               "--timeout", str(args.timeout), "--timeout-method=thread",
               f"python_testcases/test_{args.case}.py"]
    # On Windows timeout-method=thread may kill the process. Main pipeline treats missing
    # result.json as infrastructure failure, never as a measured model score.
    if os.name != "nt":
        command[command.index("--timeout-method=thread")] = "--timeout-method=signal"
    if args.correct:
        command.append("--correct")
    start = time.perf_counter()
    code = int(pytest.main(command, plugins=[reports]))
    status = "ok" if code in (0, 1) and not reports.collection_errors and reports.tests else "infrastructure_error"
    result = {"status": status, "exit_code": code, "tests": reports.tests,
              "collection_errors": reports.collection_errors, "seconds": time.perf_counter() - start,
              "python": sys.version, "pytest": pytest.__version__}
    if args.analyze:
        result["analyzers"] = analyze(root, f"python_programs/{args.case}.py")
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
