"""caesar/ and bin/ import nothing that can reach the network, and nothing outside the standard library."""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "caesar"
BANNED = {"socket", "urllib", "http", "ssl", "ftplib", "smtplib", "poplib", "imaplib", "nntplib", "telnetlib",
          "xmlrpc", "socketserver", "asyncio", "webbrowser", "wsgiref", "email", "mailbox", "selectors", "select",
          "multiprocessing", "ctypes"}


def imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            yield node.module.split(".")[0]
        elif isinstance(node, ast.Call) and getattr(node.func, "id", "") == "__import__":
            yield "__import__"


def test_no_network_or_third_party_imports():
    files = sorted(PACKAGE.rglob("*.py")) + sorted(p for p in (ROOT / "bin").iterdir() if p.is_file())
    assert len(files) > 2
    found = {}
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        for name in imports(path):
            if name == "caesar":
                continue
            if name in BANNED or name == "__import__" or name not in sys.stdlib_module_names:
                found.setdefault(rel, []).append(name)
    assert not found, f"forbidden imports: {found}"


def test_the_check_catches_a_banned_import(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("import socket\nfrom urllib import request\nimport requests\n", encoding="utf-8")
    names = list(imports(bad))
    assert [n for n in names if n in BANNED or n not in sys.stdlib_module_names] == ["socket", "urllib", "requests"]
