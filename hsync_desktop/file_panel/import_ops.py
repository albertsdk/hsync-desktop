# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Pure helpers for importing files dropped onto the file list.

Deliberately Qt-free: the drop handler (to pick a cursor) and the import worker
both call these, and they are unit-tested without a ``QApplication``.
"""

from __future__ import annotations

import os
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from hsync_common.path_validation import is_internal_name

# A dropped tree is counted with a metadata-only walk before it is copied. Past
# this budget the totals stay unknown and the caller keeps an indeterminate bar
# rather than paying a second full pass over a slow (network) source.
COUNT_BUDGET_S = 2.0
# The budget is checked every this many entries: ``time.monotonic()`` per file
# would cost more than the ``getsize`` the walk is already paying for.
_COUNT_CHECK_EVERY = 256


@dataclass(frozen=True, slots=True)
class ImportItem:
    """A resolved import: copy or move ``src`` to the absolute ``dest``."""

    src: str
    dest: str
    move: bool


class ImportPhase(StrEnum):
    """What the worker is doing with the current item."""

    SCAN = "scan"
    COPY = "copy"
    MOVE = "move"


@dataclass(frozen=True, slots=True)
class CopyProgress:
    """Advance of one import batch, rendered by ``file_panel/overlay.py``.

    ``files_total``/``bytes_total`` are ``None`` while unknown (the item is
    still being counted, or the count gave up on its budget): a bar must stay
    indeterminate in that state, never show a percentage it cannot keep.
    """

    phase: ImportPhase
    items_done: int
    items_total: int
    files_done: int
    bytes_done: int
    files_total: int | None = None
    bytes_total: int | None = None


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


def _raise_oserror(error: OSError) -> None:
    """Let ``os.walk`` propagate a scan error instead of skipping silently."""
    raise error


def count_tree(
    src: str,
    *,
    budget_s: float | None = COUNT_BUDGET_S,
    should_cancel: Callable[[], bool] | None = None,
) -> tuple[int, int, bool]:
    """Count the files and bytes under ``src`` without reading their contents.

    Metadata-only, but it still touches every entry, so the walk is bounded by
    ``budget_s`` (``None`` = unbounded). Returns ``(files, bytes, complete)``;
    ``complete=False`` (budget spent or cancelled) reports the partial counters
    so the caller keeps an indeterminate bar instead of a wrong percentage.

    Consumers: ``file_panel/workers.py::ImportWorker``.
    """
    files = 0
    total_bytes = 0
    deadline = None if budget_s is None else time.monotonic() + budget_s
    for root, _dirs, names in os.walk(src, onerror=_raise_oserror, followlinks=True):
        for name in names:
            if should_cancel is not None and should_cancel():
                return files, total_bytes, False
            files += 1
            if (
                deadline is not None
                and files % _COUNT_CHECK_EVERY == 0
                and time.monotonic() > deadline
            ):
                return files, total_bytes, False
            try:
                total_bytes += os.path.getsize(os.path.join(root, name))
            except OSError:
                # A dangling link is a copy failure the worker reports as such;
                # the count must not fail the batch before the copy starts.
                continue
    return files, total_bytes, True


def copy_tree(
    src: str,
    dest: str,
    *,
    on_file: Callable[[int, int], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> tuple[int, bool]:
    """Copy the tree at ``src`` to ``dest``, reporting every file written.

    Keeps ``shutil.copytree``'s defaults — a symlink is copied as its target and
    an existing ``dest`` is an error — but reports progress, which ``copytree``
    cannot: a folder dropped onto the file list can hold thousands of files.
    ``on_file(files, bytes)`` carries the cumulative counters of this tree.
    Returns ``(files_copied, complete)``; ``complete=False`` means the copy
    stopped on cancellation and a partial tree is left behind.

    Consumers: ``file_panel/workers.py::ImportWorker``.
    """
    # ``copytree`` opens the source before creating the destination, so a source
    # that vanished (or stopped being a directory) between the drop and the copy
    # fails without leaving an empty copy behind.
    if not os.path.isdir(src):
        raise FileNotFoundError(f"no such directory: {src}")
    os.makedirs(dest)
    files = 0
    total_bytes = 0
    # Directory metadata is applied last (root included, as ``copytree`` does):
    # a read-only source directory would otherwise block the files written
    # inside its copy.
    created_dirs: list[tuple[str, str]] = [(src, dest)]
    for root, dirs, names in os.walk(src, onerror=_raise_oserror, followlinks=True):
        relative = os.path.relpath(root, src)
        target = dest if relative == os.curdir else os.path.join(dest, relative)
        for name in dirs:
            child = os.path.join(target, name)
            os.makedirs(child, exist_ok=True)
            created_dirs.append((os.path.join(root, name), child))
        for name in names:
            if should_cancel is not None and should_cancel():
                return files, False
            destination = os.path.join(target, name)
            shutil.copy2(os.path.join(root, name), destination)
            files += 1
            total_bytes += os.path.getsize(destination)
            if on_file is not None:
                on_file(files, total_bytes)
    for source_dir, created_dir in reversed(created_dirs):
        shutil.copystat(source_dir, created_dir)
    return files, True
