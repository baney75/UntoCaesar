"""Cross-check caesar's golden cases against OpenTaxSolver 2025.

Test build: synthetic cases only, not for real records.

OpenTaxSolver is a separate, independent tax program. This script fills its text templates
from each prepared golden case's facts (never from caesar's computed lines, except where OTS
itself asks the user to carry a number from another OTS form, and then it carries the OTS
number), runs its solvers in the order its forms feed each other, and compares every line
both programs produce. It is a developer tool, not part of caesar or the test suite: it needs
an OTS 2025 source tree and a C compiler, and it builds only while the 1-minute load average is
under 8.

    python3 tests/crosscheck/ots.py --src <OpenTaxSolver2025 folder> --work <scratch folder>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "golden"))
import to_facts  # noqa: E402

CASES = HERE.parent / "golden" / "2025"
PROGRAMS = ["US_1040_2025", "US_1040_Sched_C_2025", "US_1040_Sched_SE_2025", "f8812_2025", "f8995_2025"]
STATUS = {"single": "Single", "mfj": "Married/Joint", "hoh": "Head_of_House", "mfs": "Married/Sep", "qss": "Widow(er)"}


def load_ok() -> float:
    return os.getloadavg()[0]


def build(src: Path, bin_dir: Path) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name in PROGRAMS:
        out = bin_dir / f"taxsolve_{name}"
        if out.exists():
            continue
        load = load_ok()
        if load >= 8:
            raise SystemExit(f"1-minute load is {load:.2f}, not under 8. Not building.")
        subprocess.run(["nice", "-n", "19", "gcc", "-O1", "-w", "-o", str(out), f"taxsolve_{name}.c"],
                       cwd=src / "src", check=True)


def fill(template: str, values: dict[str, str]) -> str:
    """Put each value after its label on the label's first line, dropping any value already there."""
    for label, value in values.items():
        pattern = re.compile(rf"^([ \t]*{re.escape(label)})(?=[\s;{{:]|$)[ \t]*(?:(?![{{;])\S+)?", re.M)
        template, n = pattern.subn(lambda m: f"{m.group(1)} {value} ", template, count=1)
        if n != 1:
            raise KeyError(f"label {label} not in template")
    return template


def run(bin_dir: Path, program: str, form: Path) -> dict[str, Decimal]:
    subprocess.run([str(bin_dir / f"taxsolve_{program}"), str(form)], cwd=form.parent, check=True,
                   capture_output=True, text=True)
    out = form.with_name(form.stem + "_out.txt")
    lines: dict[str, Decimal] = {}
    for line in out.read_text().splitlines():
        m = re.match(r"^([A-Za-z0-9_]+) = +(-?[0-9.]+)(?:\s|$)", line)
        if m and m.group(1) not in lines:
            lines[m.group(1)] = Decimal(m.group(2))
    return lines


def yn(v: str) -> str:
    return "Y" if v == "yes" else "N"


def money(facts: dict, name: str) -> Decimal:
    return Decimal(str(facts.get(name, ("0",))[0]) or "0")


def count(facts: dict, name: str) -> int:
    return int(facts.get(name, ("0",))[0])


def owner(facts: dict, prefix: str) -> str:
    return facts.get(f"{prefix}.owner", ("taxpayer",))[0]


