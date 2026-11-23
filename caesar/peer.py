"""Whether a process is the installed Local Studio app, by the path of its executable.

caesar-mcp sends its question token only to a socket peer that is LOCAL_STUDIO_ASK_PID and whose
executable is the installed app (docs/SPEC.md). The installed paths are the ones Local Studio's
own updater uses (local-studio core/src/update/apply.rs, install_path, and channel_name in
core/src/update/mod.rs):

- macOS: /Applications/<name>.app, or ~/Applications/<name>.app, where <name> is Local Studio,
  Local Studio Nightly or Local Studio Dev; the executable is Contents/MacOS/LocalStudio
  (macos/LocalStudio-Info.plist).
- Linux: ~/.local/lib/<slug>/local-studio, where <slug> is local-studio, local-studio-nightly or
  local-studio-dev.
- Windows and anything else: Local Studio has no installed path there, and its question socket is
  Unix only (core/src/plugins/ask.rs), so no peer passes.

Home comes from the password database, not HOME, so a launcher cannot point it elsewhere. Any
lookup that fails means not the app.
"""

from __future__ import annotations

import ctypes
import os
import sys

CHANNEL_NAMES = ("Local Studio", "Local Studio Nightly", "Local Studio Dev")
LINUX_SLUGS = ("local-studio", "local-studio-nightly", "local-studio-dev")


def home() -> str | None:
    try:
        import pwd
        return pwd.getpwuid(os.getuid()).pw_dir
    except (ImportError, KeyError, AttributeError):
        return None


def installed_apps() -> list[str]:
    """The real paths of the installed app's executable on this system, for every channel."""
    found = []
    user = home()
    if sys.platform == "darwin":
        roots = ["/Applications"] + ([os.path.join(user, "Applications")] if user else [])
        found = [os.path.join(root, f"{name}.app", "Contents", "MacOS", "LocalStudio")
                 for root in roots for name in CHANNEL_NAMES]
    elif sys.platform.startswith("linux") and user:
        found = [os.path.join(user, ".local", "lib", slug, "local-studio") for slug in LINUX_SLUGS]
    return [os.path.realpath(path) for path in found if os.path.isfile(path)]


def exe_of(pid: int) -> str | None:
    """The path of the executable process pid runs, or None when it cannot be read."""
    try:
        if sys.platform.startswith("linux"):
            return os.readlink(f"/proc/{pid}/exe")
        if sys.platform == "darwin":
            libproc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
            buf = ctypes.create_string_buffer(4096)  # PROC_PIDPATHINFO_MAXSIZE
            size = libproc.proc_pidpath(ctypes.c_int(pid), buf, ctypes.c_uint32(len(buf)))
            return os.fsdecode(buf.value) if size > 0 else None
        if sys.platform == "win32":
            from ctypes import wintypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.restype = wintypes.HANDLE
            handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not handle:
                return None
            try:
                buf = ctypes.create_unicode_buffer(32768)
                size = wintypes.DWORD(len(buf))
                if not kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                    return None
                return buf.value
            finally:
                kernel32.CloseHandle(handle)
    except (OSError, AttributeError, ValueError):
        return None
    return None


def is_installed_app(pid: int) -> tuple[bool, str]:
    """(True, "") when pid runs the installed app, else (False, why)."""
    apps = installed_apps()
    if not apps:
        return False, "no installed Local Studio app was found on this computer"
    exe = exe_of(pid)
    if not exe:
        return False, f"could not read the executable of process {pid}"
    if os.path.realpath(exe) not in apps:
        return False, f"process {pid} runs {exe}, which is not the installed Local Studio app"
    return True, ""
