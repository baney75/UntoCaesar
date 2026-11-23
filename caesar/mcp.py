"""caesar-mcp: a stdio MCP server over the caesar engine, one tool per caesar command.

Each tool runs the caesar command in this process and replies with exactly what the CLI prints,
banner to NEXT line. No tool sets a confirmed flag. Jobs are kept apart by where they were made
(docs/SPEC.md):

- Started by Local Studio with LOCAL_STUDIO_LOCAL_ONLY=1, the server opens Local Studio jobs by
  their full path, and may open an outside job to read it and confirm its facts through Local
  Studio's question card. That job stays marked outside.
- Started any other way (the person's own assistant), it opens only outside jobs, in its own
  folder, records the client's name in each, says where the figures go in its first reply about
  each job, and never confirms.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import sys
from pathlib import Path

from . import __version__
from . import cli

PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}")
COMMANDS = {
    "status": "Where the return stands and the one command to run next (NEXT).",
    "new": "Start a job folder for tax year 2025.",
    "ask": "The next interview question, and the set command that records its answer.",
    "set": "Record one fact: its value and where it came from (the document and box, or answer).",
    "confirm": "Show each unconfirmed fact to the person in Local Studio's question card and record only their answer.",
    "facts": "List every fact with its source and whether the person confirmed it.",
    "compute": "Compute the return from the facts.",
    "check": "Run the consistency checks and refusals.",
    "explain": "Show one line's rule, inputs and IRS source.",
    "worksheet": "Write worksheet.html, the show-your-work page.",
    "done": "Finish and show the final state.",
}


def outside_root() -> Path:
    home = Path.home()
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = home / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or home / ".local" / "share")
    return base / "UntoCaesar" / "outside-jobs"


def text(*lines: str) -> str:
    return "\n".join([cli.BANNER, *lines, "NEXT: none"]) + "\n"


class Server:
    def __init__(self, local_only: bool, root: Path):
        self.local_only = local_only
        self.root = root
        self.client = ""
        self.told: set[Path] = set()

    # -- JSON-RPC -----------------------------------------------------------

    def handle(self, msg) -> dict | None:
        if not isinstance(msg, dict) or "method" not in msg:
            return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "not a JSON-RPC request"}}
        if "id" not in msg:
            return None
        method, params = msg["method"], msg.get("params") or {}
        if not isinstance(params, dict) or not isinstance(params.get("arguments") or {}, dict):
            return {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32602, "message": "params and arguments must be objects"}}
        if method == "initialize":
            info = params.get("clientInfo") or {}
            name = "".join(ch for ch in str(info.get("name", "")) if ch.isprintable()).strip()[:80]
            self.client = name or "an unnamed assistant"
            asked = params.get("protocolVersion")
            result = {"protocolVersion": asked if asked in PROTOCOLS else PROTOCOLS[0],
                      "capabilities": {"tools": {}},
                      "serverInfo": {"name": "caesar-mcp", "version": __version__},
                      "instructions": self.instructions()}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": self.tools()}
        elif method == "tools/call":
            name = params.get("name")
            if not isinstance(name, str) or name.removeprefix("caesar_") not in COMMANDS or not name.startswith("caesar_"):
                return {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32602, "message": f"no tool named {name}"}}
            out, failed = self.call(name.removeprefix("caesar_"), params.get("arguments") or {})
            result = {"content": [{"type": "text", "text": out}], "isError": failed}
        else:
            return {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": f"no method {method}"}}
        return {"jsonrpc": "2.0", "id": msg["id"], "result": result}

    def instructions(self) -> str:
        where = ("This server runs in a Local Studio thread on a local model. Name each job by its full folder path."
                 if self.local_only else
                 f"{cli.OUTSIDE_NOTICE}. Name each job with a short name such as 2025-return; jobs live in"
                 f" {self.root}. Facts are confirmed only by the person in Local Studio, never here.")
        return (f"{cli.BANNER} UntoCaesar prepares a federal Form 1040 for tax year 2025. caesar does every number."
                " Every reply ends with NEXT: a caesar command; call the tool of the same name (caesar_<command>) with"
                " the job and the values NEXT shows. Never do tax math, and never file, sign, send or pay. " + where)

    def tools(self) -> list[dict]:
        job = ({"type": "string", "description": "The job folder's full path, as caesar prints it after --job."}
               if self.local_only else
               {"type": "string", "description": "A short name for this return (letters, digits, - and _), or the"
                " full path caesar prints after --job."})
        extra = {
            "new": {"year": {"type": "integer", "description": "Tax year (2025)."}},
            "set": {"fact": {"type": "string", "description": "The fact name from NEXT, such as w2.1.box1."},
                    "value": {"type": "string", "description": "The value exactly as on the form or as the person said it."},
                    "source": {"type": "string", "description": "The document and box, such as W-2 from Acme, box 1, or: answer."}},
            "confirm": {"fact": {"type": "string", "description": "One fact to confirm; leave out to confirm every unconfirmed fact."}},
            "explain": {"line": {"type": "string", "description": "A line such as 16, 1040.16 or 8812.14."}},
        }
        required = {"set": ["fact", "value", "source"], "explain": ["line"]}
        out = []
        for name, desc in COMMANDS.items():
            if name == "confirm" and not self.local_only:
                desc = "Outside Local Studio this never confirms; it says how the person confirms in Local Studio."
            props = {"job": job, **extra.get(name, {})}
            out.append({"name": f"caesar_{name}", "description": desc,
                        "inputSchema": {"type": "object", "properties": props, "required": ["job", *required.get(name, [])],
                                        "additionalProperties": False}})
        return out

    # -- jobs ---------------------------------------------------------------

    def resolve(self, job) -> tuple[Path | None, str]:
        """The job's folder, or None and why this server will not open it."""
        if not isinstance(job, str) or not job.strip():
            return None, "Give the job: " + ("its full folder path." if self.local_only else "a short name such as 2025-return.")
        if self.local_only:
            path = Path(job)
            if not path.is_absolute():
                return None, "Give the job folder's full path, as caesar prints it after --job."
            return path, ""
        root = self.root.resolve()
        if NAME.fullmatch(job):
            path = root / job
        elif Path(job).is_absolute() and Path(job).resolve().parent == root:
            path = Path(job).resolve()
        else:
            path = None
        if path is None or (cli.Job(path).state_path.exists() and not cli.Job(path).outside()):
            return None, ("caesar-mcp outside Local Studio opens only the jobs it made, in its own folder"
                          f" ({root}). A job made in Local Studio stays in Local Studio: open it there.")
        return path, ""

    def call(self, command: str, args: dict) -> tuple[str, bool]:
        path, why = self.resolve(args.get("job"))
        if path is None:
            return text(why), True
        argv, data = ["--job", str(path), command], None
        try:
            if command == "new" and args.get("year") is not None:
                argv += ["--year", str(int(args["year"]))]
            elif command == "set":
                fact, value, source = (args.get(k) for k in ("fact", "value", "source"))
                if not (isinstance(fact, str) and WORD.fullmatch(fact) and isinstance(value, str) and isinstance(source, str)):
                    return text("caesar_set needs fact (a name such as w2.1.box1), value and source, each as text."), True
                argv += [fact, "--stdin"]
                data = f"value:{value}\nsource:{source}\n"
            elif command in ("confirm", "explain"):
                key = "fact" if command == "confirm" else "line"
                if args.get(key) is not None:
                    if not (isinstance(args[key], str) and WORD.fullmatch(args[key])):
                        return text(f"{key} must be a name such as {'w2.1.box1' if key == 'fact' else '1040.16'}."), True
                    argv.append(args[key])
                elif command == "explain":
                    return text("caesar_explain needs line, such as 16 or 1040.16."), True
        except (TypeError, ValueError):
            return text("year must be a number such as 2025."), True
        outside = not self.local_only
        ctx = cli.Context(origin="outside" if outside else "local-studio", client=self.client if outside else "",
                          can_confirm=self.local_only)
        if outside and cli.Job(path).state_path.exists():
            self.add_client(cli.Job(path))
        code, out = run_cli(argv, data, ctx)
        if outside and path not in self.told:
            self.told.add(path)
            first, _, rest = out.partition("\n")
            out = f"{first}\n{cli.OUTSIDE_NOTICE}.\n{rest}"
        return out, code == 2

    def add_client(self, job: cli.Job) -> None:
        state = job.state()
        clients = state.setdefault("clients", [])
        if self.client and self.client not in clients:
            clients.append(self.client)
            job.save_state(state)


