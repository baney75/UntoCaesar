"""The person channel for caesar confirm: the stub of Local Studio's ask-user hook.

Confirmation never goes through the model. caesar confirm shows each fact, its value and its
source to the person and records only the person's answer. A plugin command cannot open
Local Studio's ask-user dialog yet, and the core does not yet guarantee that the person, not
the session's model, answers it (local-studio#15). Until both land:

- With no person channel, caesar records no confirmation, and the best state a return
  reaches is "computed, not confirmed".
- The eval harness's scripted person answers through CAESAR_SCRIPTED_PERSON, a JSON file
  {"facts": {"<fact>": "<true value>", ...}}. It says yes when the value caesar shows matches
  the true value and no otherwise, so a misread fact ends in a failing check. Its answers are
  recorded as the scripted test person's, never as a real person's.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import facts as F

SCRIPTED = "scripted test person"


class AskUser:
    """One yes or no question to the person. Returns "yes", "no", or None when no one answered."""

    name = ""

    def ask(self, fact: str, question: str) -> str | None:
        raise NotImplementedError


class NoPersonChannel(AskUser):
    name = ""

    def ask(self, fact: str, question: str) -> str | None:
        return None


class ScriptedPerson(AskUser):
    name = SCRIPTED

    def __init__(self, path: Path, facts: dict):
        with path.open(encoding="utf-8") as f:
            self.truth = json.load(f).get("facts", {})
        self.facts = facts

    def ask(self, fact: str, question: str) -> str | None:
        if fact not in self.truth:
            return "no"
        spec = F.spec_for(self.facts, fact)
        try:
            true_value = F.normalize(spec.kind, str(self.truth[fact])) if spec else str(self.truth[fact])
        except ValueError:
            return "no"
        return "yes" if self.facts[fact]["value"] == true_value else "no"


def channel(facts: dict) -> AskUser:
    path = os.environ.get("CAESAR_SCRIPTED_PERSON")
    if path:
        return ScriptedPerson(Path(path), facts)
    return NoPersonChannel()


def question(name: str, entry: dict) -> str:
    return f"Is this right? {name} = {entry['value']} (source: {entry['source']}). Answer yes or no."
