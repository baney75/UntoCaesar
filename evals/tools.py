"""The tools a model gets in an eval run: a bash limited to caesar lines, and caesar-mcp over stdio.

Test build: synthetic cases only, not for real records.

The bash tool runs one caesar line (or one caesar set heredoc) per call in the job's parent
folder, plus two read-only forms for the person's documents: `ls documents` and
`cat documents/<file>`. Anything else is refused with a plain message and never reaches a shell.
Both the bash calls and the MCP server run under `strace -f` on Linux when strace works, and
every connect, sendto or sendmsg to an AF_INET or AF_INET6 address counts as a network
connection. Where strace is missing or cannot attach, the run is marked not traced, which fails
the network bar (fail closed).
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEAM = ROOT / "evals" / "seam.py"
END = "CAESAR_END"
HEREDOC = f"<<'{END}'"
DOC_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
INET = re.compile(r"\b(connect|sendto|sendmsg)\(.*sa_family=AF_INET6?\b")
OPERATORS = set("();<>|&")

BASH_TOOL = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": ("Run one caesar command line (for a caesar set heredoc, all of its lines in one call) in the"
                        " job's folder. To read the person's documents: ls documents, or cat documents/<file>."
                        " Nothing else runs."),
        "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "The command."}},
                       "required": ["command"]},
    },
}


def check_command(command: str) -> str | None:
    """Why a bash command is refused, or None when it may run."""
    text = command.strip("\n")
    if not text.strip():
        return "Give one caesar command."
    first, _, rest = text.partition("\n")
    first = first.strip()
    if first in ("ls documents", "ls documents/", "ls"):
        return None if not rest.strip() else "Run one command per call."
    if first.startswith("cat "):
        parts = first.split()
        ok = (len(parts) == 2 and parts[1].startswith("documents/")
              and DOC_NAME.fullmatch(parts[1].removeprefix("documents/")) is not None)
        return None if ok and not rest.strip() else "Only cat documents/<file> is allowed, one file per call."
    if not (first == "caesar" or first.startswith("caesar ")):
        return "This bash runs only caesar commands, ls documents and cat documents/<file>."
    heredoc = first.endswith(HEREDOC)
    head = first[: -len(HEREDOC)].rstrip() if heredoc else first
    if "$" in head or "`" in head:
        return "Write the command without $ or backticks; text from a document goes in the heredoc lines."
    try:
        lex = shlex.shlex(head, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError as err:
        return f"bash could not read that line ({err})."
    if any(t and set(t) <= OPERATORS for t in tokens):
        return "Run one caesar command per call, with no ;, &&, |, > or other shell operators."
    if heredoc:
        body = rest.split("\n")
        if END not in [line.rstrip() for line in body]:
            return f"The heredoc needs its {END} line."
        after = body[[line.rstrip() for line in body].index(END) + 1:]
        if any(line.strip() for line in after):
            return f"Nothing may follow the {END} line."
    elif rest.strip():
        return "Run one caesar command per call."
    return None


def strace_path() -> str | None:
    return shutil.which("strace") if sys.platform.startswith("linux") else None


def traced(argv: list[str], log: Path | None) -> list[str]:
    if log is None:
        return argv
    return [strace_path(), "-f", "-qq", "-e", "trace=connect,sendto,sendmsg", "-o", str(log), *argv]


def count_connections(log: Path) -> tuple[bool, int, list[str]]:
    """(traced, network connections, the lines) from an strace log; an absent or empty log means not traced."""
    if not log.exists():
        return False, 0, []
    text = log.read_text(errors="replace")
    if "ptrace" in text and "Operation not permitted" in text:
        return False, 0, []
    hits = [line for line in text.splitlines() if INET.search(line)]
    return True, len(hits), hits[:20]


@dataclass
class Sandbox:
    """One run's tools: the job folder, its environment and the trace logs."""

    workdir: Path
    job: Path
    env: dict
    trace: bool
    logs: list[Path] = field(default_factory=list)
    calls: int = 0

    def log(self) -> Path | None:
        if not self.trace:
            return None
        path = self.workdir / "trace" / f"{len(self.logs):04d}.strace"
        path.parent.mkdir(exist_ok=True)
        self.logs.append(path)
        return path

    def bash(self, command: str, timeout: int = 120) -> str:
        self.calls += 1
        why = check_command(command)
        if why:
            return f"refused: {why}"
        first = command.strip("\n").split("\n", 1)[0].strip()
        if first.startswith("ls"):
            docs = sorted(p.name for p in (self.job / "documents").iterdir())
            return "\n".join(f"documents/{n}" for n in docs) or "(no documents)"
        if first.startswith("cat "):
            path = self.job / "documents" / first.split()[1].removeprefix("documents/")
            return path.read_text(encoding="utf-8") if path.is_file() else f"cat: {first.split()[1]}: No such file"
        argv = traced(["bash", "-c", command], self.log())
        try:
            done = subprocess.run(argv, cwd=self.workdir, env=self.env, capture_output=True, timeout=timeout,
                                  stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return f"timed out after {timeout} seconds"
        out = done.stdout.decode(errors="replace") + done.stderr.decode(errors="replace")
        return out if out.strip() else f"(exit {done.returncode}, no output)"

    def network(self) -> dict:
        if not self.trace:
            return {"traced": False, "connections": 0, "why": "strace is missing or not on Linux"}
        total, hits, all_traced = 0, [], True
        for log in self.logs:
            ok, n, lines = count_connections(log)
            if not ok:
                all_traced = False
            total += n
            hits += lines
        return {"traced": all_traced and bool(self.logs), "connections": total, "lines": hits[:20],
                "logs": len(self.logs)}


class MCPClient:
    """caesar-mcp over stdio, started the way Local Studio starts a local-only plugin's server."""

    def __init__(self, sandbox: Sandbox, env: dict):
        self.log = sandbox.log()
        argv = traced([sys.executable, str(SEAM), "mcp"], self.log)
        self.proc = subprocess.Popen(argv, cwd=sandbox.workdir, env=env, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.next_id = 0
        self.lock = threading.Lock()
        init = self.request("initialize", {"protocolVersion": "2025-06-18", "clientInfo": {"name": "local-studio-eval"},
                                           "capabilities": {}})
        self.instructions = init.get("instructions", "")
        self.tools = self.request("tools/list", {})["tools"]

    def request(self, method: str, params: dict, timeout: int = 120) -> dict:
        with self.lock:
            self.next_id += 1
            msg = {"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params}
            self.proc.stdin.write(json.dumps(msg).encode() + b"\n")
            self.proc.stdin.flush()
            timer = threading.Timer(timeout, self.proc.kill)
            timer.start()
            try:
                raw = self.proc.stdout.readline()
            finally:
                timer.cancel()
        if not raw:
            raise RuntimeError("caesar-mcp closed: " + self.proc.stderr.read().decode(errors="replace")[-500:])
        reply = json.loads(raw)
        if "error" in reply:
            raise RuntimeError(reply["error"].get("message", "caesar-mcp error"))
        return reply["result"]

    def call(self, name: str, arguments: dict) -> str:
        try:
            result = self.request("tools/call", {"name": name, "arguments": arguments})
        except RuntimeError as err:
            return f"error: {err}"
        return "\n".join(c.get("text", "") for c in result.get("content", []))

    def openai_tools(self) -> list[dict]:
        return [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                  "parameters": t["inputSchema"]}} for t in self.tools]

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.stdin.close()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def caesar_bin(workdir: Path) -> Path:
    """A bin folder whose caesar runs evals/seam.py cli, so NEXT lines work as the skill writes them."""
    folder = workdir / "bin"
    folder.mkdir(exist_ok=True)
    script = folder / "caesar"
    script.write_text(f"#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(SEAM))} cli \"$@\"\n")
    script.chmod(0o755)
    return folder


def environment(workdir: Path, key: str, tier: str) -> dict:
    """The run's environment: no proxy or provider variables, caesar on PATH, the run's ledger key."""
    keep = {k: v for k, v in os.environ.items() if k in ("HOME", "LANG", "LC_ALL", "TMPDIR", "USER", "LOGNAME")}
    path = f"{caesar_bin(workdir)}:/usr/bin:/bin"
    return {**keep, "PATH": path, "CAESAR_CMD": "caesar", "CAESAR_TIER": tier, "CAESAR_EVAL_KEY": key,
            "PYTHONDONTWRITEBYTECODE": "1"}
