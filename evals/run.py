"""Drive one model through /taxes on each case of a tier suite, the way Local Studio would.

Test build: synthetic cases only, not for real records.

Each run is a fresh session: the system prompt names the local model, the user turn is the
skill text plus the tier card and "/taxes", and the tools are a bash limited to caesar lines
(evals/tools.py) and caesar-mcp's tools over stdio, started with LOCAL_STUDIO_LOCAL_ONLY=1. The
simulated person (evals/person.py) answers the model's questions, and the scripted person inside
caesar-mcp (evals/seam.py) answers the confirm cards, rejecting any misread value.

    python3 evals/run.py --suite S --driver openai --model <name> --runs 10
    python3 evals/run.py --suite M --mode baseline --driver openai --model <name> --runs 1
    python3 evals/run.py --suite M --mode baseline --driver claude --cases single-w2 freelancer-schedule-c --runs 1

Every run writes one line to <out>/records.jsonl and its transcript under <out>/runs/. Score a
folder with evals/score.py.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
import platform
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "golden"))
sys.path.insert(0, str(ROOT / "evals"))

import drivers  # noqa: E402
import person as P  # noqa: E402
import runner  # noqa: E402
import to_facts  # noqa: E402
import tools as T  # noqa: E402

from caesar import cli  # noqa: E402
from caesar import facts as F  # noqa: E402
from caesar import keystore  # noqa: E402

SKILL = ROOT / "skills" / "plugin" / "untocaesar"
CASES = runner.CASES
EXPLAIN_LINES = ["1040.11a", "1040.16", "1040.24"]
BASELINE_LINES = list(runner.XPATH)


# ---------------------------------------------------------------------------
# cases
# ---------------------------------------------------------------------------

def suite_cases(suite: str, names: list[str] | None = None) -> list[Path]:
    folders = [CASES / n for n in names] if names else runner.case_folders()
    return [f for f in folders if suite in expected(f)["suites"]] if not names else folders


def expected(folder: Path) -> dict:
    return json.loads((folder / "expected.json").read_text(encoding="utf-8"))


_clean_cache: dict[str, dict] = {}


def clean_lines(folder: Path) -> dict:
    """A misread case's correct return: the case run through caesar with the true value."""
    if folder.name not in _clean_cache:
        case = to_facts.load(folder)
        case["untocaesar"] = {k: v for k, v in case["untocaesar"].items() if k != "misread"}
        with tempfile.TemporaryDirectory() as tmp:
            twin = Path(tmp) / folder.name
            twin.mkdir()
            (twin / "input.json").write_text(json.dumps(case), encoding="utf-8")
            _clean_cache[folder.name] = runner.run(twin, workdir=Path(tmp) / "work")["lines"]
    return _clean_cache[folder.name]


def known_lines(folder: Path) -> dict:
    want = expected(folder)
    return want["lines"] if want["outcome"] == "prepared" else clean_lines(folder) if want["outcome"] == "check_failed" else {}


def known_1040(folder: Path) -> dict[str, int]:
    """The TaxCalcBench Form 1040 lines the case is scored on."""
    if (folder / "output.xml").exists():
        return runner.expected_xml(folder)
    lines = known_lines(folder)
    return {k: lines.get(k, 0) for k in runner.XPATH} if lines else {}


# ---------------------------------------------------------------------------
# scoring one run
# ---------------------------------------------------------------------------

def outcome_of(job: Path) -> tuple[str, dict, dict]:
    """(outcome, state, return lines), with the golden runner's outcome names."""
    state = json.loads((job / "state.json").read_text(encoding="utf-8")) if (job / "state.json").exists() else {}
    ret = json.loads((job / "return.json").read_text(encoding="utf-8")) if (job / "return.json").exists() else None
    check = state.get("check", {})
    facts = cli.Job(job).facts() if (job / "facts.toml").exists() else {}
    from caesar import checks as C
    if check.get("refused") or (facts and C.fact_refusals(facts)):
        outcome = "refused"
    elif check and not check.get("passed"):
        outcome = "check_failed"
    elif state.get("final", "").startswith("prepared"):
        outcome = "prepared"
    elif state.get("final"):
        outcome = "computed_not_confirmed"
    else:
        outcome = "unfinished"
    lines = {x["id"]: x["value"] for x in ret["lines"]} if ret else {}
    return outcome, state, lines


