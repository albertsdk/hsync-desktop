# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Pure helpers for importing files dropped onto the file list.

Deliberately Qt-free: the drop handler (to pick a cursor) and the import worker
both call these, and they are unit-tested without a ``QApplication``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from hsync_common.path_validation import is_internal_name


@dataclass(frozen=True, slots=True)
class ImportItem:
    """A resolved import: copy or move ``src`` to the absolute ``dest``."""

    src: str
    dest: str
    move: bool


def target_rel_dir(hovered_rel_dir: str | None, current_path: str) -> str:
    """Destination folder, relative to the share root.

    A folder row under the cursor wins; otherwise the folder currently shown.
    """
    if hovered_rel_dir:
        return hovered_rel_dir.strip("/")
    return current_path.strip("/")


def destination_for(base_dir: str, target_rel: str, src_abs: str) -> str:
    """Absolute destination path for ``src_abs`` inside ``target_rel``."""
    name = os.path.basename(os.path.normpath(src_abs))
    if target_rel:
        return os.path.join(base_dir, target_rel, name)
    return os.path.join(base_dir, name)


def unique_name(path: str) -> str:
    """A free path next to ``path``: ``name (1).ext``, ``name (2).ext``, …"""
    if not os.path.exists(path):
        return path
    directory, name = os.path.split(path)
    stem, ext = os.path.splitext(name)
    index = 1
    while True:
        candidate = os.path.join(directory, f"{stem} ({index}){ext}")
        if not os.path.exists(candidate):
            return candidate
        index += 1


def _is_within(parent: str, candidate: str) -> bool:
    """True when ``candidate`` is ``parent`` itself or below it (symlink-safe)."""
    parent_real = os.path.realpath(parent)
    cand_real = os.path.realpath(candidate)
    return cand_real == parent_real or cand_real.startswith(parent_real + os.sep)


def validate_sources(
    base_dir: str, target_rel: str, sources: list[str]
) -> tuple[list[str], list[tuple[str, str]]]:
    """Split the dropped sources into ``(accepted, rejected)``.

    ``rejected`` pairs each source with a reason key: ``missing`` (gone),
    ``internal`` (an engine-managed file, e.g. ``.hsyncfolder``), ``recursive``
    (the share or an ancestor of the destination), ``outside`` (the destination
    resolves outside the share) or ``same`` (it is already the destination).
    """
    accepted: list[str] = []
    rejected: list[tuple[str, str]] = []
    dest_dir = os.path.join(base_dir, target_rel) if target_rel else base_dir
    for raw in sources:
        src = os.path.normpath(raw)
        if not os.path.exists(src):
            rejected.append((src, "missing"))
            continue
        if is_internal_name(os.path.basename(src)):
            rejected.append((src, "internal"))
            continue
        dest = os.path.join(dest_dir, os.path.basename(src))
        if os.path.normpath(dest) == src:
            rejected.append((src, "same"))
            continue
        if not _is_within(base_dir, dest):
            rejected.append((src, "outside"))
            continue
        # Importing the share — or an ancestor of the destination — into itself
        # would recurse forever.
        if _is_within(src, dest_dir):
            rejected.append((src, "recursive"))
            continue
        accepted.append(src)
    return accepted, rejected
