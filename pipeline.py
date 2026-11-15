"""Minimal, auditable CCRQS technical pipeline. See README before model execution."""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import difflib
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data/QuixBugs"
MANIFEST = ROOT / "data/manifest.jsonl"
# Keep transient test trees outside synced checkouts.
WORK = Path(tempfile.gettempdir())
SCHEMA = ROOT / "contracts/review_response_v4.schema.json"


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def read_manifest():
    return [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines()]


def check_dataset():
    inventory = load(ROOT / "data/provenance.json")["files_sha256"]
    for name, expected in inventory.items():
        if sha(DATA / name) != expected:
            raise ValueError(f"dataset changed: {name}; restore or prepare a new snapshot")


def validate_path(name):
    if not isinstance(name, str) or "\\" in name or ":" in name or "\x00" in name:
        raise ValueError("invalid repository path")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or str(path) != name:
        raise ValueError("unsafe or noncanonical repository path")
    if not name.startswith("python_programs/") or path.suffix != ".py":
        raise ValueError("only original Python source files may be changed")
    return path


def apply_diff(original, patch, filename):
    """Strict one-file unified diff; no fuzzy matching, shell invocation or git hooks."""
    validate_path(filename)
    lines = patch.splitlines(keepends=True)
    # Accept only optional canonical git preamble. Renames, binary patches, modes forbidden.
    if lines and lines[0].startswith("diff --git "):
        if lines.pop(0).rstrip("\r\n") != f"diff --git a/{filename} b/{filename}":
            raise ValueError("diff file mismatch")
        if lines and re.fullmatch(r"index [0-9a-f]+\.\.[0-9a-f]+(?: 100644)?\n?", lines[0]):
            lines.pop(0)
    if len(lines) < 3:
        raise ValueError("missing unified diff headers")
    for prefix, marker in (("--- ", "a/"), ("+++ ", "b/")):
        line = lines.pop(0).rstrip("\r\n")
        if not line.startswith(prefix):
            raise ValueError("missing file header")
        path = line[len(prefix):].split("\t", 1)[0]
        if path not in (filename, marker + filename):
            raise ValueError("patch must modify only issue.file")
    source = original.splitlines(keepends=True)
    result, cursor, pos, hunks = [], 0, 0, 0
    while pos < len(lines):
        match = re.fullmatch(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[^\r\n]*\r?\n?", lines[pos])
        if not match:
            raise ValueError("invalid hunk header or extra file")
        old_start, old_len, new_start, new_len = (int(match[1]), int(match[2] or 1),
                                                int(match[3]), int(match[4] or 1))
        start = old_start - 1 if old_len else old_start
        new_offset = new_start - 1 if new_len else new_start
        if start < cursor or start > len(source) or new_offset != len(result) + start - cursor:
            raise ValueError("overlapping hunk or incorrect line offsets")
        result.extend(source[cursor:start])
        cursor = start
        pos += 1
        old_seen = new_seen = 0
        while pos < len(lines) and not lines[pos].startswith("@@ "):
            line = lines[pos]
            pos += 1
            if not line or line[0] not in " +-":
                raise ValueError("invalid hunk body")
            kind, body = line[0], line[1:]
            if pos < len(lines) and lines[pos].rstrip("\r\n") == "\\ No newline at end of file":
                body = body.rstrip("\r\n")
                pos += 1
            if kind in " -":
                if cursor >= len(source) or source[cursor] != body:
                    raise ValueError("patch context does not match original")
                cursor += 1
                old_seen += 1
            if kind in " +":
                result.append(body)
                new_seen += 1
        if (old_seen, new_seen) != (old_len, new_len):
            raise ValueError("hunk counts mismatch")
        hunks += 1
    if not hunks:
        raise ValueError("no patch hunks")
    result.extend(source[cursor:])
    return "".join(result)


def parse_response(raw):
    text = raw.strip()
    wrapped = False
    if text.startswith("```") and text.endswith("```"):
        match = re.fullmatch(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            text, wrapped = match[1], True
    def reject(value):
        raise ValueError(f"nonfinite number: {value}")
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError(f"duplicate JSON key: {key}")
            obj[key] = value
        return obj
    try:
        response = json.loads(text, parse_constant=reject, object_pairs_hook=unique)
        errors = [e.message for e in Draft202012Validator(load(SCHEMA)).iter_errors(response)]
    except (ValueError, TypeError) as exc:
        return {"canonical_format_valid": False, "schema_valid": False,
                "wrapped": wrapped, "errors": [str(exc)], "response": None,
                "manual_extraction_required": True}
    return {"canonical_format_valid": not wrapped and not errors,
            "schema_valid": not errors, "wrapped": wrapped, "errors": errors,
            "response": response, "manual_extraction_required": bool(errors)}


def evaluate_workspace(case, config, directory, correct=False, analyze=False):
    args = [case, "--timeout", str(config["test_timeout_seconds"])]
    if correct:
        args.append("--correct")
    if analyze:
        args.append("--analyze")
    if config["executor"] == "trusted_local":
        command = [sys.executable, "-B", str(ROOT / "worker.py"), *args]
    elif config["executor"] == "docker":
        report_dir = directory.parent / (directory.name + "-reports")
        report_dir.mkdir()
        command = ["docker", "run", "--rm", "--name", "ccrqs-" + uuid.uuid4().hex,
                   "--network=none", "--read-only", "--cap-drop=ALL",
                   "--security-opt=no-new-privileges", "--pids-limit=128",
                   "--memory=1g", "--cpus=1", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
                   "--mount", f"type=bind,source={directory},target=/workspace,readonly",
                   "--mount", f"type=bind,source={report_dir},target=/output",
                   "--workdir=/workspace", config["docker_image"], *args, "--output", "/output/result.json"]
    else:
        raise ValueError("unknown executor")
    start = time.perf_counter()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
               PYTHONIOENCODING="utf-8")
    try:
        proc = subprocess.run(command, cwd=directory, env=env, capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=config["process_timeout_seconds"])
        report_path = directory / "result.json" if config["executor"] == "trusted_local" else report_dir / "result.json"
        report = load(report_path) if report_path.exists() else {
            "status": "infrastructure_error", "tests": {}, "error": "worker produced no result"}
        report.update(process_exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
    except subprocess.TimeoutExpired:
        if config["executor"] == "docker":
            name = command[command.index("--name") + 1]
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=15)
        report = {"status": "infrastructure_error", "tests": {}, "error": "process timeout"}
    finally:
        if config["executor"] == "docker":
            if not report_dir.resolve().is_relative_to(WORK.resolve()):
                raise ValueError("report cleanup escaped work directory")
            shutil.rmtree(report_dir)
    report.update(wall_seconds=time.perf_counter() - start, executor=config["executor"])
    return report


def execute(case, config, source=None, correct=False, analyze=False):
    attempts = []
    # Infrastructure failures: one retry. Never retry a valid failing test/model patch.
    for attempt in range(2):
        with tempfile.TemporaryDirectory(prefix=case + "-", dir=WORK) as temp:
            directory = Path(temp)
            shutil.copytree(DATA, directory, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
            if source is not None:
                (directory / f"python_programs/{case}.py").write_text(source, encoding="utf-8", newline="")
            report = evaluate_workspace(case, config, directory, correct, analyze)
        attempts.append(report)
        if report["status"] == "ok":
            break
    return {**attempts[-1], "attempts": attempts}


def prepare():
    check_dataset()
    config = load(ROOT / "configs/smoke.json")
    cases = sorted(p.stem[5:] for p in (DATA / "python_testcases").glob("test_*.py"))
    def measure(case):
        buggy = execute(case, config)
        reference = execute(case, config, correct=True)
        b, r = buggy["tests"], reference["tests"]
        failed = sorted(k for k, v in b.items() if v["outcome"] == "failed" and v["phase"] == "call")
        passed = sorted(k for k, v in b.items() if v["outcome"] == "passed")
        good = (buggy["status"] == reference["status"] == "ok" and failed and passed
                and all(r.get(k, {}).get("outcome") == "passed" for k in failed + passed))
        dump(ROOT / f"data/acceptance/{case}.json", {"buggy": buggy, "reference": reference})
        row = {"instance_id": case, "dataset": "QuixBugs", "repo_group_id": "jkoppel/QuixBugs",
               "scope": "technical_only", "split": "technical_no_train_test_split",
               "source_file": f"python_programs/{case}.py", "reference_file": f"correct_python_programs/{case}.py",
               "source_sha256": sha(DATA / f"python_programs/{case}.py"),
               "reference_sha256": sha(DATA / f"correct_python_programs/{case}.py"),
               "target_tests": failed, "regression_tests": passed,
               "skipped_tests": sorted(k for k, v in b.items() if v["outcome"] == "skipped"),
               "eligible_q": bool(good), "acceptance_executor": config["executor"],
               "reason": "accepted" if good else "missing_target_or_regression_or_reference_not_reproduced",
               "ground_truth_semantic_label": None}
        print(f"{case}: eligible_q={bool(good)}", flush=True)
        return row
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(measure, cases))
    MANIFEST.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    summary = {"cases": len(rows), "eligible_q": sum(r["eligible_q"] for r in rows),
               "checked_at": timestamp(), "manifest_sha256": sha(MANIFEST),
               "executor": config["executor"], "python": sys.version,
               "notice": "Technical corpus; no human labels and no LLM results."}
    dump(ROOT / "data/acceptance_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False))


def make_prompt(row):
    source = (DATA / row["source_file"]).read_text(encoding="utf-8")
    # Only buggy code; tests, reference code, defect names and acceptance labels are hidden.
    context = f"Python 3; репозиторий QuixBugs; файл {row['source_file']}. Номера строк начинаются с 1."
    code = row["source_file"] + "\n" + source
    template = (ROOT / "prompts/review.txt").read_text(encoding="utf-8")
    return template.replace("{repo_context}", context).replace("{source_code}", code)


def make_fixtures():
    responses = {}
    for row in read_manifest():
        if not row["eligible_q"]:
            continue
        original = (DATA / row["source_file"]).read_text(encoding="utf-8")
        reference = (DATA / row["reference_file"]).read_text(encoding="utf-8")
        patch = "".join(difflib.unified_diff(original.splitlines(True), reference.splitlines(True),
                                           fromfile="a/" + row["source_file"], tofile="b/" + row["source_file"]))
        opcodes = difflib.SequenceMatcher(None, original.splitlines(), reference.splitlines()).get_opcodes()
        changed = [(a + 1, max(a + 1, b)) for tag, a, b, _, _ in opcodes if tag != "equal"]
        response = {"schema_version": "1.0", "issues": [{"file": row["source_file"],
            "line_start": min(x[0] for x in changed), "line_end": max(x[1] for x in changed),
            "category": "functional", "severity": "medium",
            "comment": "Техническая фикстура: эталонный diff из датасета для проверки конвейера.",
            "proposed_patch": patch, "confidence": 1.0}]}
        responses[row["instance_id"]] = json.dumps(response, ensure_ascii=False)
    dump(ROOT / "fixtures/reference_replay.json", {"synthetic": True, "kind": "reference_patch_replay",
         "notice": "Not generated by a model; never include in research comparisons.", "responses": responses})


def http_json(base, route, payload=None, timeout=30):
    parsed = urlparse(base)
    if parsed.scheme != "http" or parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("only a local model endpoint is allowed")
    request = Request(base.rstrip("/") + route,
                      data=None if payload is None else json.dumps(payload).encode("utf-8"),
                      headers={"Content-Type": "application/json"},
                      method="GET" if payload is None else "POST")
    with urlopen(request, timeout=timeout) as reply:
        return json.load(reply)


def llama_generate(prompt, config, out):
    admission = config["admission"]
    required = ("model_id", "hf_repo", "revision", "weights_sha256", "weights_source",
                "backend_revision", "chat_template_sha256", "hardware", "server_command", "memory_measurements")
    if admission.get("status") != "passed" or not admission.get("non_thinking_verified") or any(not admission.get(k) for k in required):
        raise ValueError("model admission is incomplete; fill a checked copy of llama.example.json")
    base = config["base_url"]
    props = http_json(base, "/props")
    dump(out / "server_props.json", props)
    if digest(props["chat_template"]) != admission["chat_template_sha256"]:
        raise ValueError("server chat template differs from admitted template")
    if props["default_generation_settings"]["n_ctx"] < config["max_input_tokens"] + config["max_new_tokens"]:
        raise ValueError("server context too small")
    formatted = http_json(base, "/apply-template", {"messages": [{"role": "user", "content": prompt}]})["prompt"]
    (out / "formatted_prompt.txt").write_text(formatted, encoding="utf-8")
    tokens = http_json(base, "/tokenize", {"content": formatted, "add_special": True})["tokens"]
    if len(tokens) > config["max_input_tokens"]:
        raise ValueError("input exceeds shared limit; per-model truncation is forbidden")
    request = {"prompt": formatted, "n_predict": config["max_new_tokens"],
               "temperature": 0, "seed": config["seed"], "repeat_penalty": 1,
               "presence_penalty": 0, "frequency_penalty": 0, "stream": False,
               "cache_prompt": False}
    dump(out / "generation_request.json", request)
    start = time.perf_counter()
    reply = http_json(base, "/completion", request, config["inference_timeout_seconds"])
    dump(out / "generation_response.json", reply)
    return reply["content"], {"seconds": time.perf_counter() - start,
                               "input_tokens": len(tokens), "usage": reply.get("timings"),
                               "truncated": reply.get("truncated"), "stop_type": reply.get("stop_type")}


def generate_with_retry(prompt, config, out):
    attempts = []
    for number in range(2):
        attempt_out = out / f"inference_attempt_{number}"
        attempt_out.mkdir()
        start = time.perf_counter()
        try:
            raw, metadata = llama_generate(prompt, config, attempt_out)
            attempts.append({"number": number, "status": "received", "seconds": time.perf_counter() - start})
            dump(out / "inference_attempts.json", attempts)
            return raw, {**metadata, "attempts": attempts}
        except (URLError, TimeoutError) as exc:
            attempts.append({"number": number, "status": "infrastructure_error",
                             "error": str(exc), "seconds": time.perf_counter() - start})
            dump(out / "inference_attempts.json", attempts)
            # Client errors indicate configuration/request problems; no generation retry.
            if number == 1 or isinstance(exc, HTTPError) and exc.code < 500:
                raise


def patch_metrics(row, issue, config, out):
    result = {"A": 0, "T": 0, "R": 0, "S": None, "Q": None,
              "status": "patch_not_provided", "semantic_status": "not_applicable"}
    patch = issue["proposed_patch"]
    if patch is None:
        result["Q"] = 0
        return result
    original = (DATA / row["source_file"]).read_text(encoding="utf-8")
    try:
        if issue["file"] != row["source_file"]:
            raise ValueError("issue file not in this case's allowed source")
        validate_path(issue["file"])
        if not 1 <= issue["line_start"] <= issue["line_end"] <= len(original.splitlines()):
            raise ValueError("issue lines outside original source")
        modified = apply_diff(original, patch, issue["file"])
        ast.parse(modified, filename=issue["file"])
    except (ValueError, SyntaxError) as exc:
        result.update(status="patch_invalid", error=str(exc), Q=0)
        return result
    result["A"] = 1
    (out / "patch.diff").write_text(patch, encoding="utf-8")
    report = execute(row["instance_id"], config, source=modified, analyze=True)
    dump(out / "execution.json", report)
    if report["status"] != "ok":
        result.update(T=None, R=None, Q=None, status="infrastructure_error")
        return result
    outcomes = report["tests"]
    expected = row["target_tests"] + row["regression_tests"]
    if any(outcomes.get(k, {}).get("phase") != "call" or outcomes[k]["outcome"] not in ("passed", "failed") for k in expected):
        result.update(T=None, R=None, Q=None, status="infrastructure_error", error="test missing, skipped or setup failed")
        return result
    result["T"] = int(all(outcomes[k]["outcome"] == "passed" for k in row["target_tests"]))
    result["R"] = sum(outcomes[k]["outcome"] == "passed" for k in row["regression_tests"]) / len(row["regression_tests"])
    result.update(status="measured", semantic_status="pending_experts" if result["T"] else "not_applicable")
    if not result["T"]:
        result["Q"] = 0
    return result


def semantic_errors(row, issue):
    errors = []
    try:
        validate_path(issue["file"])
        if issue["file"] != row["source_file"]:
            raise ValueError("issue file outside provided case")
        length = len((DATA / issue["file"]).read_text(encoding="utf-8").splitlines())
        if not 1 <= issue["line_start"] <= issue["line_end"] <= length:
            raise ValueError("issue lines outside original source")
    except ValueError as exc:
        errors.append(str(exc))
    return errors


def run(config_path):
    config = load(config_path)
    check_dataset()
    if config["backend"] == "llama_cpp" and config["executor"] != "docker":
        raise ValueError("model patches require Docker isolation")
    if config["backend"] not in ("replay", "llama_cpp"):
        raise ValueError("unsupported backend")
    synthetic = config["backend"] == "replay"
    fixture = load(ROOT / config["fixture"]) if synthetic else None
    if synthetic and fixture.get("synthetic") is not True:
        raise ValueError("replay must explicitly mark synthetic=True")
    rows = {r["instance_id"]: r for r in read_manifest()}
    if len(set(config["case_ids"])) != len(config["case_ids"]):
        raise ValueError("duplicate case IDs")
    if not config["case_ids"]:
        raise ValueError("empty case selection")
    for case in config["case_ids"]:
        if case not in rows or not rows[case]["eligible_q"]:
            raise ValueError(f"case not eligible for Q: {case}")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    out = ROOT / "runs" / run_id
    out.mkdir(parents=True)
    dump(out / "config.json", config)
    environment = {"python": sys.version, "platform": platform.platform(), "started_at": timestamp(),
        "backend": config["backend"], "synthetic": synthetic,
        "manifest_sha256": sha(MANIFEST), "schema_sha256": sha(SCHEMA),
        "prompt_sha256": sha(ROOT / "prompts/review.txt"),
        "fixture_sha256": sha(ROOT / config["fixture"]) if synthetic else None,
        "requirements_lock_sha256": sha(ROOT / "requirements.lock.txt"),
        "source_sha256": {p.name: sha(p) for p in (ROOT / "pipeline.py", ROOT / "worker.py")},
        "packages": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}}
    if config["executor"] == "docker":
        inspect = subprocess.run(["docker", "image", "inspect", config["docker_image"]],
                                 capture_output=True, text=True, timeout=15, check=True)
        environment["docker_image_inspect"] = json.loads(inspect.stdout)
    dump(out / "environment.json", environment)
    db = sqlite3.connect(out / "results.sqlite")
    db.execute("CREATE TABLE reviews(review_id TEXT PRIMARY KEY, instance_id TEXT, synthetic INTEGER, status TEXT, result_json TEXT)")
    results = []
    start = time.perf_counter()
    for case in config["case_ids"]:
        row = rows[case]
        case_out = out / case
        case_out.mkdir()
        prompt = make_prompt(row)
        (case_out / "prompt.txt").write_text(prompt, encoding="utf-8")
        review_id = run_id + ":" + case
        result = {"review_id": review_id, "instance_id": case, "synthetic": synthetic,
                  "D": None, "C": None, "Q": None, "CCRQS": None,
                  "expert_status": "pending_M_C_S_H", "issues": []}
        try:
            if synthetic:
                raw = fixture["responses"][case]
                generation = {"seconds": 0, "kind": "offline_replay_not_inference", "input_tokens": None}
            else:
                raw, generation = generate_with_retry(prompt, config, case_out)
            (case_out / "raw_response.txt").write_text(raw, encoding="utf-8")
            dump(case_out / "generation.json", generation)
            parsed = parse_response(raw)
            dump(case_out / "validation.json", parsed)
            result["canonical_format_valid"] = parsed["canonical_format_valid"]
            result["schema_valid"] = parsed["schema_valid"]
            if generation.get("truncated"):
                raise ValueError("server truncated context despite preflight limit")
            if not parsed["schema_valid"]:
                result["status"] = "manual_extraction_required"
            else:
                response = parsed["response"]
                dump(case_out / "structured_response.json", response)
                baseline = execute(case, config, analyze=True)
                dump(case_out / "buggy_execution.json", baseline)
                # Recheck frozen acceptance in the actual executor, including model Docker.
                reference = execute(case, config, correct=True)
                dump(case_out / "reference_execution.json", reference)
                acceptance_ok = baseline["status"] == reference["status"] == "ok"
                acceptance_ok = acceptance_ok and all(
                    baseline["tests"].get(k, {}).get("outcome") == "failed" and
                    baseline["tests"][k].get("phase") == "call" and
                    reference["tests"].get(k, {}).get("outcome") == "passed" for k in row["target_tests"])
                acceptance_ok = acceptance_ok and all(
                    baseline["tests"].get(k, {}).get("outcome") == reference["tests"].get(k, {}).get("outcome") == "passed"
                    for k in row["regression_tests"])
                if not acceptance_ok:
                    result["status"] = "infrastructure_error"
                else:
                    result["status"] = "awaiting_experts"
                    for index, issue in enumerate(response["issues"]):
                        issue_out = case_out / f"issue_{index}"
                        issue_out.mkdir()
                        metrics = patch_metrics(row, issue, config, issue_out)
                        metrics["semantic_contract_errors"] = semantic_errors(row, issue)
                        result["issues"].append({"issue_id": review_id + f":{index}", **metrics})
                    if not response["issues"]:
                        result.update(D=0, C=0, Q=0, CCRQS=0, status="measured_empty_review")
                    if any(i["status"] == "infrastructure_error" for i in result["issues"]):
                        result["status"] = "infrastructure_error"
        except Exception as exc:
            result.update(status="infrastructure_error", error=f"{type(exc).__name__}: {exc}")
        dump(case_out / "result.json", result)
        db.execute("INSERT INTO reviews VALUES(?,?,?,?,?)", (review_id, case, int(synthetic), result["status"], json.dumps(result, ensure_ascii=False)))
        db.commit()
        results.append(result)
        print(f"{case}: {result['status']}", flush=True)
    db.close()
    observed = [r for r in results if "canonical_format_valid" in r]
    summary = {"run_id": run_id, "synthetic": synthetic, "backend": config["backend"],
               "cases": len(results), "wall_seconds": time.perf_counter() - start,
               "responses_observed": len(observed),
               "canonical_format_valid_rate": sum(r["canonical_format_valid"] for r in observed) / len(observed) if observed else None,
               "schema_valid_rate": sum(r["schema_valid"] for r in observed) / len(observed) if observed else None,
               "status_counts": {s: sum(r["status"] == s for r in results) for s in sorted({r["status"] for r in results})},
               "CCRQS": None, "notice": "Human matching and ratings required; reference replay is not model performance."}
    dump(out / "summary.json", summary)
    print(str(out))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare", help="verify buggy/reference tests and write manifest")
    sub.add_parser("fixtures", help="create labelled reference-diff replay fixtures")
    command = sub.add_parser("run")
    command.add_argument("--config", type=Path, default=ROOT / "configs/smoke.json")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "fixtures":
        make_fixtures()
    else:
        run(args.config)


if __name__ == "__main__":
    main()
