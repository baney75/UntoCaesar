"""Model drivers for the evals.

Test build: synthetic cases only, not for real records.

- openai: any OpenAI-compatible chat completions endpoint with tool calls, such as Ollama's
  /v1 on the local machine. Used for the plugin runs and the local no-plugin baseline.
- claude: `env -u ANTHROPIC_API_KEY claude -p`, on Donovan's own sign-in, with no tools, for the
  frontier no-plugin baseline only. It never runs the plugin, and it stops every run when the
  CLI reports a usage limit, quota or billing prompt.
- reader: no model. It follows caesar's NEXT lines, asks the person what only the person knows
  and reads every other value from the documents, so CI can run the harness end to end and
  prove the documents and answers hold everything a correct return needs.

chat(messages, tools) returns {"content": str, "tool_calls": [{"id", "name", "arguments"}]}.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "golden"))

import documents as D  # noqa: E402

STOP_WORDS = ("usage limit", "rate limit", "quota", "billing", "credit balance", "upgrade your plan", "out of credits")


class QuotaStop(Exception):
    """A quota, limit or billing prompt: every run stops (docs/SPEC.md rules for the evals)."""


class OpenAIDriver:
    name = "openai"

    def __init__(self, model: str, base_url: str, temperature: float | None = None, timeout: int = 900,
                 api_key: str | None = None, max_tokens: int | None = None, reasoning_effort: str | None = None):
        self.model, self.base, self.temperature, self.timeout = model, base_url.rstrip("/"), temperature, timeout
        self.api_key, self.max_tokens, self.reasoning_effort = api_key, max_tokens, reasoning_effort

    def post(self, body: dict) -> dict:
        req = urllib.request.Request(f"{self.base}/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json",
                                              **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as err:
            detail = err.read().decode(errors="replace")[:500]
            if err.code in (402, 429) or any(w in detail.lower() for w in STOP_WORDS):
                raise QuotaStop(f"HTTP {err.code}: {detail}") from None
            raise RuntimeError(f"HTTP {err.code}: {detail}") from None

    def chat(self, messages: list[dict], tools: list[dict] | None) -> dict:
        body = {"model": self.model, "messages": messages, "stream": False}
        if tools:
            body["tools"] = tools
        if self.temperature is not None:
            body["temperature"] = self.temperature
        if self.max_tokens:
            body["max_tokens"] = self.max_tokens
        if self.reasoning_effort:
            body["reasoning_effort"] = self.reasoning_effort
        msg = self.post(body)["choices"][0]["message"]
        calls = []
        for i, c in enumerate(msg.get("tool_calls") or []):
            fn = c.get("function", {})
            raw = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw) if isinstance(raw, str) else raw
            except ValueError:
                args = {"_unparsed": raw}
            calls.append({"id": c.get("id") or f"call_{i}", "name": fn.get("name", ""), "arguments": args})
        return {"content": msg.get("content") or "", "tool_calls": calls}


class ClaudeDriver:
    """The frontier chat model with no plugin and no tools. One prompt in, one reply out."""

    name = "claude"

    def __init__(self, model: str | None = None, timeout: int = 900, max_load: float = 6.0):
        self.model, self.timeout, self.max_load = model, timeout, max_load

    def wait_for_load(self) -> None:
        while os.getloadavg()[0] >= self.max_load:
            time.sleep(30)

    def chat(self, messages: list[dict], tools: list[dict] | None) -> dict:
        if tools:
            raise ValueError("the claude driver runs the no-plugin baseline only, with no tools")
        prompt = "\n\n".join(m["content"] for m in messages if m["role"] in ("system", "user"))
        self.wait_for_load()
        argv = ["env", "-u", "ANTHROPIC_API_KEY", "claude", "-p", "--output-format", "json", "--tools", "",
                "--no-session-persistence", "--strict-mcp-config", "--setting-sources", ""]
        if self.model:
            argv += ["--model", self.model]
        done = subprocess.run(argv, input=prompt.encode(), capture_output=True, timeout=self.timeout)
        out = done.stdout.decode(errors="replace")
        try:
            reply = json.loads(out)
        except ValueError:
            reply = {"is_error": True, "result": out + done.stderr.decode(errors="replace")}
        text = str(reply.get("result", ""))
        if reply.get("is_error") and any(w in text.lower() for w in STOP_WORDS):
            raise QuotaStop(text[:500])
        if reply.get("is_error"):
            raise RuntimeError(text[:500])
        return {"content": text, "tool_calls": []}


# ---------------------------------------------------------------------------
# reader: the no-model driver
# ---------------------------------------------------------------------------

HOLE = re.compile(r"<[a-z][^<>\n]*>")
PREFIX = {"w2": ("W-2", D.W2_LABELS), "int1099": ("1099-INT", D.INT_LABELS), "div1099": ("1099-DIV", D.DIV_LABELS),
          "nec1099": ("1099-NEC", D.NEC_LABELS)}


def last_next(text: str) -> str | None:
    """The command after the last NEXT: in a caesar reply, with a set's heredoc lines."""
    _, sep, step = ("\n" + text).rpartition("\nNEXT: ")
    return step.rstrip("\n") if sep else None


