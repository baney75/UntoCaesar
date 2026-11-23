"""caesar-mcp: one tool per caesar command, and jobs kept apart by where they were made (docs/SPEC.md)."""

import json
import os
from html import escape
import subprocess
import sys

import pytest
import runner
import to_facts

from caesar import cli
from caesar import mcp

ROOT = runner.ROOT
NOTICE = "This job's figures go to the assistant you are using and its provider."
ON_PAGE = escape(NOTICE.rstrip("."))


@pytest.fixture(autouse=True)
def caesar_cmd(monkeypatch):
    monkeypatch.setenv("CAESAR_CMD", "caesar")


@pytest.fixture
def root(tmp_path):
    return (tmp_path / "outside-jobs").resolve()


def outside(root, client="Test Assistant"):
    server = mcp.Server(local_only=False, root=root)
    server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                   "params": {"protocolVersion": "2025-06-18", "clientInfo": {"name": client}}})
    return server


def local(root):
    server = mcp.Server(local_only=True, root=root)
    server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"clientInfo": {"name": "Local Studio"}}})
    return server


def call(server, tool, **args):
    reply = server.handle({"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": f"caesar_{tool}", "arguments": args}})
    result = reply["result"]
    return result["content"][0]["text"], result["isError"]


def drive(server, job, path, folder):
    """Follow NEXT through the tools, the way an assistant does, until NEXT: none or a fix only the person can make."""
    given = to_facts.all_facts(to_facts.load(folder))
    out, _ = call(server, "new", job=job)
    replies = [out]
    for _ in range(1000):
        step = runner.next_command(out, path)
        if step is None:
            return replies
        words = step.split()
        if words[0] == "set":
            if to_facts.F.value(cli.Job(path).facts(), words[1]) is not None or words[1] not in given:
                return replies
            value, source = given[words[1]]
            out, _ = call(server, "set", job=job, fact=words[1], value=value, source=source)
        else:
            out, _ = call(server, words[0], job=job)
        replies.append(out)
    raise AssertionError("caesar never said NEXT: none")


def final(path):
    return json.loads((path / "state.json").read_text(encoding="utf-8")).get("final")


def test_tools_are_the_cli_commands_and_none_sets_a_flag(root):
    tools = outside(root).handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
    assert sorted(t["name"] for t in tools) == sorted(f"caesar_{c}" for c in cli.COMMANDS)
    for tool in tools:
        assert not any("confirm" in p for p in tool["inputSchema"]["properties"] if p != "fact"), tool
        assert tool["inputSchema"]["additionalProperties"] is False


def test_replies_carry_the_cli_text_and_next_line(root, tmp_path):
    path = tmp_path / "ls-job"
    server = local(root)
    out, failed = call(server, "new", job=str(path))
    code, cli_out = runner.caesar(tmp_path / "cli-job", "new")
    assert not failed and code == 0
    assert out.replace(str(path), "J") == cli_out.replace(str(tmp_path / "cli-job"), "J")
    out, failed = call(server, "set", job=str(path), fact="screen.ssa1099", value="no", source="answer")
    assert not failed and out.strip().endswith(f"NEXT: caesar --job {cli.quote_arg(str(path))} ask")


@pytest.mark.parametrize("fact", ["screen.ssa1099.confirmed", "confirmed", "--confirmed"])
def test_set_cannot_reach_the_confirmed_flag(root, tmp_path, fact):
    path = tmp_path / "job"
    server = local(root)
    call(server, "new", job=str(path))
    out, _ = call(server, "set", job=str(path), fact=fact, value="yes", source="answer")
    assert out.strip().endswith("NEXT: none")
    assert 'confirmed = "yes"' not in (path / "facts.toml").read_text(encoding="utf-8")


def test_golden_outside_server_refuses_a_local_studio_job(root, tmp_path):
    path = tmp_path / "ls-job"
    call(local(root), "new", job=str(path))
    call(local(root), "set", job=str(path), fact="screen.ssa1099", value="no", source="answer")
    server = outside(root)
    for tool in cli.COMMANDS:
        out, failed = call(server, tool, job=str(path))
        assert failed and "opens only the jobs it made, in its own folder" in out, (tool, out)
        assert out.strip().endswith("NEXT: none")
    # A Local Studio job moved into the outside folder is still refused, by name or by path.
    planted = root / "planted"
    root.mkdir(parents=True)
    path.rename(planted)
    for job in ("planted", str(planted)):
        out, failed = call(server, "facts", job=job)
        assert failed and "screen.ssa1099" not in out
    for job in ("../ls-job", "a/b", ""):
        _, failed = call(server, "status", job=job)
        assert failed


def test_local_studio_server_needs_a_full_path(root):
    out, failed = call(local(root), "status", job="caesar-job")
    assert failed and "full path" in out


def test_outside_job_shows_where_its_figures_go(root):
    folder = runner.CASES / "single-w2"
    path = root / "my-2025"
    assistant = outside(root, client="Grok Bot")
    replies = drive(assistant, "my-2025", path, folder)
    assert replies[0].splitlines()[1] == NOTICE
    assert sum(NOTICE in r for r in replies) == 1
    assert any("cannot ask the person" in r for r in replies)
    assert final(path) == "computed, not confirmed"
    page = (path / "worksheet.html").read_text(encoding="utf-8")
    assert page.index(ON_PAGE) < page.index("<h1>") and "Assistant: Grok Bot." in page
    # Opened in Local Studio, the job stays marked outside.
    call(local(root), "facts", job=str(path))
    state = json.loads((path / "state.json").read_text(encoding="utf-8"))
    assert state["origin"] == "outside" and state["clients"] == ["Grok Bot"]


def test_notice_comes_once_per_job(root):
    server = outside(root)
    first, _ = call(server, "new", job="a")
    again, _ = call(server, "status", job="a")
    other, _ = call(server, "new", job="b")
    assert NOTICE in first and NOTICE not in again and NOTICE in other


def test_protocol_basics(root):
    server = outside(root)
    init = server.handle({"jsonrpc": "2.0", "id": 0, "method": "initialize",
                          "params": {"protocolVersion": "2024-11-05", "clientInfo": {"name": "x"}}})
    assert init["result"]["protocolVersion"] == "2024-11-05"
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert server.handle({"jsonrpc": "2.0", "id": 3, "method": "ping"})["result"] == {}
    assert server.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "caesar_rm"}})["error"]
    assert server.handle({"jsonrpc": "2.0", "id": 5, "method": "nope"})["error"]["code"] == -32601


def test_the_launcher_serves_over_stdio(tmp_path):
    env = dict(os.environ, HOME=str(tmp_path), XDG_DATA_HOME=str(tmp_path / "xdg"), LOCALAPPDATA=str(tmp_path / "lad"))
    env.pop("LOCAL_STUDIO_LOCAL_ONLY", None)
    env.pop("CAESAR_CMD", None)
    lines = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"clientInfo": {"name": "stdio test"}}},
             {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "caesar_new", "arguments": {"job": "j"}}}]
    done = subprocess.run([sys.executable, str(ROOT / "bin" / "caesar-mcp")], input="\n".join(map(json.dumps, lines)) + "\n",
                          capture_output=True, text=True, env=env, timeout=60)
    replies = [json.loads(line) for line in done.stdout.splitlines()]
    text = replies[1]["result"]["content"][0]["text"]
    assert NOTICE in text and "Started a tax year 2025 job" in text
    assert str(ROOT / "bin" / "caesar") in text.splitlines()[-1]