def judge_run(folder: Path, outcome: str, state: dict, lines: dict, said: str) -> dict:
    """The measures for one plugin run."""
    want = expected(folder)
    rec: dict = {"expected_outcome": want["outcome"], "outcome": outcome}
    tcb = known_1040(folder)
    if lines and tcb:
        s, le, n = runner.score(lines, tcb)
        rec.update(strict=s, lenient=le, lines_scored=n)
    if want["outcome"] == "refused":
        rec["refusal_correct"] = outcome == "refused" and want["message"] in said
        rec["exact"] = rec["refusal_correct"]
        rec["silent_error"] = outcome == "prepared"
        return rec
    full = known_lines(folder)
    exact_return = outcome == "prepared" and lines == full
    rec["full_return_exact"] = exact_return
    if want["outcome"] == "check_failed":
        fix = state.get("check", {}).get("fix", "")
        rec["exact"] = exact_return or (outcome == "check_failed" and fix == want["fix"])
    else:
        rec["exact"] = exact_return
    rec["silent_error"] = outcome == "prepared" and not exact_return
    return rec


# ---------------------------------------------------------------------------
# a plugin run
# ---------------------------------------------------------------------------

def system_prompt(model: str) -> str:
    return (f"You are an assistant in Local Studio. This session runs the local model {model} through Fonsviva on"
            " this computer (a local model, not a cloud provider). You have a bash tool and the UntoCaesar plugin's"
            " MCP tools. Use the tools to act; talk to the person in plain words when you need an answer from them.")


def first_turn(card: str, job: Path) -> str:
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    tier = (SKILL / "tiers" / f"{card}.md").read_text(encoding="utf-8")
    return (f"<skill>\n{skill}\n\n{tier}\n</skill>\n/taxes\n"
            f"Please do my 2025 federal taxes. This thread's tax job folder is {job} (bash runs in {job.parent},"
            f" where caesar uses it by default), and my tax documents are in {job.name}/documents.")


def trim(messages: list[dict], budget: int) -> list[dict]:
    """Keep the system and first user turns and the newest turns within budget characters, the way a
    host compacts a long thread. A cut leaves a note, and caesar status gets the model back on track."""
    size = sum(len(json.dumps(m)) for m in messages)
    if size <= budget:
        return messages
    head, tail = messages[:2], messages[2:]
    note = {"role": "user", "content": "(Earlier steps were cut to fit the context. Run caesar status to see where the"
            " return stands, then go on.)"}
    while tail and size > budget:
        size -= len(json.dumps(tail.pop(0)))
        while tail and tail[0]["role"] == "tool":  # a tool reply never opens the kept turns
            size -= len(json.dumps(tail.pop(0)))
    return head + [note] + tail


@contextlib.contextmanager
def run_key(key: str):
    """This process reads the run's ledger with the run's key, like the caesar processes it starts."""
    saved = keystore.load_key
    keystore.load_key = lambda create, service=keystore.SERVICE: (bytes.fromhex(key), "")
    try:
        yield
    finally:
        keystore.load_key = saved


