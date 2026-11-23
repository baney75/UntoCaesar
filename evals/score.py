"""Print a results folder's tier table against the bars in docs/SPEC.md "Tier evals".

Test build: synthetic cases only, not for real records.

    python3 evals/score.py evals/results/<folder> [<folder> ...]

Reads <folder>/records.jsonl (from evals/run.py) and, when present, <folder>/judged.jsonl (from
evals/judge.py). Prints Markdown: one table per folder, then a per-case table. Exits 0 when every
bar passes, 1 otherwise.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

EXACT_BAR = {"S": 0.8, "M": 0.9, "L": 1.0}
EXPLAIN_BAR = {"S": None, "M": 0.8, "L": 0.9}


def load(folder: Path) -> tuple[dict, list[dict], dict]:
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8")) if (folder / "meta.json").exists() else {}
    records = [json.loads(line) for line in (folder / "records.jsonl").read_text(encoding="utf-8").splitlines() if line]
    judged = {}
    if (folder / "judged.jsonl").exists():
        for line in (folder / "judged.jsonl").read_text(encoding="utf-8").splitlines():
            if line:
                row = json.loads(line)
                judged[(row["case"], row["run"])] = row["correct"]
    return meta, records, judged


def table(meta: dict, records: list[dict], judged: dict) -> tuple[list[tuple[str, str, str, bool | None]], dict]:
    """Rows of (measure, result, bar, passed); passed is None when the measure is not scored."""
    suite = meta.get("suite") or records[0]["suite"]
    by_case: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_case[r["case"]].append(r)
    in_scope = {c: rs for c, rs in by_case.items() if rs[0]["expected_outcome"] != "refused"}
    refusals = {c: rs for c, rs in by_case.items() if rs[0]["expected_outcome"] == "refused"}
    bar = EXACT_BAR[suite]
    rates = {c: sum(r["exact"] for r in rs) / len(rs) for c, rs in in_scope.items()}
    meeting = sum(1 for v in rates.values() if v >= bar - 1e-9)
    runs = sum(len(rs) for rs in in_scope.values())
    exact_runs = sum(r["exact"] for rs in in_scope.values() for r in rs)
    strict = sum(r.get("strict", 0) for rs in in_scope.values() for r in rs)
    lines = sum(r.get("lines_scored", 0) for rs in in_scope.values() for r in rs)
    lenient = sum(r.get("lenient", 0) for rs in in_scope.values() for r in rs)
    silent = sum(r["silent_error"] for r in records)
    ref_runs = sum(len(rs) for rs in refusals.values())
    ref_ok = sum(r.get("refusal_correct", False) for rs in refusals.values() for r in rs)
    plugin = all(r.get("mode", "plugin") == "plugin" for r in records)
    traced = all(r["network"]["traced"] for r in records)
    conns = sum(r["network"]["connections"] for r in records)
    rows = [
        ("In-scope cases", f"{len(in_scope)}", {"S": "12", "M": "24", "L": "30"}[suite], None),
        (f"Cases at {round(bar * 10)} of 10 exact or better", f"{meeting} of {len(in_scope)} ({exact_runs} of {runs} runs exact)",
         f"every case at {round(bar * 10)} of 10", bool(in_scope) and meeting == len(in_scope)),
        ("Form 1040 lines, strict / within $5", f"{strict} / {lenient} of {lines}", "for reference", None),
        ("Silent errors", f"{silent}", "0", silent == 0),
        ("Refusals stopped right", f"{ref_ok} of {ref_runs} runs ({len(refusals)} cases)", "every run",
         ref_ok == ref_runs if ref_runs else None),
    ]
    if plugin:
        rows.append(("Network connections (traced)", f"{conns}" if traced else f"{conns}, not traced in every run",
                     "0, every run traced", traced and conns == 0))
    else:
        rows.append(("Network connections (traced)", "not traced: no plugin code runs", "plugin runs only", None))
    explain_bar = EXPLAIN_BAR[suite]
    asked = [r for r in records if "explanation" in r]
    if explain_bar is None:
        rows.append(("Explanation of three lines (blind judge)", "not scored for S", "not scored", None))
    elif not judged:
        rows.append(("Explanation of three lines (blind judge)",
                     f"not judged ({len(asked)} explanations recorded)", f"{round(explain_bar * 10)} of 10", None))
    else:
        ok = sum(judged.get((r["case"], r["run"]), False) for r in asked)
        prepared = sum(1 for rs in in_scope.values() for r in rs)
        rows.append(("Explanation of three lines (blind judge)", f"{ok} of {prepared} runs",
                     f"{round(explain_bar * 10)} of 10", prepared > 0 and ok / prepared >= explain_bar - 1e-9))
    return rows, {c: rs for c, rs in sorted(by_case.items())}


def render(folder: Path) -> tuple[str, bool]:
    meta, records, judged = load(folder)
    rows, by_case = table(meta, records, judged)
    head = (f"### {meta.get('suite')} suite, {meta.get('mode', 'plugin')}: {meta.get('model') or meta.get('driver')}\n\n"
            f"Driver {meta.get('driver')}, card {meta.get('card')}, {meta.get('runs')} runs per case, {meta.get('date')},"
            f" host {meta.get('host')}{', ' + meta['hardware'] if meta.get('hardware') else ''}, commit {meta.get('commit')}.\n")
    if (folder / "records.sha256").exists():
        head += f"Log hash (sha256 of records.jsonl): {(folder / 'records.sha256').read_text().strip()}\n"
    if (folder / "STOPPED").exists():
        head += f"**{(folder / 'STOPPED').read_text().strip()}**\n"
    out = [head, "| Measure | Result | Bar | Pass |", "| --- | --- | --- | --- |"]
    for measure, result, bar, ok in rows:
        out.append(f"| {measure} | {result} | {bar} | {'n/a' if ok is None else 'yes' if ok else 'no'} |")
    out += ["", "| Case | Expected | Runs exact | Silent | Outcomes |", "| --- | --- | --- | --- | --- |"]
    for case, rs in by_case.items():
        outcomes = ", ".join(sorted({r["outcome"] for r in rs}))
        out.append(f"| {case} | {rs[0]['expected_outcome']} | {sum(r['exact'] for r in rs)} of {len(rs)}"
                   f" | {sum(r['silent_error'] for r in rs)} | {outcomes} |")
    passed = all(ok for *_, ok in rows if ok is not None)
    return "\n".join(out) + "\n", passed


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    passed = True
    for arg in argv:
        text, ok = render(Path(arg))
        print(text)
        passed = passed and ok
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
