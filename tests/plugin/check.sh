#!/usr/bin/env bash
# Check the UntoCaesar plugin tree the way Local Studio loads it, then smoke test caesar.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"
py="${PYTHON:-python3}"
command -v "$py" >/dev/null 2>&1 || py=python

"$py" - <<'PY'
import pathlib, re, tomllib
m = tomllib.loads(pathlib.Path("plugin.toml").read_text(encoding="utf-8"))
allowed = {"id", "version", "description", "skills", "prompts", "commands", "capabilities"}
assert set(m) <= allowed, f"unknown keys: {set(m) - allowed}"
assert m["id"] == "untocaesar", m["id"]
assert m["version"] == "0.1.0", m["version"]
assert "Test build: synthetic cases only, not for real records." in m["description"]
assert m["capabilities"] == ["ask-user"], m["capabilities"]
skills = pathlib.Path(m["skills"])
assert m["skills"] == "skills/plugin", m["skills"]
names = {}
for d in sorted(p for p in skills.iterdir() if p.is_dir()):
    f = d / "SKILL.md"
    assert f.is_file(), f"missing {f}"
    text = f.read_text(encoding="utf-8")
    name = re.search(r"^name:\s*(\S+)", text, re.M).group(1)
    assert name == d.name, f"{f}: name {name} is not the folder name"
    assert re.search(r"^description:\s*\S", text, re.M), f"{f}: no description"
    assert "Test build: synthetic cases only, not for real records." in text, f"{f}: no test build banner"
    assert "local model" in text, f"{f}: no provider check"
    names[name] = f
for f in sorted(skills.iterdir()):
    assert f.is_dir(), f"{f}: only skill folders belong in {skills}"
cmds = {c["name"]: c for c in m["commands"]}
assert set(cmds) == {"taxes", "taxes-explain"}, sorted(cmds)
assert cmds["taxes"]["skill"] == "untocaesar" and cmds["taxes-explain"]["skill"] == "untocaesar-explain", cmds
for c in cmds.values():
    assert set(c) <= {"name", "description", "prompt", "skill"}, c
    assert ("prompt" in c) != ("skill" in c), c
    assert c.get("skill") in names, f"command {c['name']}: missing skill {c.get('skill')}"
for tier in "SML":
    card = skills / "untocaesar" / "tiers" / f"{tier}.md"
    text = card.read_text(encoding="utf-8")
    assert "## Rules" in text and "local model" in text, f"{card}: needs a Rules section with the provider check"
    assert "Never" in text and "file, sign, send or pay" in text, f"{card}: needs the never file, sign, send or pay rule"
s = (skills / "untocaesar" / "tiers" / "S.md").read_text(encoding="utf-8")
steps = re.findall(r"^\d+\. ", s.split("## Steps", 1)[1].split("## ", 1)[0], re.M)
assert 3 <= len(steps) <= 7, f"tier S needs short numbered steps, found {len(steps)}"
print(f"ok   plugin.toml: id untocaesar, skills {sorted(names)}, commands {sorted('/' + n for n in cmds)}, capabilities {m['capabilities']}")

bad = []
for path in sorted(pathlib.Path(".").rglob("*")):
    if path.is_file() and not any(p in path.parts for p in (".git", ".venv", "__pycache__", ".pytest_cache")) \
            and path.suffix in {".py", ".md", ".toml", ".json", ".xml", ".sh", ".yml", ".txt", ".html", ""}:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if chr(0x2013) in text or chr(0x2014) in text:
            bad.append(str(path))
assert not bad, f"em or en dashes in: {bad}"
print("ok   no em or en dashes")
PY

job="$(mktemp -d)/job"
out="$("$py" bin/caesar --job "$job" new)"
echo "$out" | head -1 | grep -qx "Test build: synthetic cases only, not for real records." || { echo "FAIL caesar new: no banner"; exit 1; }
echo "$out" | tail -1 | tr '\\' / | grep -q "^NEXT: .*bin/caesar.* ask$" || { echo "FAIL caesar new: NEXT does not name the launcher: $(echo "$out" | tail -1)"; exit 1; }
out="$(CAESAR_TIER=S "$py" bin/caesar --job "$job" status)"
echo "$out" | grep -q "^Tier S rules:" || { echo "FAIL caesar status: no tier S rules"; exit 1; }
echo "ok   caesar runs from the plugin folder with the standard library only: $(echo "$out" | tail -1 | sed 's/.*caesar[^ ]* //')"

if [ -n "${LOCAL_STUDIO:-}" ]; then
  scratch="$(mktemp -d)/untocaesar"
  mkdir -p "$scratch"
  cp -R plugin.toml skills bin caesar "$scratch"/
  "$LOCAL_STUDIO" plugin validate "$scratch"
fi
