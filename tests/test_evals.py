"""The tier eval harness (evals/), run with fake models so CI covers it without one.

Test build: synthetic cases only, not for real records.
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals"))
sys.path.insert(0, str(ROOT / "tests" / "golden"))

import drivers  # noqa: E402
import run as R  # noqa: E402
import score as SC  # noqa: E402
import tools as T  # noqa: E402

posix = pytest.mark.skipif(sys.platform == "win32", reason="the harness runs caesar through bash and /bin/sh")


def records(out: Path) -> list[dict]:
    return [json.loads(line) for line in (out / "records.jsonl").read_text(encoding="utf-8").splitlines()]


# ---------------------------------------------------------------------------
# the bash tool
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("command", [
    "caesar status",
    "caesar --job /tmp/x/caesar-job confirm",
    "caesar set screen.ssa1099 no --source answer",
    "caesar set w2.1.employer --stdin <<'CAESAR_END'\nvalue: Acme; Inc | $(x)\nsource: answer\nCAESAR_END\n",
    "ls documents",
    "cat documents/w2-1.txt",
])
def test_bash_allows_caesar_lines_and_reading_documents(command):
    assert T.check_command(command) is None


@pytest.mark.parametrize("command", [
    "rm -rf /",
    "caesar status; curl example.com",
    "caesar status && ls",
    "caesar status | tee x",
    "caesar status > out",
    "caesar set x $(id) --source answer",
    "caesar set x `id` --source answer",
    "caesar set screen.ssa1099 <yes or no> --source answer",
    "cat /etc/passwd",
    "cat documents/../facts.toml",
    "caesar status\ncaesar ask",
    "caesar set a --stdin <<'CAESAR_END'\nvalue: 1\nsource: answer\n",
    "caesar set a --stdin <<'CAESAR_END'\nvalue: 1\nsource: answer\nCAESAR_END\nrm -rf /",
    "",
])
def test_bash_refuses_everything_else(command):
    assert T.check_command(command)


def test_strace_lines_count_inet_connections_only(tmp_path):
    log = tmp_path / "a.strace"
    log.write_text(
        '101 connect(3, {sa_family=AF_UNIX, sun_path="/run/x"}, 110) = 0\n'
        '101 connect(4, {sa_family=AF_INET, sin_port=htons(443), sin_addr=inet_addr("192.0.2.1")}, 16) = -1\n'
        '102 sendto(5, "x", 1, 0, {sa_family=AF_INET6, sin6_port=htons(53)}, 28) = 1\n', encoding="utf-8")
    assert T.count_connections(log)[:2] == (True, 2)
    assert T.count_connections(tmp_path / "missing.strace")[0] is False
    denied = tmp_path / "b.strace"
    denied.write_text("strace: attach: ptrace(PTRACE_SEIZE, 1): Operation not permitted\n", encoding="utf-8")
    assert T.count_connections(denied)[0] is False


def test_untraced_runs_fail_the_network_bar(tmp_path):
    box = T.Sandbox(tmp_path, tmp_path, {}, trace=False)
    assert box.network()["traced"] is False


# ---------------------------------------------------------------------------
# whole runs with the no-model reader
# ---------------------------------------------------------------------------

@posix
def test_reader_runs_reach_the_exact_return_and_the_right_refusal(tmp_path):
    out = tmp_path / "out"
    code = R.main(["--suite", "M", "--driver", "reader", "--runs", "1", "--no-trace", "--out", str(out),
                   "--cases", "single-w2", "freelancer-schedule-c", "misread-w2-box1", "refuse-inventory-cogs"])
    assert code == 0
    got = {r["case"]: r for r in records(out)}
    for case in ("single-w2", "freelancer-schedule-c", "misread-w2-box1"):
        assert got[case]["outcome"] == "prepared" and got[case]["exact"], got[case]
        assert got[case]["strict"] == got[case]["lines_scored"]
    assert got["refuse-inventory-cogs"]["refusal_correct"]
    assert not any(r["silent_error"] for r in got.values())
    assert (out / "runs" / "single-w2" / "run-1" / "transcript.json").exists()
    assert not (out / ".seam").exists() or not any((out / ".seam").rglob("truth.json"))


@posix
def test_a_misread_is_caught_by_the_confirm_card_not_prepared_silently(tmp_path, monkeypatch):
    monkeypatch.setattr(drivers, "make", lambda *a, **k: drivers.ReaderDriver(misread={"w2.1.box1": "25000"}))
    out = tmp_path / "out"
    R.main(["--suite", "S", "--driver", "reader", "--runs", "1", "--no-trace", "--out", str(out), "--cases", "single-w2"])
    (rec,) = records(out)
    log = json.loads((out / "runs" / "single-w2" / "run-1" / "transcript.json").read_text(encoding="utf-8"))["log"]
    assert any("1 rejected" in e.get("result", "") for e in log if e.get("tool") == "caesar_confirm")
    assert not rec["silent_error"]
    assert rec["exact"] or rec["outcome"] == "check_failed"


class FakeOpenAI(BaseHTTPRequestHandler):
    """An OpenAI-compatible /chat/completions whose 'model' is the reader."""

    reader: drivers.ReaderDriver

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        reply = type(self).reader.chat(body["messages"], body.get("tools"))
        msg = {"role": "assistant", "content": reply["content"]}
        if reply["tool_calls"]:
            msg["tool_calls"] = [{"id": c["id"], "type": "function",
                                  "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])}}
                                 for c in reply["tool_calls"]]
        data = json.dumps({"choices": [{"message": msg}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@posix
def test_the_openai_driver_runs_a_case_through_a_compatible_server(tmp_path):
    FakeOpenAI.reader = drivers.ReaderDriver()
    server = HTTPServer(("127.0.0.1", 0), FakeOpenAI)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        out = tmp_path / "out"
        R.main(["--suite", "S", "--driver", "openai", "--model", "fake", "--base-url",
                f"http://127.0.0.1:{server.server_port}/v1", "--runs", "1", "--no-trace", "--out", str(out),
                "--cases", "hoh-one-child"])
    finally:
        server.shutdown()
    (rec,) = records(out)
    assert rec["outcome"] == "prepared" and rec["exact"], rec


def test_quota_answers_stop_every_run(tmp_path):
    class Quota:
        name = "quota"

        def chat(self, messages, tools):
            raise drivers.QuotaStop("usage limit")

    out = tmp_path / "out"
    R_make = drivers.make
    drivers.make = lambda *a, **k: Quota()
    try:
        assert R.main(["--suite", "S", "--mode", "baseline", "--driver", "openai", "--runs", "3", "--out", str(out),
                       "--cases", "single-w2", "mfs-one-w2"]) == 3
    finally:
        drivers.make = R_make
    assert (out / "STOPPED").exists()
    assert not (out / "records.jsonl").exists()


# ---------------------------------------------------------------------------
# baselines
# ---------------------------------------------------------------------------

class Canned:
    name = "canned"

    def __init__(self, reply):
        self.reply = reply
        self.prompts = []

    def chat(self, messages, tools):
        assert tools is None
        self.prompts.append(messages[-1]["content"])
        return {"content": self.reply(messages[-1]["content"]), "tool_calls": []}


def baseline(tmp_path, monkeypatch, reply, cases):
    fake = Canned(reply)
    monkeypatch.setattr(drivers, "make", lambda *a, **k: fake)
    out = tmp_path / "out"
    R.main(["--suite", "M", "--mode", "baseline", "--driver", "openai", "--runs", "1", "--out", str(out), "--cases", *cases])
    return fake, {r["case"]: r for r in records(out)}


def test_baseline_wrong_lines_count_as_silent_errors(tmp_path, monkeypatch):
    fake, got = baseline(tmp_path, monkeypatch, lambda p: 'Here: {"refuse": false, "lines": {"1a": 1, "24": 2}}',
                         ["single-w2", "refuse-ssa1099"])
    assert got["single-w2"]["silent_error"] and not got["single-w2"]["exact"]
    assert got["refuse-ssa1099"]["silent_error"] and not got["refuse-ssa1099"]["refusal_correct"]
    assert "documents/w2-1.txt" in fake.prompts[0] and "Q: " in fake.prompts[0]


def test_baseline_exact_lines_and_refusals_score_right(tmp_path, monkeypatch):
    truth = R.known_1040(R.CASES / "single-w2")
    lines = {k.removeprefix("1040."): f"${v:,}" for k, v in truth.items()}

    def reply(prompt):
        if "SSA-1099" in prompt and "ssa-1099-1.txt" in prompt:
            return '{"refuse": true, "reason": "Social Security benefits"}'
        return json.dumps({"refuse": False, "lines": lines})

    _, got = baseline(tmp_path, monkeypatch, reply, ["single-w2", "refuse-ssa1099"])
    assert got["single-w2"]["exact"] and not got["single-w2"]["silent_error"]
    assert got["refuse-ssa1099"]["refusal_correct"] and not got["refuse-ssa1099"]["silent_error"]


def test_baseline_prompt_carries_the_misread_correction():
    prompt = R.baseline_prompt(R.CASES / "misread-w2-box1")
    assert "w2.1.box1" in prompt and "52000" in prompt


# ---------------------------------------------------------------------------
# the tier table
# ---------------------------------------------------------------------------

def write_results(folder: Path, suite: str, rows: list[dict]) -> Path:
    folder.mkdir()
    (folder / "meta.json").write_text(json.dumps({"suite": suite, "mode": "plugin", "driver": "fake", "runs": 10}))
    base = {"suite": suite, "mode": "plugin", "silent_error": False, "network": {"traced": True, "connections": 0}}
    (folder / "records.jsonl").write_text("".join(json.dumps({**base, **r}) + "\n" for r in rows))
    return folder


def runs(case, expected, exact, total=10, **extra):
    return [{"case": case, "run": k, "expected_outcome": expected, "outcome": "prepared", "exact": k <= exact,
             **({"refusal_correct": k <= exact} if expected == "refused" else {}), **extra} for k in range(1, total + 1)]


def test_tier_bars_follow_the_spec_table(tmp_path):
    s_pass = write_results(tmp_path / "s", "S", runs("a", "prepared", 8) + runs("r", "refused", 10))
    assert SC.render(s_pass)[1]
    m_fail = write_results(tmp_path / "m", "M", runs("a", "prepared", 8) + runs("r", "refused", 10))
    assert not SC.render(m_fail)[1]
    refusal_miss = write_results(tmp_path / "r", "S", runs("a", "prepared", 10) + runs("r", "refused", 9))
    assert not SC.render(refusal_miss)[1]
    silent = write_results(tmp_path / "x", "S", runs("a", "prepared", 10, silent_error=True) + runs("r", "refused", 10))
    assert not SC.render(silent)[1]
    untraced = write_results(tmp_path / "u", "S", runs("a", "prepared", 10, network={"traced": False, "connections": 0})
                             + runs("r", "refused", 10))
    text, ok = SC.render(untraced)
    assert not ok and "not traced" in text
