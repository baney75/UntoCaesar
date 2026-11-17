"""caesar: the UntoCaesar command line.

Every message starts with the test build banner and ends with one NEXT: line naming the one
command to run next. caesar status repeats it. NEXT: none means stop.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import sys
from pathlib import Path

from . import __version__
from . import checks as C
from . import confirm as K
from . import engine as E
from . import facts as F
from . import worksheet as W
from . import yeardata

BANNER = "Test build: synthetic cases only, not for real records."
DEFAULT_JOB = "caesar-job"
COUNT_LINES = {"8812.4", "8812.6"}
SAFETY = "caesar never files, signs, sends or pays. The person does those steps, outside caesar."


class Stop(Exception):
    """End the command with a message and an exit code."""

    def __init__(self, lines: list[str], code: int = 2):
        super().__init__("\n".join(lines))
        self.lines = lines
        self.code = code


# ---------------------------------------------------------------------------
# The job folder
# ---------------------------------------------------------------------------

class Job:
    def __init__(self, path: Path):
        self.path = path
        self.facts_path = path / "facts.toml"
        self.state_path = path / "state.json"
        self.return_path = path / "return.json"
        self.worksheet_path = path / "worksheet.html"

    def exists(self) -> bool:
        return self.facts_path.exists()

    def state(self) -> dict:
        if not self.state_path.exists():
            return {}
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def save_state(self, state: dict) -> None:
        write(self.state_path, json.dumps(state, indent=2, sort_keys=True) + "\n")

    def year(self) -> yeardata.YearData:
        return yeardata.load(int(self.state().get("year", 2025)))

    def facts(self) -> dict:
        return F.load(self.facts_path)

    def save_facts(self, facts: dict) -> None:
        F.save(self.facts_path, facts, self.year().year)

    def ret(self) -> dict | None:
        if not self.return_path.exists():
            return None
        return json.loads(self.return_path.read_text(encoding="utf-8"))


def write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def content_hash(facts: dict) -> str:
    """Values and sources: what the math and the person's confirmation depend on."""
    data = {k: [v["value"], v["source"]] for k, v in sorted(facts.items())}
    return hashlib.sha256(json.dumps(data).encode()).hexdigest()


def full_hash(facts: dict) -> str:
    data = {k: [v["value"], v["source"], v["confirmed"], v["by"]] for k, v in sorted(facts.items())}
    return hashlib.sha256(json.dumps(data).encode()).hexdigest()


# ---------------------------------------------------------------------------
# NEXT
# ---------------------------------------------------------------------------

def prog(job: Job) -> str:
    base = os.environ.get("CAESAR_CMD")
    if not base:
        if shutil.which("caesar"):
            base = "caesar"
        else:
            base = ("python" if os.name == "nt" else "python3") + " -m caesar"
    if job.path.resolve() != (Path.cwd() / DEFAULT_JOB).resolve():
        base += " --job " + quote_arg(str(job.path))
    return base


def quote_arg(text: str) -> str:
    if os.name == "nt":
        return f'"{text}"' if any(c in text for c in ' "&|<>^') else text
    return shlex.quote(text)


def set_template(spec: F.Spec) -> str:
    hint = {"status": "<single, mfj, mfs, hoh or qss>", "yesno": "<yes or no>", "owner": "<taxpayer or spouse>",
            "count": "<number>", "codes": "<codes or none>", "money": "<amount>", "number": "<number>",
            "text": '"<name>"'}[spec.kind]
    source = "<document and box, or: answer>" if not spec.name.startswith(("screen.", "filing_status")) else "answer"
    return f'set {spec.name} {hint} --source "{source}"'


