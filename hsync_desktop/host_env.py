# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Environment for host tools spawned by the frozen payload.

PyInstaller points the process at the bundled libraries: ``LD_LIBRARY_PATH``
(the AppImage loader does the same) plus, depending on the bundle,
``PYTHONHOME``/``PYTHONPATH``, ``GI_TYPELIB_PATH`` and
``GDK_PIXBUF_MODULE_FILE``. A host binary that is *not* part of the bundle then
loads the bundled GLib/GIO instead of the system ones and dies at dynamic-link
time as soon as the host is newer than the bundle — ``gsettings`` cannot read
the host schemas and ``gio trash`` aborts with ``symbol lookup error`` and exit
status 127.

Every spawn of a host tool (``gsettings``, ``gio``, …) must therefore use
:func:`host_env`, so the child sees the system libraries it was built against.
"""

from __future__ import annotations

import os

# Overrides that redirect a child process to the PyInstaller/AppImage libraries.
LIBRARY_ENV_KEYS = (
    "LD_LIBRARY_PATH",
    "PYTHONHOME",
    "PYTHONPATH",
    "GI_TYPELIB_PATH",
    "GDK_PIXBUF_MODULE_FILE",
)


def host_env() -> dict[str, str]:
    """Return the process environment without the bundled-library overrides."""
    env = os.environ.copy()
    for key in LIBRARY_ENV_KEYS:
        env.pop(key, None)
    return env
