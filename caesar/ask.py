"""Ask the person one question through Local Studio's question card.

This is the one module in caesar that opens a socket, and only the Unix socket Local Studio names
in LOCAL_STUDIO_ASK (local-studio docs/plugins.md, "Questions from plugins"). Before it sends its
token it checks that the peer is LOCAL_STUDIO_ASK_PID and that this process runs the installed
Local Studio app (peer.py). Any other outcome is a refusal, which caesar treats as not confirmed.
"""

from __future__ import annotations

import json
import os
import socket
import struct
import sys

from . import peer

# The socket path, the plugin's question token and the pid of the Local Studio that owns the socket.
ASK_VARS = ("LOCAL_STUDIO_ASK", "LOCAL_STUDIO_ASK_TOKEN", "LOCAL_STUDIO_ASK_PID")
THREAD_VAR = "LOCAL_STUDIO_THREAD"
MAX_REPLY = 64 * 1024
WAIT = 600  # seconds the person has to answer before caesar gives up on the card


def available() -> bool:
    return all(os.environ.get(name) for name in ASK_VARS)


def peer_pid(conn) -> int:
    if sys.platform == "darwin":
        return struct.unpack("i", conn.getsockopt(0, 2, 4))[0]  # SOL_LOCAL, LOCAL_PEERPID
    if sys.platform.startswith("linux"):
        return struct.unpack("3i", conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[0]
    raise OSError("this system cannot tell who serves the question socket")


def refused(error: str) -> dict:
    return {"status": "refused", "error": error}


def ask(text: str, choices: list[str]) -> dict:
    """{"status": "answered", "answer": ...}, {"status": "cancelled"} or {"status": "refused", "error": ...}."""
    path, key, pid = (os.environ.get(name) for name in ASK_VARS)
    if not (path and key and pid):
        return refused("not running under Local Studio, so there is no question card")
    try:
        want = int(pid)
    except ValueError:
        return refused("LOCAL_STUDIO_ASK_PID is not a process id")
    unix = getattr(socket, "AF_UNIX", None)
    if unix is None:
        return refused("this system has no Unix sockets, so there is no question card")
    conn = socket.socket(unix, socket.SOCK_STREAM)
    try:
        conn.settimeout(5)
        conn.connect(path)
        got = peer_pid(conn)
        if got != want:
            return refused(f"the question socket is served by process {got}, not Local Studio's {want}")
        ok, why = peer.is_installed_app(got)
        if not ok:
            return refused(why)
        request = {"token": key, "text": text, "choices": choices}
        if os.environ.get(THREAD_VAR):
            request["thread"] = os.environ[THREAD_VAR]
        conn.sendall((json.dumps(request) + "\n").encode("utf-8"))
        conn.settimeout(WAIT)
        reply = b""
        while not reply.endswith(b"\n"):
            chunk = conn.recv(4096)
            if not chunk:
                return {"status": "cancelled"}
            reply += chunk
            if len(reply) > MAX_REPLY:
                return refused("the reply was too long")
        answer = json.loads(reply)
    except (OSError, ValueError) as error:
        return refused(str(error))
    finally:
        conn.close()
    if not isinstance(answer, dict) or answer.get("status") not in ("answered", "cancelled", "refused"):
        return refused("the reply was not a question card answer")
    if answer["status"] == "answered" and not isinstance(answer.get("answer"), str):
        return refused("the answer was not text")
    return answer
