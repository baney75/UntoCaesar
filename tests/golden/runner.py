"""Run a golden case through caesar the way the skill does, and score it.

The runner follows caesar's NEXT: lines the way a model does. It runs each one through bash -c,
and when NEXT is a caesar set template it fills each <...> with the case's value and source
(tests/golden/to_facts.py) as they are, with no escaping, so the shell path is what is tested. It
stops at NEXT: none or at a set for a fact already answered (a fix only a person can make). The
scripted person answers caesar confirm from the case's true values. Scoring follows TaxCalcBench: each Form 1040 line
in output.xml is scored strict (exact) and lenient (within $5).

Usage: python3 tests/golden/runner.py [case folder ...]   prints a score table.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import to_facts  # noqa: E402

from caesar import cli  # noqa: E402

CASES = Path(__file__).resolve().parent / "2025"
LENIENT = 5
XPATH = {"1040.1a": "WagesAmt", "1040.9": "TotalIncomeAmt", "1040.10": "TotalAdjustmentsAmt",
         "1040.11a": "AdjustedGrossIncomeAmt", "1040.12e": "TotalItemizedOrStandardDedAmt", "1040.15": "TaxableIncomeAmt",
         "1040.16": "TaxAmt", "1040.19": "CTCODCAmt", "1040.24": "TotalTaxAmt", "1040.25d": "WithholdingTaxAmt",
         "1040.26": "EstimatedTaxPaymentsAmt", "1040.27a": "EarnedIncomeCreditAmt", "1040.28": "AdditionalChildTaxCreditAmt",
         "1040.29": "RefundableAmerOppCreditAmt", "1040.32": "RefundableCreditsAmt", "1040.33": "TotalPaymentsAmt",
         "1040.34": "OverpaidAmt", "1040.35a": "RefundAmt", "1040.37": "OwedAmt"}


def case_folders() -> list[Path]:
    return sorted(p for p in CASES.iterdir() if (p / "input.json").exists())


BASH = shutil.which("bash")
# In the bash that runs a NEXT line, caesar is a function that records the argv and stdin bash
# hands it. Every expansion, quote and heredoc is bash's own; the runner then calls cli.main with
# exactly those arguments and that input, in this process, which keeps the suite fast.
SHIM = 'caesar() { printf "%s\\0" "$@" > "$CAESAR_ARGV"; IFS= read -r -d "" input; printf "%s" "$input" > "$CAESAR_STDIN"; }\n'
HOLE = re.compile(r"<[a-z][^<>\n]*>")


def shell(job: Path, command: str) -> tuple[int, str]:
    """Run one caesar command line through bash -c, as a model's bash tool does."""
    assert BASH, "the golden runner needs bash on PATH"
    argv_file, stdin_file = job.parent / "argv.bin", job.parent / "stdin.bin"
    for f in (argv_file, stdin_file):
        f.unlink(missing_ok=True)
    env = dict(os.environ, CAESAR_ARGV=str(argv_file), CAESAR_STDIN=str(stdin_file))
    done = subprocess.run([BASH, "-c", SHIM + command], env=env, stdin=subprocess.DEVNULL, capture_output=True)
    if done.returncode != 0 or not argv_file.exists():
        return 2, f"bash failed ({done.returncode}): {done.stderr.decode(errors='replace')}"
    argv = [a.decode("utf-8") for a in argv_file.read_bytes().split(b"\0")[:-1]]
    data = stdin_file.read_bytes() if stdin_file.exists() else b""
    buf = io.StringIO()
    saved = sys.stdin
    sys.stdin = io.TextIOWrapper(io.BytesIO(data), encoding="utf-8")
    try:
        with contextlib.redirect_stdout(buf):
            code = cli.main(argv)
    finally:
        sys.stdin = saved
    return code, buf.getvalue()


def caesar(job: Path, *args: str) -> tuple[int, str]:
    return shell(job, " ".join(shlex.quote(a) for a in ("caesar", "--job", str(job), *args)))


def next_command(output: str, job: Path) -> str | None:
    """The NEXT: command after the program and job, which for a set may run on to a heredoc."""
    head, sep, step = output.rpartition("\nNEXT: ")
    assert sep, output
    step = step.rstrip("\n")
    if step == "none":
        return None
    prefix = f"caesar --job {shlex.quote(str(job))} "
    assert step.startswith(prefix), step
    return step[len(prefix):]


