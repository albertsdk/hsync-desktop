# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Startup benchmark for hsync-desktop (GUI import + binary probes).

Measures the two costs that dominated the pre-optimization startup path:

* ``desktop_import_main`` — cold ``import hsync_desktop.main`` (PySide6 + app
  modules) in a fresh process;
* ``desktop_version_probe`` / ``desktop_capabilities_probe`` — the raw
  subprocess wall-clock of ``<bundled-hsync> --version`` /
  ``--capabilities-json``, i.e. what ``engine.get_binary_version`` /
  ``engine.get_binary_capabilities`` pay before the QSettings cache.

After the cache was introduced (engine, ADR-00XX), a cache **hit** is a QSettings
read (no subprocess), so it is effectively zero compared to these figures; only
the first launch after a binary change pays the probe cost measured here.

Standalone script, not collected by pytest. Comparative figures for this
machine, not SLAs.

Usage:
    cd hsync-desktop && .venv/bin/python bench/bench_startup.py --count 30
    .venv/bin/python bench/bench_startup.py --count 30 --json-out /tmp/desktop.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_VERSION_RE = re.compile(r"hsync \d+\.\d+\.\d+")


def _platform_tag() -> str:
    system = platform.system().lower()
    if system.startswith("mingw") or system.startswith("cygwin") or system.startswith("msys"):
        system = "windows"
    machine = platform.machine().lower()
    arch_map = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "aarch64": "arm64",
        "arm64": "arm64",
        "armv7l": "armv7",
        "armv7": "armv7",
        "i386": "x86",
        "i686": "x86",
    }
    return f"{system}-{arch_map.get(machine, machine)}"


def _default_binary() -> str | None:
    bin_name = "hsync.exe" if sys.platform == "win32" else "hsync"
    pkg_dir = _PROJECT_ROOT / "hsync_desktop"
    candidates = [
        pkg_dir / "bin" / bin_name,
        _PROJECT_ROOT.parent / "hsync-client" / "dist" / _platform_tag() / bin_name,
    ]
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def _clean_env() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("HSYNC_")}
    env["NO_COLOR"] = "1"
    return env


def _run(cmd: list[str], check: Callable[[str], bool], timeout: int) -> str | None:
    """Run ``cmd``; return None on success or an error message otherwise."""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_clean_env(),
            cwd=str(_PROJECT_ROOT),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"{cmd} failed: {exc}"
    output = f"{proc.stdout}\n{proc.stderr}"
    if proc.returncode != 0:
        return f"{cmd} exited {proc.returncode}: {output[-200:]}"
    if not check(output):
        return f"{cmd} output check failed: {output[-200:]}"
    return None


def _scenarios(
    python: str, binary: str | None
) -> list[tuple[str, list[str], Callable[[str], bool], int]]:
    scenarios: list[tuple[str, list[str], Callable[[str], bool], int]] = [
        ("desktop_import_main", [python, "-c", "import hsync_desktop.main"], lambda _o: True, 60),
    ]
    if binary is not None:
        scenarios += [
            (
                "desktop_version_probe",
                [binary, "--version"],
                lambda o: bool(_VERSION_RE.search(o)),
                60,
            ),
            (
                "desktop_capabilities_probe",
                [binary, "--capabilities-json"],
                lambda o: '"schema_version"' in o,
                60,
            ),
        ]
    return scenarios


def _measure(name: str, op: Callable[[], str | None], count: int) -> dict[str, float] | None:
    samples: list[float] = []
    error = op()  # warm-up (prime the page cache)
    if error is not None:
        print(f"{name:28} SKIPPED — {error}")
        return None
    for _ in range(count):
        start = time.perf_counter()
        error = op()
        if error is not None:
            print(f"{name:28} SKIPPED — {error}")
            return None
        samples.append((time.perf_counter() - start) * 1000.0)
    return {
        "name": name,
        "mean_ms": statistics.fmean(samples),
        "p50_ms": statistics.median(samples),
        "p99_ms": max(samples),
        "stdev_ms": statistics.pstdev(samples),
        "min_ms": min(samples),
        "max_ms": max(samples),
        "n": count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument(
        "--binary", default=None, help="Bundled hsync binary (default: auto-detect)."
    )
    parser.add_argument("--no-binary", action="store_true", help="Skip the binary probe scenarios.")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    binary = (
        args.binary if args.binary is not None else (None if args.no_binary else _default_binary())
    )

    print(f"hsync-desktop startup benchmark — count={args.count} — {platform.system().lower()}")
    print("comparative figures (this machine, warm page cache), not SLAs\n")

    results = []
    for name, cmd, check, timeout in _scenarios(args.python, binary):
        measured = _measure(
            name,
            lambda cmd=cmd, check=check, timeout=timeout: _run(cmd, check, timeout),
            args.count,
        )
        if measured is not None:
            results.append(measured)

    header = f"{'scenario':28} {'mean_ms':>10} {'p50_ms':>10} {'p99_ms':>10} {'stdev_ms':>10}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r['name']:28} {r['mean_ms']:10.2f} {r['p50_ms']:10.2f} {r['p99_ms']:10.2f} {r['stdev_ms']:10.2f}"
        )

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
