# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Tests for the POSIX ``install.sh`` bootstrap.

The desktop app also ships a Windows installer (``tests/test_windows_installer.py``);
this module only covers the Unix script that release downloads.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = PROJECT_ROOT / "install.sh"


def _restricted_bin(tmp_path: Path, names: tuple[str, ...]) -> Path:
    """A PATH dir holding only the given tools, so a real tool on the runner
    cannot leak into the "tool missing" tests."""
    bin_dir = tmp_path / "restricted-bin"
    bin_dir.mkdir(exist_ok=True)
    for name in names:
        real = shutil.which(name)
        if real is not None:
            (bin_dir / name).symlink_to(real)
    return bin_dir


def _run_installer(
    tmp_path: Path,
    *args: str,
    path_tools: tuple[str, ...] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if path_tools is not None:
        env["PATH"] = str(_restricted_bin(tmp_path, path_tools))
    return subprocess.run(
        [
            str(INSTALL_SCRIPT),
            "--install-dir",
            str(tmp_path / "installation"),
            "--bin-dir",
            str(tmp_path / "bin"),
            *args,
        ],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_help_has_no_runtime_dependencies(tmp_path: Path):
    result = subprocess.run(
        [str(INSTALL_SCRIPT), "--help"],
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Install HSYNC Desktop" in result.stdout


def test_dry_run_creates_nothing(tmp_path: Path):
    result = _run_installer(tmp_path, "--dry-run")

    assert result.returncode == 0, result.stderr
    assert "Dry run" in result.stdout
    assert not (tmp_path / "installation").exists()


# --- Prerequisite guidance ---------------------------------------------------


def test_missing_curl_prints_hint(tmp_path: Path):
    result = _run_installer(tmp_path, path_tools=("bash", "sh", "uname"))

    assert result.returncode == 1
    assert "required command not found: curl" in result.stderr
    assert 'downloads the release archive with "curl"' in result.stderr
    assert "Then re-run:" in result.stderr
    assert "releases/latest/download/install.sh" in result.stderr


def test_missing_tar_prints_hint(tmp_path: Path):
    result = _run_installer(tmp_path, path_tools=("bash", "sh", "uname", "curl"))

    assert result.returncode == 1
    assert "required command not found: tar" in result.stderr
    assert 'extracts the release archive with "tar"' in result.stderr
    assert "Then re-run:" in result.stderr
