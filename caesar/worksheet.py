"""worksheet.html: the show-your-work page.

One static file with no script. Every string from a fact, a document or the year file is
HTML escaped, and the Content-Security-Policy meta blocks every load but inline style, so a
hostile string in a payer name can neither run nor reach the network.
"""

from __future__ import annotations

from html import escape

from .facts import sort_key
from .yeardata import YearData

CSP = "default-src 'none'; style-src 'unsafe-inline'"

STYLE = """
:root { color-scheme: light dark; --bg: #fafafa; --fg: #1d1d1f; --muted: #5f6368; --line: #d6d6d6; --card: #ffffff; --warn: #8a4b00; --warn-bg: #fff4e0; }
@media (prefers-color-scheme: dark) { :root { --bg: #161616; --fg: #ececec; --muted: #a8a8a8; --line: #3a3a3a; --card: #1f1f1f; --warn: #ffcf8a; --warn-bg: #3a2a10; } }
* { box-sizing: border-box; }
body { margin: 0; padding: 16px; background: var(--bg); color: var(--fg); font: 15px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 960px; margin: 0 auto; }
h1 { font-size: 1.4rem; margin: 0 0 4px; }
h2 { font-size: 1.1rem; margin: 28px 0 8px; }
.banner { background: var(--warn-bg); color: var(--warn); border: 1px solid var(--warn); border-radius: 6px; padding: 8px 12px; font-weight: 600; margin: 12px 0; }
.muted { color: var(--muted); }
.row { background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 10px 12px; margin: 8px 0; display: grid; grid-template-columns: 7rem 1fr 7rem; gap: 4px 12px; }
.row .id { font-weight: 600; font-variant-numeric: tabular-nums; }
.row .result { text-align: right; font-weight: 600; font-variant-numeric: tabular-nums; }
.row .detail { grid-column: 2 / 4; }
.row ul { margin: 4px 0; padding-left: 18px; }
a { color: inherit; }
code { font-size: 0.9em; overflow-wrap: anywhere; }
li, p { overflow-wrap: anywhere; }
@media (max-width: 600px) {
  .row { grid-template-columns: 1fr auto; }
  .row .label { grid-column: 1 / 3; grid-row: 2; }
  .row .detail { grid-column: 1 / 3; }
}
"""


def dollars(value: int) -> str:
    return f"-${-value:,}" if value < 0 else f"${value:,}"


def render(ret_doc: dict, facts: dict, year: YearData, banner: str) -> str:
    e = escape
    parts = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        f'<meta http-equiv="Content-Security-Policy" content="{e(CSP)}">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>Tax worksheet {year.year}</title>",
        f"<style>{STYLE}</style></head><body><main>",
        f"<h1>Form 1040 worksheet, tax year {year.year}</h1>",
        f'<p class="banner">{e(banner)}</p>',
        f"<p>State: <strong>{e(ret_doc['state'])}</strong>. caesar never files, signs, sends or pays. "
        "Each row shows the inputs, the rule in plain words, where the rule comes from, and the result.</p>",
    ]

    findings = ret_doc.get("check", {})
    for title, key in (("Stops (outside v0)", "refusals"), ("Checks that failed", "failures")):
        items = findings.get(key, [])
        if items:
            parts.append(f"<h2>{e(title)}</h2><ul>")
            parts += [f"<li>{e(item['message'])}</li>" for item in items]
            parts.append("</ul>")
    if findings.get("unconfirmed"):
        parts.append(f"<h2>Not confirmed by the person</h2><p class=\"muted\">{len(findings['unconfirmed'])} facts are not confirmed.</p>")

    parts.append("<h2>Lines</h2>")
    for line in ret_doc["lines"]:
        cite = line["citation"]
        inputs = []
        for item in line["inputs"]:
            text = f"{item['name']} = {item['value']}"
            if item.get("source"):
                text += f" (source: {item['source']})"
            inputs.append(f"<li><code>{e(text)}</code></li>")
        parts.append(
            '<section class="row">'
            f'<div class="id">{e(line["id"])}</div>'
            f'<div class="label">{e(line["label"])}</div>'
            f'<div class="result">{e(dollars(line["value"]) if line["money"] else str(line["value"]))}</div>'
            '<div class="detail">'
            f"<div>Rule: {e(line['rule'])}</div>"
            + (f"<div>Inputs:</div><ul>{''.join(inputs)}</ul>" if inputs else "")
            + f'<div class="muted">Source: <a href="{e(cite["url"], quote=True)}">{e(cite["source"])}</a>'
            f" ({e(cite['revision'])}), {e(cite['at'])}</div>"
            "</div></section>"
        )

    parts.append("<h2>Facts</h2>")
    for name in sorted(facts, key=sort_key):
        entry = facts[name]
        state = {"yes": "confirmed", "no": "rejected by the person"}.get(entry["confirmed"], "not confirmed")
        if entry["confirmed"] and entry.get("by"):
            state += f" ({entry['by']})"
        parts.append(f"<p><code>{e(name)} = {e(entry['value'])}</code><br>"
                     f'<span class="muted">Source: {e(entry["source"])}. {e(state)}.</span></p>')
    parts.append(f'<p class="banner">{e(banner)}</p></main></body></html>')
    return "\n".join(parts) + "\n"