def next_step(job: Job) -> str | None:
    """The one command to run next, without the program name, or None to stop."""
    if not job.exists():
        return "new"
    facts = job.facts()
    if C.fact_refusals(facts):
        return None
    if F.missing(facts):
        return "ask"
    state = job.state()
    ch = content_hash(facts)
    if any(e["confirmed"] == "" for e in facts.values()) and state.get("confirm_hash") != ch:
        return "confirm"
    if rejected(facts):
        # A value the person rejected: show the failing check, then ask for the right value.
        if state.get("check", {}).get("hash") != full_hash(facts):
            return "check"
        return set_template(F.spec_for(facts, rejected(facts)[0]))
    ret = job.ret()
    if ret is None or ret.get("content_hash") != ch:
        return "compute"
    fh = full_hash(facts)
    check = state.get("check", {})
    if check.get("hash") != fh:
        return "check"
    if check.get("refused"):
        return None
    if not check.get("passed"):
        fact = check.get("fix", "")
        spec = F.spec_for(facts, fact) if fact else None
        return set_template(spec) if spec else "facts"
    if state.get("worksheet_hash") != fh:
        return "worksheet"
    if state.get("done_hash") != fh:
        return "done"
    return None


def emit(job: Job, lines: list[str], step: str | None = "auto") -> None:
    if step == "auto":
        step = next_step(job)
    print(BANNER)
    for line in lines:
        print(line)
    print(f"NEXT: {prog(job)} {step}" if step else "NEXT: none")


def return_state(facts: dict, check: dict | None) -> str:
    if check and check.get("refused"):
        return "stopped: outside v0"
    if check and not check.get("passed"):
        return "check failed"
    confirmed = facts and all(e["confirmed"] == "yes" for e in facts.values())
    if check and check.get("passed") and confirmed:
        if all(e["by"] == K.SCRIPTED for e in facts.values()):
            return "prepared for the eval (every fact confirmed by the scripted test person, not a real person)"
        return "prepared"
    return "computed, not confirmed"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_new(job: Job, args) -> int:
    if job.exists():
        emit(job, [f"A job already exists at {job.path}. caesar keeps working in it."])
        return 0
    year = yeardata.load(args.year)
    job.path.mkdir(parents=True, exist_ok=True)
    (job.path / "documents").mkdir(exist_ok=True)
    job.save_state({"year": year.year})
    job.save_facts({})
    emit(job, [f"Started a tax year {year.year} job at {job.path}.",
               "Put the person's documents in its documents folder. They never leave this computer through caesar.",
               SAFETY])
    return 0


def cmd_status(job: Job, args) -> int:
    if not job.exists():
        emit(job, [f"caesar {__version__}. No job at {job.path} yet."])
        return 0
    facts = job.facts()
    refusals = C.fact_refusals(facts)
    missing = F.missing(facts)
    lines = [f"caesar {__version__}. Job {job.path}, tax year {job.year().year}.",
             f"Facts answered: {len(facts)}. Still to ask: {len(missing)} (more may follow from the answers)."]
    if refusals:
        lines.append("Stopped: this return is outside what caesar v0 can prepare.")
        lines += [f"- {f.message}" for f in refusals]
        lines.append("If an answer was wrong, set it again with caesar set; otherwise the person needs another way to file.")
    else:
        unconfirmed = sum(1 for e in facts.values() if e["confirmed"] != "yes")
        lines.append(f"Not confirmed by the person: {unconfirmed}.")
        lines.append(f"State: {return_state(facts, job.state().get('check') if job.ret() else None)}.")
        if next_step(job) is None:
            lines.append(SAFETY)
    emit(job, lines)
    return 0


def cmd_ask(job: Job, args) -> int:
    facts = need_job(job)
    if C.fact_refusals(facts):
        return cmd_status(job, args)
    missing = F.missing(facts)
    if not missing:
        emit(job, ["Every question is answered."])
        return 0
    spec = missing[0]
    lines = [f"Ask the person: {spec.question}",
             f"Then record the answer with caesar set {spec.name}. Put where it came from in --source: the document and box"
             " (for example \"W-2 from Acme, box 1\"), or answer when the person said it."]
    emit(job, lines, set_template(spec))
    return 0


