"""The ledger key: 32 random bytes kept in the OS keychain through the platform's own tool.

- macOS: the login keychain through /usr/bin/security, a generic password with service
  UntoCaesar and account ledger-key. The key goes in on stdin (security -i), never in argv.
- Linux: the Secret Service through secret-tool, attributes service UntoCaesar and account
  ledger-key, when secret-tool is installed and a keyring answers.
- Windows: DPAPI for the current user through Windows PowerShell. The protected blob lives in
  %LOCALAPPDATA%/UntoCaesar/ledger-key.dpapi, readable only by this Windows user's DPAPI key.

The item holds only the ledger key. When no keychain answers there is no key, so nothing is
signed and every fact stays unconfirmed (docs/SPEC.md). The key is never printed or logged.
"""

from __future__ import annotations

import base64
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

SERVICE = "UntoCaesar"
ACCOUNT = "ledger-key"
_cache: dict[str, bytes] = {}

PROTECT = ("Add-Type -AssemblyName System.Security; "
           "$d = [Convert]::FromBase64String([Console]::In.ReadToEnd().Trim()); "
           "$o = [Security.Cryptography.ProtectedData]::{op}($d, $null, 'CurrentUser'); "
           "[Console]::Out.Write([Convert]::ToBase64String($o))")


class NoKeychain(Exception):
    pass


def run(argv: list[str], data: str = "", timeout: int = 20) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(argv, input=data.encode(), capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise NoKeychain(f"{Path(argv[0]).name} did not answer ({type(error).__name__})") from None


def parse(text: str) -> bytes | None:
    text = text.strip()
    if len(text) != 64:
        return None
    try:
        return bytes.fromhex(text)
    except ValueError:
        return None


def mac_read(service: str) -> bytes | None:
    done = run(["/usr/bin/security", "find-generic-password", "-s", service, "-a", ACCOUNT, "-w"])
    return parse(done.stdout.decode(errors="replace")) if done.returncode == 0 else None


def mac_write(service: str, key: str) -> None:
    run(["/usr/bin/security", "-i"], f"add-generic-password -U -s {service} -a {ACCOUNT} -w {key}\n")


def linux_tool() -> str:
    tool = shutil.which("secret-tool")
    if not tool:
        raise NoKeychain("secret-tool is not installed, so there is no keychain")
    return tool


def linux_read(service: str) -> bytes | None:
    done = run([linux_tool(), "lookup", "service", service, "account", ACCOUNT])
    return parse(done.stdout.decode(errors="replace")) if done.returncode == 0 else None


def linux_write(service: str, key: str) -> None:
    done = run([linux_tool(), "store", f"--label={service} ledger key", "service", service, "account", ACCOUNT], key)
    if done.returncode != 0:
        raise NoKeychain("no keyring answered secret-tool")


def dpapi_file(service: str) -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        raise NoKeychain("LOCALAPPDATA is not set")
    return Path(base) / SERVICE / f"{service}.dpapi"


def dpapi(op: str, data: str) -> str:
    done = run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", PROTECT.format(op=op)], data, 60)
    if done.returncode != 0:
        raise NoKeychain("Windows PowerShell could not use DPAPI")
    return done.stdout.decode(errors="replace")


def win_read(service: str) -> bytes | None:
    path = dpapi_file(service)
    if not path.exists():
        return None
    plain = base64.b64decode(dpapi("Unprotect", path.read_text(encoding="ascii")))
    return parse(plain.decode(errors="replace"))


def win_write(service: str, key: str) -> None:
    path = dpapi_file(service)
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = dpapi("Protect", base64.b64encode(key.encode()).decode())
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(blob, encoding="ascii")
    tmp.replace(path)


def backend():
    if sys.platform == "darwin":
        return mac_read, mac_write
    if sys.platform.startswith("linux"):
        return linux_read, linux_write
    if sys.platform == "win32":
        return win_read, win_write
    raise NoKeychain(f"caesar knows no keychain on {sys.platform}")


def load_key(create: bool, service: str = SERVICE) -> tuple[bytes | None, str]:
    """(key, "") or (None, why). With create, make the key when the keychain has none yet."""
    if service in _cache:
        return _cache[service], ""
    try:
        read, write = backend()
        key = read(service)
        if key is None and create:
            write(service, secrets.token_hex(32))
            key = read(service)
            if key is None:
                return None, "the keychain did not keep the ledger key"
    except (NoKeychain, OSError, ValueError) as error:
        return None, str(error)
    if key is None:
        return None, "the keychain has no ledger key yet"
    _cache[service] = key
    return key, ""
