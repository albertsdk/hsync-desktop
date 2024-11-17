#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Compile Qt Designer .ui files to Python modules.

This script converts all .ui files in hsync_desktop/ui/ to Python modules
using pyside6-uic. The generated files are named ui_<original_name>.py.

Usage:
    python scripts/compile_ui.py [--watch]

Options:
    --watch     Watch for changes and recompile automatically

Requirements:
    - PySide6 must be installed (provides pyside6-uic)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
UI_DIR = PROJECT_ROOT / "hsync_desktop" / "ui"
RESOURCES_DIR = PROJECT_ROOT / "hsync_desktop" / "resources"


def compile_ui_file(ui_path: Path) -> bool:
    """Compile a single .ui file to Python.
    
    Args:
        ui_path: Path to the .ui file.
    
    Returns:
        True if compilation succeeded, False otherwise.
    """
    output_name = f"ui_{ui_path.stem}.py"
    output_path = ui_path.parent / output_name
    
    cmd = ["pyside6-uic", str(ui_path), "-o", str(output_path)]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  ✅ {ui_path.name} → {output_name}")
            return True
        else:
            print(f"  ❌ {ui_path.name}: {result.stderr.strip()}")
            return False
    except FileNotFoundError:
        print("  ❌ pyside6-uic not found. Install PySide6: pip install PySide6")
        return False


def compile_qrc_file(qrc_path: Path) -> bool:
    """Compile a .qrc resource file to Python.
    
    Args:
        qrc_path: Path to the .qrc file.
    
    Returns:
        True if compilation succeeded, False otherwise.
    """
    output_name = f"{qrc_path.stem}_rc.py"
    output_path = qrc_path.parent / output_name
    
    cmd = ["pyside6-rcc", str(qrc_path), "-o", str(output_path)]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  ✅ {qrc_path.name} → {output_name}")
            return True
        else:
            print(f"  ❌ {qrc_path.name}: {result.stderr.strip()}")
            return False
    except FileNotFoundError:
        print("  ❌ pyside6-rcc not found. Install PySide6: pip install PySide6")
        return False


def compile_all() -> int:
    """Compile all .ui and .qrc files.
    
    Returns:
        Number of files that failed to compile.
    """
    failures = 0
    
    # Compile .ui files
    ui_files = list(UI_DIR.glob("*.ui"))
    if ui_files:
        print(f"\n📦 Compiling {len(ui_files)} .ui files...")
        for ui_file in sorted(ui_files):
            if not compile_ui_file(ui_file):
                failures += 1
    else:
        print("\n⚠️  No .ui files found in", UI_DIR)
    
    # Compile .qrc files
    qrc_files = list(RESOURCES_DIR.glob("*.qrc"))
    if qrc_files:
        print(f"\n📦 Compiling {len(qrc_files)} .qrc files...")
        for qrc_file in sorted(qrc_files):
            if not compile_qrc_file(qrc_file):
                failures += 1
    
    return failures


def watch_and_compile() -> None:
    """Watch for file changes and recompile."""
    print("\n👀 Watching for changes... (Ctrl+C to stop)")
    
    # Track file modification times
    mtimes: dict[Path, float] = {}
    
    def get_files() -> list[Path]:
        return list(UI_DIR.glob("*.ui")) + list(RESOURCES_DIR.glob("*.qrc"))
    
    # Initial scan
    for f in get_files():
        mtimes[f] = f.stat().st_mtime
    
    try:
        while True:
            time.sleep(1)
            for f in get_files():
                if not f.exists():
                    continue
                mtime = f.stat().st_mtime
                if f not in mtimes or mtime > mtimes[f]:
                    print(f"\n🔄 {f.name} changed, recompiling...")
                    if f.suffix == ".ui":
                        compile_ui_file(f)
                    elif f.suffix == ".qrc":
                        compile_qrc_file(f)
                    mtimes[f] = mtime
    except KeyboardInterrupt:
        print("\n\n👋 Stopped watching.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile Qt Designer .ui files to Python modules."
    )
    parser.add_argument(
        "--watch", "-w",
        action="store_true",
        help="Watch for changes and recompile automatically"
    )
    args = parser.parse_args()
    
    print("🔧 HSYNC Desktop UI Compiler")
    print("=" * 40)
    
    failures = compile_all()
    
    if args.watch:
        watch_and_compile()
    
    if failures:
        print(f"\n⚠️  {failures} file(s) failed to compile.")
        return 1
    else:
        print("\n✅ All files compiled successfully!")
        return 0


if __name__ == "__main__":
    sys.exit(main())