def fill(template: str, value: str, source: str) -> str:
    """Fill a set template's <...> holes in order, value then source, with the text as it is."""
    holes = HOLE.findall(template)
    assert 1 <= len(holes) <= 2, template
    if len(holes) == 1:
        assert source == "answer", (template, source)  # the template's own fixed source
    texts = iter([value, source])
    return HOLE.sub(lambda m: next(texts), template)


def run(folder: Path, scripted: bool = True, workdir: Path | None = None) -> dict:
    case = to_facts.load(folder)
    work = Path(workdir or tempfile.mkdtemp(prefix="caesar-golden-")).resolve()
    work.mkdir(parents=True, exist_ok=True)
    job = work / "job"
    env = {"CAESAR_CMD": "caesar"}
    if scripted:
        truth = work / "person.json"
        truth.write_text(json.dumps(to_facts.truth(case)), encoding="utf-8")
        env["CAESAR_SCRIPTED_PERSON"] = str(truth)
    saved = {k: os.environ.get(k) for k in ("CAESAR_CMD", "CAESAR_SCRIPTED_PERSON")}
    os.environ.pop("CAESAR_SCRIPTED_PERSON", None)
    os.environ.update(env)
    given = to_facts.all_facts(case)
    transcript = []
    try:
        code, out = caesar(job, "new")
        transcript.append(("new", code, out))
        refused_at = ""
        for _ in range(1000):
            step = next_command(out, job)
            if step is None:
                break
            words = step.split()
            if words[0] == "set":
                name = words[1]
                answered = to_facts.F.value(cli.Job(job).facts(), name) is not None
                if answered or name not in given:
                    break
                step = fill(step, *given[name])
                label = f"set {name}"
            else:
                label = step
            code, out = shell(job, f"caesar --job {shlex.quote(str(job))} {step}")
            transcript.append((label, code, out))
            # A model follows NEXT, so a set that ends in NEXT: none stops the interview.
            if words[0] == "set" and (code == 1 or out.strip().endswith("NEXT: none")):
                refused_at = "set"
                break
        else:
            raise AssertionError("caesar never said NEXT: none")
    finally:
        for k, val in saved.items():
            if val is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = val

    state = json.loads((job / "state.json").read_text(encoding="utf-8"))
    ret = json.loads((job / "return.json").read_text(encoding="utf-8")) if (job / "return.json").exists() else None
    check = state.get("check", {})
    if refused_at or check.get("refused"):
        outcome = "refused"
        refused_at = refused_at or "check"
    elif check and not check.get("passed"):
        outcome = "check_failed"
    elif state.get("final", "").startswith("prepared"):
        outcome = "prepared"
    elif state.get("final"):
        outcome = "computed_not_confirmed"
    else:
        outcome = "unfinished"
    return {"outcome": outcome, "at": refused_at, "job": job, "transcript": transcript, "state": state,
            "lines": {x["id"]: x["value"] for x in ret["lines"]} if ret else {}, "return": ret,
            "output": "\n".join(out for _, _, out in transcript)}


def expected_xml(folder: Path) -> dict[str, int]:
    tree = ET.parse(folder / "output.xml")
    found = {}
    for line, tag in XPATH.items():
        node = tree.find(f"./ReturnData/IRS1040/{tag}")
        found[line] = int(float(node.text)) if node is not None and node.text else 0
    return found


def score(lines: dict[str, int], expected: dict[str, int]) -> tuple[int, int, int]:
    strict = sum(1 for k, v in expected.items() if lines.get(k, 0) == v)
    lenient = sum(1 for k, v in expected.items() if abs(lines.get(k, 0) - v) <= LENIENT)
    return strict, lenient, len(expected)


def main(argv: list[str]) -> int:
    folders = [Path(a) for a in argv] or case_folders()
    bad = 0
    print(f"{'case':32} {'outcome':14} {'strict':>8} {'lenient':>8} all lines")
    for folder in folders:
        want = json.loads((folder / "expected.json").read_text(encoding="utf-8"))
        result = run(folder)
        ok = result["outcome"] == want["outcome"]
        strict = lenient = "-"
        all_lines = "-"
        if want["outcome"] == "prepared" and result["lines"]:
            s, le, n = score(result["lines"], expected_xml(folder))
            strict, lenient = f"{s}/{n}", f"{le}/{n}"
            same = result["lines"] == want["lines"]
            all_lines = f"{'exact' if same else 'DIFFERENT'} ({len(want['lines'])})"
            ok = ok and s == n and same
        bad += not ok
        print(f"{folder.name:32} {result['outcome']:14} {strict:>8} {lenient:>8} {all_lines}")
    print(f"{len(folders) - bad} of {len(folders)} cases match")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