def cmd_set(job: Job, args) -> int:
    facts = need_job(job)
    spec = F.spec_for(facts, args.fact)
    if spec is None:
        raise Stop([f"caesar v0 has no fact named {args.fact} here. It knows only the facts its interview asks for;"
                    " run caesar ask to see the next one. A fact for a later item (such as w2.2) appears once its count is set."])
    try:
        value = F.normalize(spec.kind, args.value)
        source = F.normalize("text", args.source)
    except ValueError as err:
        raise Stop([f"{args.fact}: {err}."]) from None
    old = facts.get(args.fact)
    if old and old["value"] == value and old["source"] == source:
        emit(job, [f"{args.fact} is already {value}."])
        return 0
    facts[args.fact] = {"value": value, "source": source, "confirmed": "", "by": ""}
    dropped = F.unknown(facts)
    for name in dropped:
        del facts[name]
    job.save_facts(facts)
    lines = [f"Set {args.fact} = {value} (source: {source}). It is not confirmed by the person yet."]
    if dropped:
        lines.append(f"Removed {len(dropped)} facts the interview no longer asks for: {', '.join(dropped)}.")
    what = F.refusal(spec, value)
    if what:
        lines += [f"Stop: caesar v0 does not handle {what}. This return is outside what caesar can prepare.",
                  "Tell the person in plain words. If the answer was wrong, set it again."]
        emit(job, lines)
        return 1
    emit(job, lines)
    return 0


def cmd_confirm(job: Job, args) -> int:
    facts = need_job(job)
    if C.fact_refusals(facts):
        return cmd_status(job, args)
    names = [args.fact] if args.fact else [n for n in sorted(facts, key=F.sort_key) if facts[n]["confirmed"] == ""]
    for name in names:
        if name not in facts:
            raise Stop([f"There is no fact named {name} to confirm."])
    person = K.channel(facts)
    answered = {"yes": 0, "no": 0}
    if isinstance(person, K.NoPersonChannel):
        lines = ["caesar shows each fact to the person and records only the person's answer.",
                 "This build has no person channel: a plugin command cannot open Local Studio's ask-user dialog yet, and the"
                 " core does not yet guarantee that the person answers it (local-studio#15). So caesar records no"
                 " confirmation, and the best state this return can reach is: computed, not confirmed.",
                 f"Facts not confirmed: {len(names)}. The person can review them with caesar facts."]
    else:
        for name in names:
            answer = person.ask(name, K.question(name, facts[name]))
            if answer in ("yes", "no"):
                facts[name]["confirmed"] = answer
                facts[name]["by"] = person.name
                answered[answer] += 1
        job.save_facts(facts)
        lines = [f"Asked the {person.name} about {len(names)} facts: {answered['yes']} confirmed, {answered['no']} rejected."]
        rejected = [n for n in names if facts[n]["confirmed"] == "no"]
        if rejected:
            lines.append("Rejected (read the document again and set the right value): " + ", ".join(rejected) + ".")
    state = job.state()
    state["confirm_hash"] = content_hash(facts)
    job.save_state(state)
    emit(job, lines)
    return 0


def cmd_facts(job: Job, args) -> int:
    facts = need_job(job)
    lines = [f"{len(facts)} facts in {job.facts_path}:"]
    for name in sorted(facts, key=F.sort_key):
        e = facts[name]
        state = {"yes": "confirmed", "no": "REJECTED by the person"}.get(e["confirmed"], "not confirmed")
        lines.append(f"- {name} = {e['value']} (source: {e['source']}; {state})")
    lines.append("To change a fact: caesar set <fact> <value> --source \"<where it came from>\".")
    emit(job, lines)
    return 0


def build_return(job: Job, facts: dict) -> dict:
    year = job.year()
    ret = E.compute(facts, year)
    out = []
    for line_id, value in ret.lines.items():
        info = year.line_info(line_id)
        inputs = []
        for name in ret.inputs[line_id]:
            if name in facts:
                inputs.append({"name": name, "value": facts[name]["value"], "source": facts[name]["source"]})
            elif name in ret.lines:
                inputs.append({"name": name, "value": ret.lines[name]})
            else:
                inputs.append({"name": name, "value": F.value(facts, name) or "not answered"})
        out.append({"id": line_id, "label": info["label"], "value": value, "money": line_id not in COUNT_LINES,
                    "rule": info["rule"], "citation": info["citation"], "inputs": inputs})
    return {"test_build": BANNER, "year": year.year, "caesar": __version__, "content_hash": content_hash(facts),
            "state": "computed, not confirmed", "lines": out, "_engine": ret}


