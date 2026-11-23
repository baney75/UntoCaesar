"""Judge the three-line explanations in a results folder, blind, for the M and L explanation bar.

Test build: synthetic cases only, not for real records.

    python3 evals/judge.py evals/results/<folder> --driver openai --model <judge> [--base-url URL]

For each run that recorded an explanation, the judge gets the explanation, the known amounts of
Form 1040 lines 11a, 16 and 24, and caesar's own `caesar explain` text for each line as the
reference. It does not get the model, driver, tier or case name. It answers with one JSON object;
an explanation is correct when all three lines are right in amount and meaning and each cites an
IRS form line, instruction or rule. Writes <folder>/judged.jsonl, which evals/score.py reads.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import drivers  # noqa: E402
import run as R  # noqa: E402


def prompt(rec: dict) -> str:
    known = R.known_lines(R.CASES / rec["case"])
    reference = "\n\n".join(f"--- caesar explain {line} ---\n{text.strip()}" for line, text in rec["explain_reference"].items())
    amounts = ", ".join(f"line {line.removeprefix('1040.')}: ${known.get(line, 0):,}" for line in R.EXPLAIN_LINES)
    return ("You are grading a tax assistant's explanation of three lines of a 2025 Form 1040, blind. The known"
            f" amounts are {amounts}. The reference explanations from the tax engine are below.\n\n{reference}\n\n"
            f"--- the explanation to grade ---\n{rec['explanation']}\n\n"
            "The explanation is correct only when, for each of the three lines, it states the right amount, says"
            " correctly what the line is and how it was reached, and cites an IRS form line, instruction or rule."
            ' Reply with one JSON object and nothing else: {"correct": true or false, "why": "<one sentence>"}.')


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path)
    ap.add_argument("--driver", choices=["openai", "claude"], required=True)
    ap.add_argument("--model", default="")
    ap.add_argument("--base-url", default="http://127.0.0.1:11434/v1")
    args = ap.parse_args(argv)
    judge = drivers.make(args.driver, args.model, args.base_url, 0.0)
    recs = [json.loads(line) for line in (args.folder / "records.jsonl").read_text(encoding="utf-8").splitlines() if line]
    asked = [r for r in recs if r.get("explanation")]
    random.Random(0).shuffle(asked)  # the order says nothing about the model either
    rows = []
    for rec in asked:
        try:
            reply = judge.chat([{"role": "user", "content": prompt(rec)}], None)["content"]
        except drivers.QuotaStop as err:
            print(f"STOPPED: quota, limit or billing prompt: {err}", file=sys.stderr)
            return 3
        verdict = R.parse_json(reply) or {}
        rows.append({"case": rec["case"], "run": rec["run"], "correct": verdict.get("correct") is True,
                     "why": str(verdict.get("why", reply[:300]))})
    with (args.folder / "judged.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    print(f"judged {len(rows)} explanations: {sum(r['correct'] for r in rows)} correct")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
