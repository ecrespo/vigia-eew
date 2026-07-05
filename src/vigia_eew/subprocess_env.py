"""Environment sanitization for launching *system* binaries as subprocesses.

A PyInstaller **onefile** bundle prepends its extraction dir (`sys._MEIPASS`) to
`LD_LIBRARY_PATH` (Linux) / `DYLD_LIBRARY_PATH` (macOS) so the frozen agent finds
its own bundled shared libraries. That value is inherited by any subprocess, so a
system binary such as `systemctl` ends up loading the bundle's (older) `libcrypto.so`
instead of the system one, failing with a missing versioned symbol
(e.g. ``version `OPENSSL_3.4.0' not found``).

`system_env()` returns an environment to hand to `subprocess.*` when spawning system
binaries (systemctl/launchctl/schtasks/xdg-open/audio players), with the injected
library path **restored to its pre-bundle value or removed** so the OS libraries win.
When not running frozen it returns ``None`` (inherit the environment unchanged), so
source installs and the test suite behave exactly as before.
"""

from __future__ import annotations

import os
import sys

_LIBRARY_PATH_VARS = ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH")


def system_env() -> dict[str, str] | None:
    """Environment for launching system binaries from a PyInstaller onefile bundle.

    Returns ``None`` when not frozen (callers pass it straight to
    ``subprocess.*(env=...)``, which then inherits the current environment).
    """
    if not getattr(sys, "frozen", False):
        return None
    env = dict(os.environ)
    for var in _LIBRARY_PATH_VARS:
        original = env.pop(f"{var}_ORIG", None)
        if original is not None:
            env[var] = original  # restore the value that existed before the bundle
        else:
            env.pop(var, None)  # PyInstaller added it from nothing → drop it entirely
    return env