def plugin_run(folder: Path, k: int, driver, args, out: Path) -> dict:
    work = out / "runs" / folder.name / f"run-{k}"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    key = secrets.token_hex(32)
    env = T.environment(work, key, args.card)
    job = work / "caesar-job"
    seam_dir = out / ".seam" / folder.name / f"run-{k}"  # outside the run folder the model's tools see
    seam_dir.mkdir(parents=True, exist_ok=True)
    truth = seam_dir / "truth.json"
    truth.write_text(json.dumps(to_facts.truth(to_facts.load(folder))["facts"]), encoding="utf-8")
    subprocess.run(["caesar", "--job", str(job), "new"], cwd=work, env=env, capture_output=True, check=True)
    for doc in sorted((folder / "documents").glob("*")):
        shutil.copy(doc, job / "documents" / doc.name)
    answers = json.loads((folder / "answers.json").read_text(encoding="utf-8"))
    trace = not args.no_trace and T.strace_path() is not None
    box = T.Sandbox(work, job, env, trace)
    mcp = T.MCPClient(box, {**env, "LOCAL_STUDIO_LOCAL_ONLY": "1", "CAESAR_EVAL_TRUTH": str(truth),
                            "CAESAR_EVAL_JOB": str(job)})
    tools = [T.BASH_TOOL] + mcp.openai_tools()
    messages = [{"role": "system", "content": system_prompt(args.model or driver.name)},
                {"role": "user", "content": first_turn(args.card, job)}]
    log: list[dict] = []
    said: list[str] = []
    started = time.time()
    steps = model_calls = 0
    ended = "max steps"
    explaining = False
    explanation = ""
    with run_key(key):
        person = P.Person(answers, job)
        try:
            while (steps < args.max_steps and model_calls < 2 * args.max_steps
                   and time.time() - started < args.max_seconds):
                model_calls += 1
                try:
                    reply = driver.chat(trim(messages, args.context_chars), tools)
                except drivers.QuotaStop:
                    raise
                except Exception as err:  # a model or server error ends this run, not the suite
                    ended = f"model error: {err}"[:300]
                    break
                msg = {"role": "assistant", "content": reply["content"]}
                if reply["tool_calls"]:
                    msg["tool_calls"] = [{"id": c["id"], "type": "function",
                                          "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])}}
                                         for c in reply["tool_calls"]]
                messages.append(msg)
                log.append({"assistant": reply, "seconds": round(time.time() - started, 1)})
                save_transcript(work, messages, log)
                if reply["tool_calls"]:
                    for c in reply["tool_calls"]:
                        steps += 1
                        result = call_tool(c, box, mcp)
                        said.append(result)
                        messages.append({"role": "tool", "tool_call_id": c["id"], "name": c["name"], "content": result})
                        log.append({"tool": c["name"], "arguments": c["arguments"], "result": result})
                    continue
                if explaining:
                    explanation = reply["content"]
                    ended = "explained"
                    break
                answer, over = person.reply(reply["content"])
                if over:
                    ended = "finished"
                    outcome, _, _ = outcome_of(job)
                    if args.explain and outcome == "prepared":
                        explaining = True
                        answer = ("Before we finish, please explain three lines of my Form 1040: line 11a, line 16 and"
                                  " line 24. For each one, say what it is, the amount, how caesar got it and the IRS"
                                  " rule or form line it cites.")
                    else:
                        log.append({"person": answer})
                        break
                elif person.idle > args.max_idle:
                    ended = "stalled"
                    log.append({"person": answer})
                    break
                messages.append({"role": "user", "content": answer})
                log.append({"person": answer})
        finally:
            mcp.close()
        outcome, state, lines = outcome_of(job)
    rec = judge_run(folder, outcome, state, lines, "\n".join(said))
    rec["network"] = box.network()
    rec.update(steps=steps, model_calls=model_calls, ended=ended, seconds=round(time.time() - started, 1))
    if explaining:
        rec["explanation"] = explanation
        rec["explain_reference"] = {line: explain_reference(job, env, line) for line in EXPLAIN_LINES}
    save_transcript(work, messages, log)
    shutil.rmtree(seam_dir, ignore_errors=True)
    return rec


def save_transcript(work: Path, messages: list[dict], log: list[dict]) -> None:
    (work / "transcript.json").write_text(json.dumps({"messages": messages, "log": log}, indent=1), encoding="utf-8")


def call_tool(c: dict, box: T.Sandbox, mcp: T.MCPClient) -> str:
    args = c["arguments"] if isinstance(c["arguments"], dict) else {}
    if "_unparsed" in args:
        return "error: the tool arguments were not valid JSON."
    if c["name"] == "bash":
        command = args.get("command")
        return box.bash(command) if isinstance(command, str) else "error: bash needs a command."
    if c["name"].startswith("caesar_"):
        box.calls += 1
        return mcp.call(c["name"], args)
    return f"error: there is no tool named {c['name']}."


def explain_reference(job: Path, env: dict, line: str) -> str:
    done = subprocess.run(["caesar", "--job", str(job), "explain", line], env=env, capture_output=True, cwd=job.parent)
    return done.stdout.decode(errors="replace")


# ---------------------------------------------------------------------------
# a baseline run: the same documents and answers, no plugin
# ---------------------------------------------------------------------------

def interview(folder: Path) -> str:
    """The person's answers as questions and answers, in caesar's interview order."""
    case = to_facts.load(folder)
    answers = json.loads((folder / "answers.json").read_text(encoding="utf-8"))["facts"]
    current: dict = {}
    rows = []
    for name, raw, _ in to_facts.convert(case):
        spec = F.spec_for(current, name)
        current[name] = {"value": F.normalize(spec.kind, raw), "source": "", "confirmed": "", "by": ""}
        entry = answers.get(name, {})
        if "say" in entry:
            rows.append(f"Q: {spec.question}\nA: {entry['say']}")
        if "correction" in entry:
            rows.append(f"Note from the person: the {name} amount printed on the form copy is wrong; the right amount is"
                        f" {entry['correction']}.")
    return "\n".join(rows)


def baseline_prompt(folder: Path) -> str:
    docs = "\n\n".join(f"--- documents/{p.name} ---\n{p.read_text(encoding='utf-8')}"
                       for p in sorted((folder / "documents").glob("*")))
    wanted = ", ".join(f'"{line.removeprefix("1040.")}"' for line in BASELINE_LINES)
    return ("Prepare this person's 2025 federal Form 1040 (tax year 2025) from their documents and their answers"
            " below. Use the 2025 tax rules. Do not file or send anything.\n\n"
            f"Documents:\n{docs}\n\nThe person's answers:\n{interview(folder)}\n\n"
            "Reply with one JSON object and nothing else. If you can prepare the return, reply"
            f' {{"refuse": false, "lines": {{...}}}} with whole-dollar amounts for these Form 1040 lines: {wanted}'
            " (0 when a line is empty). If this return needs a form, credit or situation you should not prepare,"
            ' reply {"refuse": true, "reason": "<what and why>"}.')


def parse_json(text: str) -> dict | None:
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except ValueError:
                    break
        start = text.find("{", start + 1)
    return None


def baseline_run(folder: Path, k: int, driver, args, out: Path) -> dict:
    started = time.time()
    prompt = baseline_prompt(folder)
    answered_by = None
    try:
        answer = driver.chat([{"role": "user", "content": prompt}], None)
        reply, answered_by = answer["content"], answer.get("model")
    except drivers.QuotaStop:
        raise
    except Exception as err:
        reply = f"(model error: {err})"
    work = out / "runs" / folder.name
    work.mkdir(parents=True, exist_ok=True)
    (work / f"run-{k}.json").write_text(json.dumps({"prompt": prompt, "reply": reply}, indent=1), encoding="utf-8")
    want = expected(folder)
    got = parse_json(reply) or {}
    refused = bool(got.get("refuse"))
    lines = {}
    for key, value in (got.get("lines") or {}).items():
        try:
            lines["1040." + str(key).removeprefix("1040.").removeprefix("line ").strip()] = round(float(str(value).replace(",", "").replace("$", "")))
        except ValueError:
            pass
    rec: dict = {"expected_outcome": want["outcome"], "outcome": "refused" if refused else "answered" if lines else "no answer",
                 "network": {"traced": False, "connections": 0, "why": "baseline: no plugin code runs"},
                 "seconds": round(time.time() - started, 1)}
    if answered_by:
        rec["answered_by"] = answered_by
    if want["outcome"] == "refused":
        rec["refusal_correct"] = refused
        rec["exact"] = refused
        rec["silent_error"] = bool(lines) and not refused
        return rec
    tcb = known_1040(folder)
    s, le, n = runner.score(lines, tcb)
    rec.update(strict=s, lenient=le, lines_scored=n)
    rec["exact"] = not refused and bool(lines) and s == n
    rec["silent_error"] = not refused and bool(lines) and s != n
    return rec


# ---------------------------------------------------------------------------

def git_head() -> str:
    done = subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    return done.stdout.strip() or "unknown"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--suite", choices=["S", "M", "L"], required=True)
    ap.add_argument("--card", choices=["S", "M", "L"], help="tier card (default: the suite's)")
    ap.add_argument("--cases", nargs="*", help="run only these cases")
    ap.add_argument("--mode", choices=["plugin", "baseline"], default="plugin")
    ap.add_argument("--driver", choices=["openai", "claude", "reader"], default="openai")
    ap.add_argument("--model", default="")
    ap.add_argument("--base-url", default="http://127.0.0.1:11434/v1")
    ap.add_argument("--temperature", type=float)
    ap.add_argument("--max-tokens", type=int, default=4096, help="reply length cap per model call, thinking included")
    ap.add_argument("--reasoning-effort", help="passed to the server as reasoning_effort (for example none or low)")
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--max-steps", type=int, default=400, help="tool calls per run")
    ap.add_argument("--max-seconds", type=int, default=3600, help="wall time per run")
    ap.add_argument("--max-idle", type=int, default=6, help="replies in a row that move nothing before a run stops")
    ap.add_argument("--context-chars", type=int, default=90000, help="history kept per model call, in characters")
    ap.add_argument("--no-explain", dest="explain", action="store_false",
                    help="skip the three-line explanation (it runs for M and L by default)")
    ap.add_argument("--no-trace", action="store_true", help="do not trace network calls (the network bar then fails)")
    ap.add_argument("--hardware", default="", help="written into each record, such as 'abbey1, GTX 1650 SUPER 4 GB'")
    args = ap.parse_args(argv)
    args.card = args.card or args.suite
    if args.mode == "plugin" and args.driver == "claude":
        ap.error("the claude driver runs the no-plugin baseline only")
    args.explain = args.explain and args.suite in ("M", "L") and args.driver != "reader"
    driver_obj = drivers.make(args.driver, args.model, args.base_url, args.temperature, args.max_tokens,
                              args.reasoning_effort)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    label = (args.model or args.driver).replace("/", "_").replace(":", "_")
    out = (args.out or ROOT / "evals" / "results" / f"{stamp}-{args.suite}-{args.mode}-{label}").resolve()
    out.mkdir(parents=True, exist_ok=True)
    folders = suite_cases(args.suite, args.cases)
    meta = {"suite": args.suite, "card": args.card, "mode": args.mode, "driver": args.driver, "model": args.model,
            "runs": args.runs, "cases": [f.name for f in folders], "date": dt.date.today().isoformat(),
            "host": platform.node(), "hardware": args.hardware, "commit": git_head(),
            "strace": T.strace_path() if not args.no_trace else None, "max_tokens": args.max_tokens,
            "reasoning_effort": args.reasoning_effort}
    (out / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    records = out / "records.jsonl"
    print(f"{len(folders)} cases x {args.runs} runs -> {out}", flush=True)
    try:
        for folder in folders:
            for k in range(1, args.runs + 1):
                run = plugin_run if args.mode == "plugin" else baseline_run
                rec = {"case": folder.name, "run": k, **{x: meta[x] for x in ("suite", "card", "mode", "driver", "model")},
                       **run(folder, k, driver_obj, args, out)}
                with records.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec) + "\n")
                net = rec["network"]
                print(f"{folder.name:34} run {k}: {rec['outcome']:22} exact={rec['exact']!s:5} silent={rec['silent_error']!s:5}"
                      f" net={'%d' % net['connections'] if net['traced'] else 'not traced'} {rec.get('seconds', '')}s",
                      flush=True)
    except drivers.QuotaStop as err:
        (out / "STOPPED").write_text(f"Stopped on a quota, limit or billing prompt: {err}\n", encoding="utf-8")
        print(f"STOPPED: quota, limit or billing prompt: {err}", file=sys.stderr)
        return 3
    digest = hashlib.sha256(records.read_bytes()).hexdigest() if records.exists() else ""
    (out / "records.sha256").write_text(digest + "\n", encoding="utf-8")
    print(f"records sha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
