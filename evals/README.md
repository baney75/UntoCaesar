# Tier evals

Test build: synthetic cases only, not for real records.

The model-in-the-loop evals that docs/SPEC.md "Tier evals" and "The check that says it wins"
define. The engine eval (tests/golden, `pytest`) stays as it is; this folder runs a model.

## Suites

Each case in `tests/golden/2025/` names its suites in `expected.json` (`"suites"`):

| Suite | In-scope cases | Refusal cases |
| --- | --- | --- |
| S | 12, W-2 only | 8 |
| M | 24, W-2 plus Schedule C and SE | 10 |
| L | 30, every v0 case | 10 |

Each case folder holds `documents/` (the person's W-2s and 1099s and business records, as text)
and `answers.json` (what the simulated person says, or which document holds the value). Both are
written by `python3 tests/golden/documents.py`; `--check` reports any that are out of date.

## Run

    python3 evals/run.py --suite S --driver openai --model hf.co/LiquidAI/LFM3-1.7B-GGUF:Q4_K_M --runs 10
    python3 evals/score.py evals/results/<folder>

One run is one fresh session, the way Local Studio runs `/taxes`:

- the system turn names the local model; the user turn is the skill text plus the tier card
  (`--card`, the suite's by default) and `/taxes`
- tools: `bash`, which runs one `caesar ...` line (or one `caesar set` heredoc) in the job's
  folder, plus `ls documents` and `cat documents/<file>` so the model can read the documents;
  anything else is refused without reaching a shell. And caesar-mcp's tools over stdio, started
  with `LOCAL_STUDIO_LOCAL_ONLY=1`
- the simulated person (`person.py`, rules only) answers what caesar is waiting on: the answer for
  facts only the person knows, or the document that holds the value. A misread value the confirm
  card rejected gets the true value
- the confirm card goes to the scripted person inside the caesar-mcp process (`seam.py`), which
  says yes only when a value matches the case's true value

Each run writes one line to `records.jsonl`: the outcome, the TaxCalcBench Form 1040 lines strict
and within $5, whether the full return matches, silent error (prepared but wrong), refusal
correctness (refused, with the case's message in caesar's output) and network connections.

For M and L, a prepared run is then asked to explain lines 11a, 16 and 24. `evals/judge.py` grades
those blind against `caesar explain` and writes `judged.jsonl`; until it runs, score.py prints
"not judged".

## Baselines (the win check)

    python3 evals/run.py --suite M --mode baseline --driver openai --model <same local model> --runs 10
    python3 evals/run.py --suite M --mode baseline --driver claude --cases <case> <case> --runs 1

The model gets the same documents and the person's answers in one prompt and returns the Form
1040 lines as JSON, or a refusal. Every wrong set of lines counts as a silent error, since nothing
checks it. The `claude` driver runs `env -u ANTHROPIC_API_KEY claude -p` on the signed-in account,
with no tools; it is for this baseline only and waits while the 1 minute load is 6 or more. Any
quota, limit or billing answer stops every run and writes `STOPPED`.

## Network tracing

On Linux, every caesar bash call and the caesar-mcp server run under
`strace -f -e trace=connect,sendto,sendmsg`, and any AF_INET or AF_INET6 address counts as a
connection. Where strace is missing, cannot attach, or `--no-trace` is given, the run is marked
not traced and the network bar fails. macOS and Windows runs are never traced.

## Fake model

`--driver reader` uses no model: it follows caesar's NEXT lines, asks the person, and reads values
from the documents. tests/test_evals.py runs it, directly and behind a fake OpenAI-compatible
server, so CI covers the harness without a model.
