import json
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline as p


def issue(**updates):
    value = {"file": "python_programs/gcd.py", "line_start": 1, "line_end": 1,
             "category": "functional", "severity": "medium", "comment": "",
             "confidence": 0.5, "proposed_patch": None}
    value.update(updates)
    return value


@pytest.mark.parametrize("name", ["../x.py", "/x.py", "C:/x.py", "python_programs/../x.py",
                                  "python_programs\\gcd.py", "python_testcases/test_gcd.py",
                                  "python_programs//gcd.py"])
def test_unsafe_paths(name):
    with pytest.raises(ValueError):
        p.validate_path(name)


def test_exact_diff_and_multiple_hunks():
    diff = "--- a/python_programs/gcd.py\n+++ b/python_programs/gcd.py\n@@ -1,2 +1,2 @@\n-a\n+A\n b\n@@ -4 +4 @@\n-d\n+D\n"
    assert p.apply_diff("a\nb\nc\nd\n", diff, "python_programs/gcd.py") == "A\nb\nc\nD\n"
    with pytest.raises(ValueError):
        p.apply_diff("wrong\nb\nc\nd\n", diff, "python_programs/gcd.py")
    with pytest.raises(ValueError):
        p.apply_diff("a\nb\nc\nd\n", diff.replace("@@ -4 +4", "@@ -4 +5"), "python_programs/gcd.py")


def test_reject_second_file_and_reference_to_tests():
    head = "--- a/python_programs/gcd.py\n+++ b/python_programs/gcd.py\n@@ -1 +1 @@\n-a\n+b\n"
    with pytest.raises(ValueError):
        p.apply_diff("a\n", head + head, "python_programs/gcd.py")
    with pytest.raises(ValueError):
        p.apply_diff("a\n", head.replace("b/python_programs/gcd.py", "b/python_testcases/test_gcd.py"), "python_programs/gcd.py")


def test_no_final_newline():
    diff = "--- a/python_programs/gcd.py\n+++ b/python_programs/gcd.py\n@@ -1 +1 @@\n-a\n\\ No newline at end of file\n+b\n\\ No newline at end of file\n"
    assert p.apply_diff("a", diff, "python_programs/gcd.py") == "b"


@pytest.mark.parametrize("raw", ['{}', '{"schema_version":"1.0","issues":[],"extra":1}',
    '{"schema_version":"1.0","schema_version":"1.0","issues":[]}',
    '{"schema_version":"1.0","issues":[],"bad":NaN}', 'text {"schema_version":"1.0","issues":[]}'])
def test_invalid_json_is_retained_for_manual_extraction(raw):
    parsed = p.parse_response(raw)
    assert not parsed["schema_valid"]
    assert parsed["manual_extraction_required"]


def test_fence_is_recorded_not_silently_repaired():
    raw = '{"schema_version":"1.0","issues":[]}'
    assert p.parse_response(raw)["canonical_format_valid"]
    parsed = p.parse_response("```json\n" + raw + "\n```")
    assert parsed["schema_valid"] and not parsed["canonical_format_valid"] and parsed["wrapped"]


def test_no_patch_and_invalid_syntax_do_not_execute(tmp_path):
    row = next(r for r in p.read_manifest() if r["instance_id"] == "gcd")
    config = p.load(p.ROOT / "configs/smoke.json")
    with patch.object(p, "execute", side_effect=AssertionError("must not execute")):
        assert p.patch_metrics(row, issue(), config, tmp_path)["Q"] == 0
        assert p.semantic_errors(row, issue(line_end=9999))
        bad = "--- a/python_programs/gcd.py\n+++ b/python_programs/gcd.py\n@@ -1 +1 @@\n-def gcd(a, b):\n+this is invalid !!!\n"
        measured = p.patch_metrics(row, issue(proposed_patch=bad), config, tmp_path)
        assert measured["A"] == 0 and measured["Q"] == 0


def test_missing_regression_result_is_infrastructure_failure(tmp_path):
    row = next(r for r in p.read_manifest() if r["instance_id"] == "gcd")
    fixture = p.load(p.ROOT / "fixtures/reference_replay.json")
    record = json.loads(fixture["responses"]["gcd"])["issues"][0]
    with patch.object(p, "execute", return_value={"status": "ok", "tests": {}}):
        result = p.patch_metrics(row, record, p.load(p.ROOT / "configs/smoke.json"), tmp_path)
    assert result["A"] == 1 and result["T"] is None and result["Q"] is None
    assert result["status"] == "infrastructure_error"