def save_return(job: Job, doc: dict) -> None:
    doc = {k: v for k, v in doc.items() if k != "_engine"}
    write(job.return_path, json.dumps(doc, indent=2) + "\n")


def cmd_compute(job: Job, args) -> int:
    facts = need_job(job)
    if C.fact_refusals(facts):
        return cmd_status(job, args)
    if F.missing(facts):
        emit(job, ["Some questions are not answered yet, so caesar cannot compute."])
        return 1
    doc = build_return(job, facts)
    ret = doc["_engine"]
    save_return(job, doc)
    lines = [f"Computed {len(ret.lines)} lines into {job.return_path}.",
             f"Adjusted gross income (line 11b): {W.dollars(ret.get('1040.11b'))}.",
             f"Taxable income (line 15): {W.dollars(ret.get('1040.15'))}.",
             f"Total tax (line 24): {W.dollars(ret.get('1040.24'))}.",
             f"Total payments (line 33): {W.dollars(ret.get('1040.33'))}."]
    if ret.get("1040.34"):
        lines.append(f"Refund (line 35a): {W.dollars(ret.get('1040.35a'))}.")
    else:
        lines.append(f"Amount owed (line 37): {W.dollars(ret.get('1040.37'))}.")
    lines.append("These are not final until caesar check passes.")
    emit(job, lines)
    return 0


def cmd_check(job: Job, args) -> int:
    facts = need_job(job)
    year = job.year()
    ret = None
    if not C.fact_refusals(facts) and not F.missing(facts):
        doc = build_return(job, facts)
        ret = doc["_engine"]
    report = C.run(facts, ret, year)
    fix = next((f.fact for f in report.failures if f.fact), "")
    check = {"hash": full_hash(facts), "passed": report.passed, "refused": bool(report.refusals), "fix": fix,
             "refusals": [vars(f) for f in report.refusals], "failures": [vars(f) for f in report.failures],
             "unconfirmed": report.unconfirmed}
    state = job.state()
    state["check"] = check
    job.save_state(state)
    if ret is not None:
        doc["check"] = check
        doc["state"] = return_state(facts, check)
        save_return(job, doc)
    lines = []
    if report.refusals:
        lines.append("Stop: this return is outside what caesar v0 can prepare.")
        for f in report.refusals:
            lines.append(f"- {f.message}")
            if f.citation:
                lines.append(f"  Rule: {f.citation['source']}, {f.citation['at']} ({f.citation['url']})")
        lines.append("Tell the person in plain words. caesar cannot finish this return.")
    if report.failures:
        lines.append(f"{len(report.failures)} check{'s' if len(report.failures) != 1 else ''} failed:")
        lines += [f"- {f.message}" for f in report.failures]
    if report.unconfirmed:
        lines.append(f"Not confirmed by the person: {len(report.unconfirmed)} facts.")
    if report.passed:
        lines.append("Every check passed.")
        lines.append(f"State: {return_state(facts, check)}.")
    emit(job, lines)
    return 0 if report.passed else 1


def cmd_worksheet(job: Job, args) -> int:
    facts = need_job(job)
    doc = job.ret()
    if doc is None or doc.get("content_hash") != content_hash(facts):
        emit(job, ["The return is out of date. Compute it first."])
        return 1
    state = job.state()
    doc["state"] = return_state(facts, state.get("check"))
    write(job.worksheet_path, W.render(doc, facts, job.year(), BANNER))
    state["worksheet_hash"] = full_hash(facts)
    job.save_state(state)
    emit(job, [f"Wrote {job.worksheet_path}. Open it in a browser to read every line, its rule, its source and its inputs."])
    return 0


