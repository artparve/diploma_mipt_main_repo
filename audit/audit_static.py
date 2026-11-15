"""Read-only source inspection for stage 5; writes derived JSON evidence only."""

from __future__ import annotations

import collections
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import openpyxl


ROOT = Path(__file__).resolve().parent
SHA = re.compile(r"^[0-9a-f]{40}$", re.I)
DIFF = re.compile(r"^diff --git a/(.+?) b/(.+?)$", re.M)


def repo_key(url: str | None) -> str | None:
    if not url:
        return None
    path = urlparse(str(url).strip()).path.strip("/")
    parts = path.removesuffix(".git").split("/")
    if len(parts) < 2:
        return None
    return "/".join(parts[:2]).lower()


def from_commit_url(url: str | None) -> str | None:
    return repo_key(url)


def patch_paths(patch: str | None) -> list[str]:
    return sorted({b for _, b in DIFF.findall(patch or "")})


def info_map(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def read_bugssinpy() -> tuple[list[dict], dict]:
    root = ROOT / "BugsInPy"
    rows: list[dict] = []
    for project_dir in sorted((root / "projects").iterdir()):
        if not project_dir.is_dir():
            continue
        project = info_map(project_dir / "project.info")
        for info_path in sorted((project_dir / "bugs").glob("*/bug.info")):
            bug_dir = info_path.parent
            info = info_map(info_path)
            patch = (bug_dir / "bug_patch.txt").read_text(encoding="utf-8", errors="replace")
            paths = patch_paths(patch)
            py_paths = [p for p in paths if p.endswith(".py")]
            command = (bug_dir / "run_test.sh").read_text(encoding="utf-8", errors="replace").strip()
            buggy_sha = info.get("buggy_commit_id", "")
            fixed_sha = info.get("fixed_commit_id", "")
            rows.append({
                "source": "BugsInPy",
                "record_id": f"{project_dir.name}/{bug_dir.name}",
                "repo_key": repo_key(project.get("github_url")),
                "repo_url": project.get("github_url"),
                "buggy_commit": buggy_sha,
                "fixed_commit": fixed_sha,
                "changed_files": paths,
                "python_file_count": len(py_paths),
                "test_command_present": bool(command),
                "python_version": info.get("python_version"),
                "patch_sha256": hashlib.sha256(patch.encode()).hexdigest(),
                "static_flags": [
                    *([] if SHA.fullmatch(buggy_sha) else ["abbreviated_or_invalid_buggy_sha"]),
                    *([] if SHA.fullmatch(fixed_sha) else ["abbreviated_or_invalid_fixed_sha"]),
                    *([] if len(py_paths) == 1 else ["not_one_python_file"]),
                    *([] if command else ["missing_target_command"]),
                ],
                "reproduction_status": "not_run",
                "license_status": "project_license_not_checked",
            })
    counts = collections.Counter(len(r["changed_files"]) for r in rows)
    summary = {
        "raw_records": len(rows),
        "unique_repo_keys": len({r["repo_key"] for r in rows if r["repo_key"]}),
        "complete_sha_pairs": sum(SHA.fullmatch(r["buggy_commit"] or "") is not None and SHA.fullmatch(r["fixed_commit"] or "") is not None for r in rows),
        "nonempty_buggy_and_fixed_ids": sum(bool(r["buggy_commit"] and r["fixed_commit"]) for r in rows),
        "one_changed_python_file": sum(r["python_file_count"] == 1 for r in rows),
        "one_changed_file_total": counts[1],
        "test_command_present": sum(r["test_command_present"] for r in rows),
        "static_flags": dict(collections.Counter(f for r in rows for f in r["static_flags"])),
        "by_project": dict(sorted(collections.Counter(r["record_id"].split("/")[0] for r in rows).items())),
    }
    return rows, summary


def read_pyresbugs() -> tuple[list[dict], dict]:
    wb = openpyxl.load_workbook(ROOT / "PyResBugs" / "PyresBugs.xlsx", read_only=True, data_only=True)
    sheet = wb.active
    iterator = sheet.values
    headers = next(iterator)
    rows: list[dict] = []
    type_counts: collections.Counter[str] = collections.Counter()
    input_counts: collections.Counter[str] = collections.Counter()
    for index, values in enumerate(iterator, start=2):
        item = dict(zip(headers, values))
        commit = str(item.get("Commit_sha") or "").strip()
        url_key = repo_key(item.get("Url"))
        commit_key = from_commit_url(item.get("Commit_URL"))
        paths = patch_paths(item.get("Diff_patch"))
        py_paths = [p for p in paths if p.endswith(".py")]
        bug_type = str(item.get("Bug_Type") or "").strip()
        dataset_input = str(item.get("Dataset_input") or "").strip()
        type_counts[bug_type or "<blank>"] += 1
        input_counts[dataset_input or "<blank>"] += 1
        flags: list[str] = []
        if not SHA.fullmatch(commit):
            flags.append("missing_or_invalid_fixed_sha")
        if not url_key:
            flags.append("missing_source_repo")
        if not commit_key:
            flags.append("missing_commit_repo")
        if url_key and commit_key and url_key != commit_key:
            flags.append("repo_url_mismatch")
        if len(py_paths) != 1:
            flags.append("not_one_python_file")
        if not item.get("Faulty Code") or not item.get("Fault Free Code"):
            flags.append("missing_code_pair")
        if not item.get("Test_File_Path"):
            flags.append("missing_test_path")
        rows.append({
            "source": "PyResBugs",
            "record_id": f"row_{index}",
            "repo_key": url_key,
            "commit_url_repo_key": commit_key,
            "fixed_commit": commit,
            "changed_files": paths,
            "python_file_count": len(py_paths),
            "bug_type": bug_type,
            "dataset_input": dataset_input,
            "test_file_path": str(item.get("Test_File_Path") or ""),
            "static_flags": flags,
            "reproduction_status": "not_run",
            "license_status": "source_project_license_not_checked",
        })
    wb.close()
    fixed_keys = [(r["repo_key"], r["fixed_commit"]) for r in rows if r["repo_key"] and SHA.fullmatch(r["fixed_commit"])]
    counts = collections.Counter(fixed_keys)
    summary = {
        "raw_records": len(rows),
        "unique_repo_keys_from_url": len({r["repo_key"] for r in rows if r["repo_key"]}),
        "complete_fixed_sha": sum(SHA.fullmatch(r["fixed_commit"]) is not None for r in rows),
        "one_changed_python_file": sum(r["python_file_count"] == 1 for r in rows),
        "code_pair_present": sum("missing_code_pair" not in r["static_flags"] for r in rows),
        "test_path_present": sum("missing_test_path" not in r["static_flags"] for r in rows),
        "repeated_repo_fixed_commit_key_rows": sum(n - 1 for n in counts.values() if n > 1),
        "static_flags": dict(collections.Counter(f for r in rows for f in r["static_flags"])),
        "bug_type_counts": dict(type_counts.most_common()),
        "dataset_input_counts": dict(input_counts.most_common()),
        "mismatch_examples": [r["record_id"] for r in rows if "repo_url_mismatch" in r["static_flags"]][:10],
    }
    return rows, summary


def import_function(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(f"audit_{path.parent.name}_{name}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return getattr(module, name)


def quix_smoke(root: Path) -> dict:
    buggy = import_function(root / "python_programs" / "quicksort.py", "quicksort")
    fixed = import_function(root / "correct_python_programs" / "quicksort.py", "quicksort")
    cases = [json.loads(line) for line in (root / "json_testcases" / "quicksort.json").read_text(encoding="utf-8").splitlines() if line.strip()]
    outcomes = []
    for _ in range(3):
        run = []
        for inputs, expected in cases:
            run.append({"buggy_pass": buggy(*inputs) == expected, "fixed_pass": fixed(*inputs) == expected})
        outcomes.append(run)
    return {
        "case": "quicksort",
        "json_testcases": len(cases),
        "buggy_fail_fixed_pass_per_run": [sum(not x["buggy_pass"] and x["fixed_pass"] for x in run) for run in outcomes],
        "buggy_pass_fixed_pass_per_run": [sum(x["buggy_pass"] and x["fixed_pass"] for x in run) for run in outcomes],
        "fixed_fail_per_run": [sum(not x["fixed_pass"] for x in run) for run in outcomes],
        "runs": 3,
        "method": "direct stdlib invocation of bundled JSON inputs; not original pytest harness",
    }


def read_quixbugs() -> tuple[list[dict], dict]:
    root = ROOT / "QuixBugs"
    buggy = {p.stem: p for p in (root / "python_programs").glob("*.py") if p.stem != "__init__"}
    fixed = {p.stem: p for p in (root / "correct_python_programs").glob("*.py") if p.stem != "__init__"}
    tests = {p.stem.removeprefix("test_"): p for p in (root / "python_testcases").glob("test_*.py")}
    json_tests = {p.stem: p for p in (root / "json_testcases").glob("*.json")}
    rows = []
    for name in sorted(tests):
        rows.append({
            "source": "QuixBugs",
            "record_id": name,
            "repo_key": "jkoppel/quixbugs",
            "buggy_path": str(buggy[name].relative_to(root)).replace("\\", "/") if name in buggy else None,
            "fixed_path": str(fixed[name].relative_to(root)).replace("\\", "/") if name in fixed else None,
            "test_path": str(tests[name].relative_to(root)).replace("\\", "/") if name in tests else None,
            "json_test_path": str(json_tests[name].relative_to(root)).replace("\\", "/") if name in json_tests else None,
            "static_flags": [*([] if name in buggy else ["missing_buggy_program"]), *([] if name in fixed else ["missing_fixed_program"]), *([] if name in json_tests else ["missing_json_testcases"])],
            "reproduction_status": "smoke_only" if name == "quicksort" else "not_run",
            "license_status": "repo_mit_upstream_caveat",
        })
    return rows, {
        "raw_python_files_including_helpers": len(buggy),
        "fixed_python_files_including_helpers": len(fixed),
        "canonical_test_programs": len(tests),
        "matched_buggy": sum(r["buggy_path"] is not None for r in rows),
        "matched_fixed": sum(r["fixed_path"] is not None for r in rows),
        "matched_pytests": sum(r["test_path"] is not None for r in rows),
        "matched_json_testcases": sum(r["json_test_path"] is not None for r in rows),
        "smoke": quix_smoke(root),
    }


def main() -> None:
    bugs, bugs_summary = read_bugssinpy()
    pyres, pyres_summary = read_pyresbugs()
    quix, quix_summary = read_quixbugs()
    bugs_sha = {r["fixed_commit"]: r for r in bugs if SHA.fullmatch(r["fixed_commit"] or "")}
    matches = [{"bugs_in_py": bugs_sha[r["fixed_commit"]]["record_id"], "pyresbugs": r["record_id"], "same_repo_key": bugs_sha[r["fixed_commit"]]["repo_key"] == r["repo_key"]} for r in pyres if r["fixed_commit"] in bugs_sha]
    summary = {
        "source_snapshots": {"BugsInPy": "11c5f1eea954a42132cfd06bf257766a7963e0fd", "PyResBugs": "27d2a38682d861339275e37c17b52826292dd458", "QuixBugs": "4257f44b0ff1181dedaedee6a447e133219fcebf"},
        "BugsInPy": bugs_summary,
        "PyResBugs": pyres_summary,
        "QuixBugs": quix_summary,
        "cross_source_fixed_sha_matches": matches,
        "cross_source_fixed_sha_match_counts": {
            "pyres_rows": len(matches),
            "unique_bugsinpy_cases": len({m["bugs_in_py"] for m in matches}),
            "same_repo_key": sum(m["same_repo_key"] for m in matches),
        },
    }
    (ROOT / "dataset_static_audit_v6.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    with (ROOT / "dataset_candidates_v6.jsonl").open("w", encoding="utf-8") as out:
        for row in bugs + pyres + quix:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "cross_source_fixed_sha_matches"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
