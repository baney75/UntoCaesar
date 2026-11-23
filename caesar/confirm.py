"""The person channel for caesar confirm.

Confirmation never goes through the model. caesar confirm shows each fact, its value and its
source to the person and records only the person's answer, signed in the ledger (ledger.py). The
one channel is Local Studio's question card (ask.py), which only caesar-mcp's process can reach.
With no channel, or when the card is cancelled or refused, nothing is recorded and the best state
a return reaches is "computed, not confirmed". No variable or file turns confirmation on: the
golden runner's scripted person replaces channel() inside its own process (tests/golden/runner.py).
"""

from __future__ import annotations

from . import ask
from . import facts as F

SCRIPTED = F.SCRIPTED
PERSON = F.PERSON
CHOICES = ["Yes", "No"]


class AskUser:
    """One yes or no question to the person. Returns "yes", "no", or None when no one answered (see why)."""

    name = ""
    why = ""

    def ask(self, fact: str, question: str) -> str | None:
        raise NotImplementedError


class NoPersonChannel(AskUser):
    def ask(self, fact: str, question: str) -> str | None:
        return None


class LocalStudio(AskUser):
    name = PERSON

    def ask(self, fact: str, question: str) -> str | None:
        reply = ask.ask(question, CHOICES)
        if reply["status"] == "answered":
            said = reply["answer"].strip().lower().rstrip(".!")
            if said in ("yes", "no"):
                return said
            self.why = "the person typed an answer that is not yes or no"
        elif reply["status"] == "cancelled":
            self.why = "the person stopped the question"
        else:
            self.why = f"Local Studio's question card was not reached: {reply.get('error', 'refused')}"
        return None


def channel() -> AskUser:
    return LocalStudio() if ask.available() else NoPersonChannel()


def question(name: str, entry: dict) -> str:
    return f"Is this right? {name} = {entry['value']} (source: {entry['source']}). Answer yes or no."