def cmd_explain(job: Job, args) -> int:
    facts = need_job(job)
    doc = job.ret()
    if doc is None:
        emit(job, ["There is no computed return yet."])
        return 1
    wanted = args.line if "." in args.line else f"1040.{args.line}"
    line = next((x for x in doc["lines"] if x["id"] == wanted), None)
    if line is None:
        raise Stop([f"The return has no line {wanted}. Lines look like 1040.16, schc-taxpayer.31 or 8812.14."])
    value = W.dollars(line["value"]) if line["money"] else str(line["value"])
    cite = line["citation"]
    lines = [f"{line['id']}, {line['label']}: {value}", f"Rule: {line['rule']}",
             f"Source: {cite['source']} ({cite['revision']}), {cite['at']}. {cite['url']}"]
    if line["inputs"]:
        lines.append("Inputs:")
        for item in line["inputs"]:
            extra = f" (source: {item['source']})" if item.get("source") else ""
            lines.append(f"- {item['name']} = {item['value']}{extra}")
    if doc.get("content_hash") != content_hash(facts):
        lines.append("Facts changed after this was computed, so this line may be out of date.")
    emit(job, lines)
    return 0


def cmd_done(job: Job, args) -> int:
    facts = need_job(job)
    state = job.state()
    doc = job.ret()
    fh = full_hash(facts)
    if doc is None or state.get("check", {}).get("hash") != fh or state.get("worksheet_hash") != fh:
        emit(job, ["Not finished yet."])
        return 1
    final = return_state(facts, state.get("check"))
    state["done_hash"] = fh
    state["final"] = final
    job.save_state(state)
    doc["state"] = final
    save_return(job, doc)
    lines = [f"State: {final}."]
    if final == "computed, not confirmed":
        lines.append("No fact is confirmed by the person, so this return is not prepared. The person must check every fact"
                     " against their documents before relying on any line.")
    lines += [f"The return is in {job.return_path} and the worksheet in {job.worksheet_path}.", SAFETY]
    emit(job, lines)
    return 0


def rejected(facts: dict) -> list[str]:
    return [n for n in sorted(facts, key=F.sort_key) if facts[n]["confirmed"] == "no"]


def need_job(job: Job) -> dict:
    if not job.exists():
        raise Stop([f"There is no job at {job.path} yet."])
    return job.facts()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="caesar", description="UntoCaesar: a federal Form 1040 engine for tax year 2025. " + BANNER)
    p.add_argument("--job", default=os.environ.get("CAESAR_JOB", DEFAULT_JOB), help="job folder (default ./caesar-job)")
    p.add_argument("--version", action="version", version=f"caesar {__version__}")
    sub = p.add_subparsers(dest="command")
    sub.add_parser("status", help="where the return stands and what to do next")
    new = sub.add_parser("new", help="start a job folder")
    new.add_argument("--year", type=int, default=2025)
    sub.add_parser("ask", help="the next interview question")
    s = sub.add_parser("set", help="record a fact")
    s.add_argument("fact")
    s.add_argument("value")
    s.add_argument("--source", required=True, help="the document and box, or answer")
    c = sub.add_parser("confirm", help="ask the person to confirm facts")
    c.add_argument("fact", nargs="?")
    sub.add_parser("facts", help="list every fact")
    sub.add_parser("compute", help="compute the return")
    sub.add_parser("check", help="run the checks and refusals")
    e = sub.add_parser("explain", help="show one line's rule, inputs and source")
    e.add_argument("line")
    sub.add_parser("worksheet", help="write worksheet.html")
    sub.add_parser("done", help="finish and show the final state")
    return p


COMMANDS = {"new": cmd_new, "status": cmd_status, "ask": cmd_ask, "set": cmd_set, "confirm": cmd_confirm,
            "facts": cmd_facts, "compute": cmd_compute, "check": cmd_check, "explain": cmd_explain,
            "worksheet": cmd_worksheet, "done": cmd_done}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args_for_set = argv[argv.index("set") + 1:] if "set" in argv else []
    if any(a.startswith("--confirm") or a.lower().split("=", 1)[0] in ("confirm", "confirmed")
           or a.lower().endswith(".confirmed") for a in args_for_set):
        print(BANNER)
        print("caesar set cannot mark a fact confirmed. Only the person can, through caesar confirm.")
        print("NEXT: none")
        return 2
    args = parser().parse_args(argv)
    job = Job(Path(args.job))
    command = args.command or "status"
    try:
        return COMMANDS[command](job, args)
    except Stop as stop:
        emit(job, stop.lines)
        return stop.code
    except (OSError, ValueError) as err:
        emit(job, [f"caesar could not finish: {err}"])
        return 2
