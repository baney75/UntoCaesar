"""The simulated person: a small rule-based responder, no model.

Test build: synthetic cases only, not for real records.

When the model speaks to the person (a reply with no tool call), the person answers the question
caesar is waiting on, read from the job itself: the next missing fact, or the fact caesar asks
again after the person rejected it. The answer comes from the case's answers.json: the answer
itself for facts only the person knows (screening answers, filing status, dependents), or the
document that holds it for facts on a form, so the model has to read the document. A misread
fact the person rejected is answered with its true value. Confirmation cards are answered
elsewhere, by the scripted person inside caesar-mcp (evals/seam.py).
"""

from __future__ import annotations

import re
from pathlib import Path

from caesar import cli
from caesar import facts as F

STATUS = {"single": "single", "mfj": "married filing jointly", "mfs": "married filing separately",
          "hoh": "head of household", "qss": "qualifying surviving spouse"}
DOCS = {"w2": "W-2", "1099-int": "1099-INT", "1099-div": "1099-DIV", "1099-nec": "1099-NEC", "business": "business records"}


def pending(job: Path) -> tuple[str, str | None]:
    """What caesar waits on: ("ask", fact), ("fix", fact), ("confirm", None), ("done", None) or ("go", None)."""
    j = cli.Job(job)
    step = cli.next_step(j)
    if step is None:
        return "done", None
    if step == "ask":
        missing = F.missing(j.facts())
        return ("ask", missing[0].name) if missing else ("go", None)
    if step.startswith("set "):
        return "fix", step.split()[1]
    if step == "confirm":
        return "confirm", None
    return "go", None


def phrase(fact: str, value: str) -> str:
    if fact == "filing_status":
        return f"My filing status is {value} ({STATUS.get(value, value)})."
    if value in ("yes", "no"):
        return f"{value.capitalize()}."
    return f"{value}."


def document_label(name: str) -> str:
    stem = name.removesuffix(".txt")
    for prefix, label in DOCS.items():
        if stem.startswith(prefix):
            return label
    return "document"


WORD = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SMALL = {"the", "and", "for", "you", "your", "did", "was", "were", "what", "with", "that", "this", "any", "from", "2025",
         "spouse", "have", "how", "many", "much", "does", "are", "get", "got", "say", "its", "his", "her", "their"}


def words(text: str) -> set[str]:
    return {w for w in WORD.findall(text.lower()) if len(w) > 2 and w not in SMALL}


def asks(said: str, question: str) -> bool:
    """Whether the model's message puts caesar's question to the person: most of its words, or the fact name."""
    want = words(question)
    return bool(want) and len(want & words(said)) >= 0.5 * len(want)


class Person:
    def __init__(self, answers: dict, job: Path):
        self.facts = answers["facts"]
        self.job = job
        self.idle = 0  # replies in a row that found caesar waiting on the same thing
        self.last: tuple[str, str | None] | None = None

    def reply(self, said: str) -> tuple[str, bool]:
        """(the person's reply, whether the conversation is over)."""
        now = pending(self.job)
        self.idle = self.idle + 1 if now == self.last else 0
        self.last = now
        kind, fact = now
        if kind == "done":
            return "Thank you. That is all I need.", True
        if kind == "confirm":
            return "Please ask me to confirm the facts with the caesar_confirm tool.", False
        if kind == "go" or fact not in self.facts:
            return "Please go on.", False
        entry = self.facts[fact]
        if kind == "fix" and "correction" in entry:
            text = (f"That copy of the form is wrong. The right amount for {fact} is {entry['correction']}."
                    " Use source: answer.")
        elif "document" in entry:
            doc = entry["document"]
            text = f"That is on my {document_label(doc)}. It is in the documents folder: documents/{doc}"
        else:
            text = phrase(fact, entry["say"])
        spec = F.spec_for(cli.Job(self.job).facts(), fact)
        question = spec.question if spec else fact
        if kind == "ask" and fact not in said and not asks(said, question):
            # The model asked something else. A person answers the question that is actually next.
            text = f"I am not sure what you are asking. The next question on my list is: {question} My answer: {text}"
        return text, False