def crosscheck(case: Path, src: Path, bin_dir: Path, work: Path) -> dict:
    facts = to_facts.all_facts(json.loads((case / "input.json").read_text()))
    expected = json.loads((case / "expected.json").read_text())["lines"]
    t = src / "tax_form_files"
    tpl_1040 = (t / "US_1040" / "US_1040_template.txt").read_text()
    tpl_c = (t / "US_1040_Sched_C" / "US_1040Sched_C_2025_template.txt").read_text()
    tpl_se = (t / "US_1040_Sched_SE" / "US_1040_Sched_SE_template.txt").read_text()
    tpl_8812 = (t / "Form_8812" / "Form_8812_template.txt").read_text()
    tpl_8995 = (t / "Form_8995" / "Form_8995_template.txt").read_text()
    folder = work / case.name
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)

    status = facts["filing_status"][0]
    joint = status == "mfj"
    w2s = [f"w2.{i}" for i in range(1, count(facts, "w2.count") + 1)]
    ints = [f"int1099.{i}" for i in range(1, count(facts, "int1099.count") + 1)]
    divs = [f"div1099.{i}" for i in range(1, count(facts, "div1099.count") + 1)]
    necs = [f"nec1099.{i}" for i in range(1, count(facts, "nec1099.count") + 1)]
    deps = [f"dependent.{i}" for i in range(1, count(facts, "dependents.count") + 1)]
    ots: dict[str, Decimal] = {}

    # Schedule C and SE, one per business owner.
    sched_c_out, s1_3, s1_15, s2_4 = None, Decimal(0), Decimal(0), Decimal(0)
    for i in range(1, count(facts, "business.count") + 1):
        b = f"business.{i}"
        who = owner(facts, b)
        f = lambda k: str(money(facts, f"{b}.{k}"))  # noqa: E731
        c_form = folder / f"c_{who}.txt"
        c_form.write_text(fill(tpl_c, {
            "L1": f("gross_receipts"), "L2": f("returns"), "L6": f("other_income"), "L8": f("advertising"),
            "L9": f("parking_tolls"), "L10": f("commissions"), "L11": f("contract_labor"),
            "L14": f("employee_benefits"), "L15": f("insurance"), "L16a": f("mortgage_interest"),
            "L16b": f("other_interest"), "L17": f("legal_professional"), "L18": f("office"),
            "L19": f("pension_plans"), "L20a": f("rent_equipment"), "L20b": f("rent_other"),
            "L21": f("repairs"), "L22": f("supplies"), "L23": f("taxes_licenses"), "L24a": f("travel"),
            "L24b": str(money(facts, f"{b}.meals") / 2), "L25": f("utilities"), "L26": f("wages"),
            "L32a": "Yes", "L44a": f("business_miles"), "L48a_amnt": f("other_expenses"),
        }))
        c = run(bin_dir, "US_1040_Sched_C_2025", c_form)
        sched_c_out = c_form.with_name(c_form.stem + "_out.txt")
        ots.update({f"schc-{who}.{k[1:]}": v for k, v in c.items() if k.startswith("L")})
        s1_3 += c["L31"]
        wages = sum((money(facts, f"{w}.box3") + money(facts, f"{w}.box7") for w in w2s if owner(facts, w) == who), Decimal(0))
        se_form = folder / f"se_{who}.txt"
        se_form.write_text(fill(tpl_se, {"L2": str(c["L31"]), "L8a": str(wages)}))
        se = run(bin_dir, "US_1040_Sched_SE_2025", se_form)
        ots.update({f"se-{who}.{k[1:]}": v for k, v in se.items() if k.startswith("L")})
        s2_4 += se.get("L12", Decimal(0))
        s1_15 += se.get("L13", Decimal(0))

    base = {
        "Status": STATUS[status],
        "You_65+Over?": yn(facts["taxpayer.born_before_1961"][0]), "You_Blind?": yn(facts["taxpayer.blind"][0]),
        "Spouse_65+Over?": yn(facts["spouse.born_before_1961"][0]) if joint else "N",
        "Spouse_Blind?": yn(facts["spouse.blind"][0]) if joint else "N",
        "Dependents": str(len(deps)),
        "L1a": " ".join(str(money(facts, f"{w}.box1")) for w in w2s) or "0",
        "L2a": " ".join(str(money(facts, f"{x}.box8")) for x in ints) or "0",
        "L2b": " ".join(str(money(facts, f"{x}.box1") + money(facts, f"{x}.box3")) for x in ints) or "0",
        "L3b": " ".join(str(money(facts, f"{x}.box1a")) for x in divs) or "0",
        "L25a": " ".join(str(money(facts, f"{w}.box2")) for w in w2s) or "0",
        "L25b": " ".join(str(money(facts, f"{x}.box4")) for x in ints + divs + necs) or "0",
        "L26": str(money(facts, "payments.estimated")),
        "S1_3": str(s1_3), "S1_15": str(s1_15), "S2_4": str(s2_4),
    }

    def form_1040(extra: dict[str, str], tag: str) -> tuple[dict[str, Decimal], Path]:
        path = folder / f"f1040_{tag}.txt"
        path.write_text(fill(tpl_1040, {**base, **extra}))
        return run(bin_dir, "US_1040_2025", path), path.with_name(path.stem + "_out.txt")

    f1040, f1040_out = form_1040({}, "1")
    extra: dict[str, str] = {}

    # Form 8995, from the OTS 1040 output file. Line 1 is typed in with the formula OTS's own
    # auto calculation uses (Schedule C line 31 less Schedule 1 line 15), because with auto
    # calculation on, the stock template's row iii name field (a lone ";") counts as a second
    # business and doubles line 2.
    if sched_c_out is not None:
        p = folder / "f8995.txt"
        p.write_text(fill(tpl_8995, {"FileName1040": f1040_out.name, "L1_i_a:": "Business",
                                     "L1_i_c": str(s1_3 - s1_15)}))
        q = run(bin_dir, "f8995_2025", p)
        ots.update({f"8995.{k[1:]}": v for k, v in q.items() if k.startswith("L") and k[1:].isdigit()})
        ots[f"8995-{who}.1"] = q["L1_i_c"]
        extra["L13a"] = str(q["L15"])
        f1040, f1040_out = form_1040(extra, "2")

    # Schedule 8812.
    if deps:
        children = [d for d in deps if facts[f"{d}.qualifying_child"][0] == "yes"
                    and facts.get(f"{d}.under_17", ("no",))[0] == "yes"
                    and facts[f"{d}.ssn_valid_for_work"][0] == "yes"]
        earned = f1040["L1z"] + s1_3 - s1_15
        p = folder / "f8812.txt"
        p.write_text(fill(tpl_8812, {
            "Status": STATUS[status], "L1": str(f1040["L11a"]), "L4": str(len(children)),
            "L6": str(len(deps) - len(children)), "L13": str(f1040["L18"]), "L18a": str(earned),
            "L21": " ".join(str(money(facts, f"{w}.box4") + money(facts, f"{w}.box6")) for w in w2s) or "0",
            "L22": str(s1_15),
        }))
        k = run(bin_dir, "f8812_2025", p)
        ots.update({f"8812.{n[1:]}": v for n, v in k.items() if n.startswith("L")})
        extra["L19"] = str(k["L14"])
        extra["L28"] = str(k.get("L27", Decimal(0)))
        f1040, f1040_out = form_1040(extra, "3")

    for k, v in f1040.items():
        if re.fullmatch(r"L\d+[a-z]?", k):
            ots["1040.12e" if k == "L12" else f"1040.{k[1:]}"] = v
        elif re.fullmatch(r"S1_\d+[a-z]?", k):
            ots[f"s1.{k[3:]}"] = v
        elif re.fullmatch(r"S2_\d+[a-z]?", k):
            ots[f"s2.{k[3:]}"] = v
        elif re.fullmatch(r"S1A_\d+[a-z]?", k):
            ots[f"s1a.{k[4:]}"] = v

    rows = []
    for line, mine in expected.items():
        if line not in ots:
            continue
        theirs = ots[line]
        whole = int(theirs.quantize(Decimal(1), rounding=ROUND_HALF_UP))
        rows.append({"line": line, "caesar": mine, "ots": str(theirs), "exact": whole == mine,
                     "within5": abs(theirs - mine) <= 5})
    return {"case": case.name, "rows": rows, "only_caesar": sorted(set(expected) - set(ots))}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    bin_dir = a.work / "bin"
    build(a.src, bin_dir)
    results = []
    for case in sorted(CASES.iterdir()):
        exp = case / "expected.json"
        if exp.exists() and json.loads(exp.read_text())["outcome"] == "prepared":
            results.append(crosscheck(case, a.src, bin_dir, a.work / "runs"))
    for r in results:
        rows = r["rows"]
        exact = sum(x["exact"] for x in rows)
        near = sum(x["within5"] for x in rows)
        print(f"{r['case']}: {len(rows)} shared lines, {exact} exact after rounding, {near} within $5")
        for x in rows:
            if not x["exact"]:
                print(f"  {x['line']}: caesar {x['caesar']}, OTS {x['ots']}")
    if a.json:
        a.json.write_text(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