def test_all_reference_fixtures_apply_to_their_originals():
    fixture = p.load(p.ROOT / "fixtures/reference_replay.json")
    for row in p.read_manifest():
        if row["eligible_q"]:
            issue = json.loads(fixture["responses"][row["instance_id"]])["issues"][0]
            original = (p.DATA / row["source_file"]).read_text(encoding="utf-8")
            expected = (p.DATA / row["reference_file"]).read_text(encoding="utf-8")
            assert p.apply_diff(original, issue["proposed_patch"], row["source_file"]) == expected


def test_prompt_has_no_reference_or_tests():
    row = next(r for r in p.read_manifest() if r["instance_id"] == "gcd")
    prompt = p.make_prompt(row)
    assert "python_programs/gcd.py" in prompt
    assert "correct_python_programs" not in prompt and "test_gcd" not in prompt
    assert "{repo_context}" not in prompt and "{source_code}" not in prompt


def admitted_config():
    config = p.load(p.ROOT / "configs/llama.example.json")
    admission = config["admission"]
    for key in admission:
        if admission[key] is None:
            admission[key] = "synthetic-test-value"
    admission.update(status="passed", non_thinking_verified=True, chat_template_sha256=p.digest("template"))
    return config


def test_llama_admission_guard(tmp_path):
    with pytest.raises(ValueError, match="admission"):
        p.llama_generate("prompt", p.load(p.ROOT / "configs/llama.example.json"), tmp_path)


def test_transport_failure_retried_once_but_invalid_config_never_retried(tmp_path):
    from urllib.error import URLError
    with patch.object(p, "llama_generate", side_effect=[URLError("synthetic unavailable server"), ("raw", {"seconds": 0})]) as call:
        raw, metadata = p.generate_with_retry("prompt", admitted_config(), tmp_path)
    assert raw == "raw" and call.call_count == 2 and len(metadata["attempts"]) == 2
    second = tmp_path / "invalid"
    second.mkdir()
    with patch.object(p, "llama_generate", side_effect=ValueError("not admitted")) as call:
        with pytest.raises(ValueError):
            p.generate_with_retry("prompt", admitted_config(), second)
    assert call.call_count == 1


def test_llama_protocol_uses_one_generation_and_limits_input(tmp_path):
    calls = []
    def fake(base, route, payload=None, timeout=30):
        calls.append((route, payload))
        return {"/props": {"chat_template": "template", "default_generation_settings": {"n_ctx": 6144}},
                "/apply-template": {"prompt": "rendered"}, "/tokenize": {"tokens": [1, 2]},
                "/completion": {"content": '{"schema_version":"1.0","issues":[]}', "truncated": False, "stop_type": "eos"}}[route]
    with patch.object(p, "http_json", side_effect=fake):
        raw, meta = p.llama_generate("prompt", admitted_config(), tmp_path)
    assert len([c for c in calls if c[0] == "/completion"]) == 1
    request = calls[-1][1]
    assert request["temperature"] == 0 and request["n_predict"] == 2048 and request["prompt"] == "rendered"
    assert "grammar" not in request and meta["input_tokens"] == 2
    config = admitted_config()
    config["max_input_tokens"] = 1
    calls.clear()
    with patch.object(p, "http_json", side_effect=fake), pytest.raises(ValueError, match="truncation"):
        p.llama_generate("prompt", config, tmp_path)
    assert not any(route == "/completion" for route, _ in calls)


def test_container_uses_readonly_tests_and_no_network(tmp_path):
    p.WORK.mkdir(exist_ok=True)
    # evaluate_workspace expects its caller to place workspace under the verified root.
    import tempfile
    with tempfile.TemporaryDirectory(dir=p.WORK) as temp:
        directory = Path(temp)
        commands = []
        def fake(command, **kwargs):
            commands.append(command)
            report_dir = directory.parent / (directory.name + "-reports")
            p.dump(report_dir / "result.json", {"status": "ok", "tests": {"test": {"outcome": "passed"}}})
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        config = p.load(p.ROOT / "configs/llama.example.json")
        with patch.object(p.subprocess, "run", side_effect=fake):
            report = p.evaluate_workspace("gcd", config, directory)
        command = commands[0]
        assert "--network=none" in command and "--read-only" in command
        assert any("target=/workspace,readonly" in arg for arg in command)
        assert "--cap-drop=ALL" in command and report["status"] == "ok"
