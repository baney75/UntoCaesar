"""The person channel for caesar confirm.

Confirmation never goes through the model. caesar confirm shows each fact, its value and its
source to the person and records only the person's answer, signed in the ledger (ledger.py). The
one channel will be Local Studio's question card, asked from caesar-mcp's process; until it lands
there is no channel, nothing is recorded and the best state a return reaches is "computed, not
confirmed". No variable or file turns confirmation on: the
golden runner's scripted person replaces channel() inside its own process (tests/golden/runner.py).
"""

from __future__ import annotations

from . import facts as F

SCRIPTED = F.SCRIPTED
PERSON = F.PERSON


class AskUser:
    """One yes or no question to the person. Returns "yes", "no", or None when no one answered (see why)."""

    name = ""
    why = ""

    def ask(self, fact: str, question: str) -> str | None:
        raise NotImplementedError


class NoPersonChannel(AskUser):
    def ask(self, fact: str, question: str) -> str | None:
        return None


def channel() -> AskUser:
    return NoPersonChannel()


def question(name: str, entry: dict) -> str:
    return f"Is this right? {name} = {entry['value']} (source: {entry['source']}). Answer yes or no."
