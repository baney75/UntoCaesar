"""Run a golden case through caesar the way the skill does, and score it.

The runner sets each fact from the case (tests/golden/to_facts.py), then runs whatever each
NEXT: line says until caesar says NEXT: none or asks for a fact. The scripted person answers
caesar confirm from the case's true values. Scoring follows TaxCalcBench: each Form 1040 line
in output.xml is scored strict (exact) and lenient (within $5).

Usage: python3 tests/golden/runner.py [case folder ...]   prints a score table.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shlex
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


def caesar(job: Path, *args: str) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cli.main(["--job", str(job), *args])
    return code, buf.getvalue()


def next_command(output: str, job: Path) -> list[str] | None:
    line = output.strip().splitlines()[-1]
    assert line.startswith("NEXT: "), output
    words = shlex.split(line[len("NEXT: "):]) if os.name != "nt" else line[len("NEXT: "):].split()
    if words == ["none"]:
        return None
    assert words[:3] == ["caesar", "--job", str(job)], line
    return words[3:]


def run(folder: Path, scripted: bool = True, workdir: Path | None = None) -> dict:
    case = to_facts.load(folder)
    work = Path(workdir or tempfile.mkdtemp(prefix="caesar-golden-"))
    job = work / "job"
    env = {"CAESAR_CMD": "caesar"}
    if scripted:
        truth = work / "person.json"
        truth.write_text(json.dumps(to_facts.truth(case)), encoding="utf-8")
        env["CAESAR_SCRIPTED_PERSON"] = str(truth)
    saved = {k: os.environ.get(k) for k in ("CAESAR_CMD", "CAESAR_SCRIPTED_PERSON")}
    os.environ.pop("CAESAR_SCRIPTED_PERSON", None)
    os.environ.update(env)
    transcript = []
    try:
        transcript.append(("new", *caesar(job, "new")))
        refused_at = ""
        for name, value, source in to_facts.convert(case):
            code, out = caesar(job, "set", name, value, "--source", source)
            transcript.append((f"set {name}", code, out))
            # A model follows NEXT, so a set that ends in NEXT: none stops the interview.
            if code == 1 or out.strip().endswith("NEXT: none"):
                refused_at = "set"
                break
        for _ in range(40):
            code, out = caesar(job, "status")
            command = next_command(out, job)
            if command is None or command[0] == "set":
                break
            code, out = caesar(job, *command)
            transcript.append((" ".join(command), code, out))
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
