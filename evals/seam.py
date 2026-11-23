"""Run caesar or caesar-mcp for one eval run, with the run's ledger key and, for caesar-mcp, the scripted person.

Test build: synthetic cases only, not for real records.

    python3 evals/seam.py cli <caesar args>    what the model's bash runs for each caesar line
    python3 evals/seam.py mcp                  the stdio MCP server, as Local Studio starts it

The eval harness (evals/run.py) starts both, each under strace when it can. It sets
CAESAR_EVAL_KEY (the run's ledger key, in place of the OS keychain) for both. For the MCP server
it also sets CAESAR_EVAL_TRUTH (the case's true facts) and CAESAR_EVAL_JOB, and only there does
caesar confirm reach the scripted person, who says yes when the value matches the true value and
no otherwise, so a misread fact ends in a failing check. The CLI gets no person channel, as in
Local Studio, where only the plugin's MCP server can reach the question card.

This is a test seam like tests/golden/runner.py's scripted_person(): the variables exist only in
the processes the harness starts, and the model's bash tool runs nothing but caesar lines.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "golden"))

from caesar import keystore  # noqa: E402


def install_key() -> None:
    key = bytes.fromhex(os.environ["CAESAR_EVAL_KEY"])
    keystore.load_key = lambda create, service=keystore.SERVICE: (key, "")


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ("cli", "mcp"):
        print(__doc__)
        return 2
    install_key()
    if argv[0] == "cli":
        from caesar import cli
        return cli.main(argv[1:])
    import runner
    from caesar import confirm as K
    from caesar import mcp
    truth = json.loads(Path(os.environ["CAESAR_EVAL_TRUTH"]).read_text(encoding="utf-8"))
    job = Path(os.environ["CAESAR_EVAL_JOB"])
    K.channel = lambda: runner.ScriptedPerson(truth, job)
    return mcp.main()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