def run_cli(argv: list[str], data: str | None, ctx: cli.Context) -> tuple[int, str]:
    buf = io.StringIO()
    saved = sys.stdin
    if data is not None:
        sys.stdin = io.TextIOWrapper(io.BytesIO(data.encode("utf-8")), encoding="utf-8")
    try:
        with contextlib.redirect_stdout(buf):
            code = cli.main(argv, ctx)
    except SystemExit:
        # argparse exits on arguments it cannot read; the reply says so instead of ending the server.
        code = 2
        buf = io.StringIO(text("caesar could not read those arguments."))
    finally:
        sys.stdin = saved
    return code, buf.getvalue()


def main() -> int:
    server = Server(os.environ.get("LOCAL_STUDIO_LOCAL_ONLY") == "1", outside_root())
    inp, out = sys.stdin.buffer, sys.stdout.buffer
    for raw in inp:
        if not raw.strip():
            continue
        try:
            msg = json.loads(raw)
        except ValueError:
            msg = None
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "not JSON"}}
        if msg is not None:
            try:
                reply = server.handle(msg)
            except Exception as err:  # one bad call must not end the server
                ident = msg.get("id") if isinstance(msg, dict) else None
                reply = {"jsonrpc": "2.0", "id": ident, "error": {"code": -32603, "message": f"caesar-mcp: {type(err).__name__}"}}
        if reply is not None:
            out.write(json.dumps(reply).encode("utf-8") + b"\n")
            out.flush()
    return 0
