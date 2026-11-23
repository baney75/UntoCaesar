"""The confirmation ledger: <job>/ledger.json, beside facts.toml.

Each entry records one answer the person gave about one fact: the job, the fact, the value and
source they were shown, their answer (yes or no) and who answered, signed with HMAC-SHA256 under
the ledger key (keystore.py). A fact counts as confirmed or rejected only when a valid entry
covers its current value and source; the newest such entry wins. Whatever facts.toml says about
confirmation is ignored. A missing, unreadable or forged ledger, or no key, means every fact is
unconfirmed, never an error.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
from pathlib import Path

from . import keystore

NAME = "ledger.json"


def signed(key: bytes, job_id: str, fact: str, value: str, source: str, answer: str, by: str) -> str:
    body = json.dumps([job_id, fact, value, source, answer, by], ensure_ascii=False, separators=(",", ":"))
    return hmac.new(key, body.encode("utf-8"), hashlib.sha256).hexdigest()


def entries(path: Path) -> list:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    found = data.get("entries") if isinstance(data, dict) else None
    return found if isinstance(found, list) else []


def apply(facts: dict, job_dir: Path, job_id: str) -> None:
    """Set each fact's confirmed and by from the ledger alone."""
    for entry in facts.values():
        entry["confirmed"], entry["by"] = "", ""
    path = job_dir / NAME
    if not job_id or not path.exists():
        return
    key, _ = keystore.load_key(create=False)
    if key is None:
        return
    for e in entries(path):
        try:
            fact, value, source, answer, by, mac = (e[k] for k in ("fact", "value", "source", "answer", "by", "mac"))
            if not all(isinstance(x, str) for x in (fact, value, source, answer, by, mac)):
                continue
        except (KeyError, TypeError):
            continue
        current = facts.get(fact)
        if (current is None or answer not in ("yes", "no") or (current["value"], current["source"]) != (value, source)
                or not hmac.compare_digest(mac.encode("utf-8", "replace"),  # bytes: a non-ASCII mac is just wrong
                                           signed(key, job_id, fact, value, source, answer, by).encode())):
            continue
        current["confirmed"], current["by"] = answer, by


def record(job_dir: Path, key: bytes, job_id: str, answers: list[tuple[str, dict, str]], by: str) -> None:
    """Append the person's answers: (fact, its entry as shown, "yes" or "no")."""
    path = job_dir / NAME
    kept = entries(path)
    at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    for fact, entry, answer in answers:
        kept.append({"fact": fact, "value": entry["value"], "source": entry["source"], "answer": answer, "by": by,
                     "at": at, "mac": signed(key, job_id, fact, entry["value"], entry["source"], answer, by)})
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({"entries": kept}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)
