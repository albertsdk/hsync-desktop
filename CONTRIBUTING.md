# Contributing to hsync-desktop

Thanks for your interest in contributing! This guide covers the development
workflow for the HSYNC desktop GUI (PySide6).

## Prerequisites

- Python `>=3.12,<3.15` (lint/CI target: **3.13**)
- A committed virtualenv at `.venv/` (no Poetry required)
- A checkout of [`hsync-common`](../hsync-common) as a **sibling directory**
  (declared as a Poetry path dependency)

## Setup

The project ships a committed virtualenv at `.venv/`. All tooling is invoked
through it as `.venv/bin/python -m <tool>` — exactly as the root `Makefile`
does. No Poetry installation is required.

## Running

```bash
.venv/bin/python -m hsync_desktop
```

## Building the Binary

```bash
./compile.sh                    # native host binary (PyInstaller onefile)
./compile.sh --clean            # clean and rebuild
./compile.sh --target deb       # Debian/Ubuntu .deb for the host arch
./compile.sh --target deb-all   # .deb for amd64 + arm64 (Docker + qemu)
./compile.sh --target rpi       # Raspberry Pi OS 64-bit (arm64) via Docker
./compile.sh --target windows   # Windows x64 installer + portable zip
```

The native build bundles the `hsync` client binary from
`../hsync-client/dist/<os>-<arch>/hsync[.exe]` when present. The `rpi` target
cross-builds arm64 only and requires Docker with `qemu-user-static` (binfmt)
configured; run `./compile.sh --help` for the full option list. PySide6 publishes
no armv7 Linux wheels, so 32-bit Raspberry Pi OS (armhf) is not supported for the
GUI.

The `windows` target builds the per-user Inno Setup installer and a portable
`.zip` for **x64** Windows 10 (version 1809 or later) or Windows 11; it runs on an
x64 Windows host and needs Inno Setup 6 (`ISCC`) and ImageMagick.

The `deb` target builds `dist/deb/hsync-desktop_<ver>_<arch>.deb` for the host
architecture (needs `dpkg-deb`); `deb-all` cross-builds amd64 + arm64 inside
Docker. The package installs the GUI under `/usr/lib/hsync-desktop` with a
`.desktop` launcher and icons, and bundles the `hsync` client engine so it is
self-contained; see [docs/README.md](docs/README.md).

## Code Style

This project uses [ruff](https://docs.astral.sh/ruff/) for linting and
formatting (line length 100, target `py313`), enforced via pre-commit hooks.

```bash
.venv/bin/python -m ruff check --fix .
.venv/bin/python -m ruff format .
```

## Pre-commit Workflow

Pre-commit hooks run ruff (and an end-of-file fixer) on commit. When a hook
auto-fixes files, the commit aborts because files changed — **this is expected,
not a failure**. Re-stage and commit again:

```bash
.venv/bin/python -m ruff check --fix .
.venv/bin/python -m ruff format .
git add -A
git commit -m "type(scope): message"
# if hooks modified files and the commit aborted, re-stage and retry:
git add -A
git commit -m "type(scope): message"
```

## Tests & Type Checking

GUI tests use pytest-qt and need a display: always set
`QT_QPA_PLATFORM=offscreen` (this is what `make test-python` does).

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest
.venv/bin/python -m mypy hsync_desktop
```

## Documentation

HSYNC maintains two documentation sets that must stay in sync with the code:

- `llm-wiki/` — internal agent knowledge base (architecture, modules, data models)
- `docs/` — end-user technical documentation

Any change that affects architecture, contracts, configuration, or behavior
must update the relevant files in both sets within the same change.

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):
`type(scope): summary` (`feat`, `fix`, `docs`, `refactor`, `test`, `chore`, …).

## Pull Requests

- Keep changes focused and covered by tests.
- Ensure `ruff`, `pytest` and `mypy` pass locally before opening a PR.