def read_label(doc: str, label: str) -> str | None:
    for line in doc.splitlines():
        if line.startswith(label + " "):
            return line[len(label):].strip()
    return None


def amount(text: str) -> str:
    return text.replace(",", "")


class ReaderDriver:
    """Follows NEXT. Asks the person for facts only the person knows, reads the rest from the documents."""

    name = "reader"

    def __init__(self, misread: dict | None = None):
        self.misread = dict(misread or {})  # {fact: wrong value} written once on purpose, to test the checks
        self.asked: tuple[str, str] | None = None  # (fact, NEXT template) put to the person
        self.reading: tuple[str, str] | None = None  # (fact, NEXT template) whose document is being read
        self.n = 0

    def call(self, name: str, **arguments) -> dict:
        self.n += 1
        return {"content": "", "tool_calls": [{"id": f"r{self.n}", "name": name, "arguments": arguments}]}

    def chat(self, messages: list[dict], tools: list[dict] | None) -> dict:
        last = messages[-1]
        if last["role"] == "user":
            if self.asked:
                fact, template = self.asked
                self.asked = None
                return self.answer(fact, template, last["content"])
            if len(messages) <= 2:
                return self.call("bash", command="caesar status")
            return {"content": "Done.", "tool_calls": []}
        out = last["content"]
        if self.reading:
            fact, template = self.reading
            self.reading = None
            return self.fill(fact, template, self.value_from_doc(fact, out), out)
        step = last_next(out)
        if step is None:
            return {"content": "I could not find caesar's NEXT line.", "tool_calls": []}
        if step == "none":
            return {"content": "caesar has finished: " + out.strip(), "tool_calls": []}
        words = step.split("\n", 1)[0].split()
        if words[-1] == "confirm":
            return self.call("caesar_confirm", job=shlex.split(step)[2])
        at = words.index("set") if "set" in words else -1
        if 0 < at < len(words) - 1 and HOLE.search(step):
            fact = words[at + 1]
            self.asked = (fact, step)
            question = re.search(r"Ask the person: (.*)", out)
            return {"content": question.group(1) if question else f"What is the right value for {fact}?",
                    "tool_calls": []}
        return self.call("bash", command=step)

    def answer(self, fact: str, template: str, said: str) -> dict:
        doc = re.search(r"documents/(\S+)", said)
        if doc:
            self.reading = (fact, template)
            return self.call("bash", command=f"cat documents/{doc.group(1)}")
        fixed = re.search(r"right amount for \S+ is (\S+?)\. Use", said)
        if fixed:
            value = fixed.group(1)
        elif fact == "filing_status":
            value = said.split("is ", 1)[1].split()[0]
        else:
            value = said.strip().rstrip(".")
            value = value.lower() if value.lower() in ("yes", "no") else value
        return self.fill(fact, template, value, None)

    def value_from_doc(self, fact: str, doc: str) -> str:
        parts = fact.split(".")
        if parts[0] == "business":
            key = parts[2]
            if key == "other_expenses":
                total = sum(float(amount(line.rsplit(None, 1)[1])) for line in doc.splitlines()
                            if line.startswith("Other expense"))
                return f"{total:.2f}"
            return amount(read_label(doc, D.BUSINESS_LABELS[key]) or "0")
        labels = PREFIX[parts[0]][1]
        box = parts[2]
        if box == "other_boxes":
            other = {"int1099": "box2", "div1099": "box2a"}[parts[0]]
            return "yes" if float(amount(read_label(doc, labels[other]) or "0")) else "no"
        raw = read_label(doc, labels[box]) or "0"
        if box == "box12":
            return "none" if raw == "(empty)" else raw
        if box == "box13_statutory":
            return "yes" if raw == "X" else "no"
        return raw if box in ("employer", "payer") else amount(raw)

    def fill(self, fact: str, template: str, value: str, doc: str | None) -> dict:
        value = self.misread.pop(fact, value)
        parts = fact.split(".")
        if doc is None:
            source = "answer"
        elif parts[0] == "business":
            source = f"business {parts[1]} records"
        else:
            who = read_label(doc, "c Employer's name") or read_label(doc, "PAYER'S name") or "document"
            source = f"{PREFIX[parts[0]][0]} from {who}, {parts[2].replace('box', 'box ')}"
        texts = iter([value, source])
        return self.call("bash", command=HOLE.sub(lambda m: next(texts), template))


def make(kind: str, model: str = "", base_url: str = "", temperature: float | None = None,
         max_tokens: int | None = None, reasoning_effort: str | None = None):
    if kind == "openai":
        return OpenAIDriver(model, base_url, temperature, max_tokens=max_tokens, reasoning_effort=reasoning_effort)
    if kind == "claude":
        return ClaudeDriver(model or None)
    if kind == "reader":
        return ReaderDriver()
    raise ValueError(f"no driver named {kind}")
