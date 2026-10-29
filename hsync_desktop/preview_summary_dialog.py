# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""
Preview Summary Dialog for HSYNC Desktop.

The confirmation a sync plan passes through: one summary line, the two facts
only the engine knows (deletions the policy drops, a plan the mass-deletion guard
will pause), the plan grouped by action with the destructive ones first, and the
transfers estimated at the configured bandwidth limits.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from hsync_common.format import format_bytes
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from hsync_desktop.i18n import tr
from hsync_desktop.themes import COLOR_DISCONNECTED
from hsync_desktop.ui.loader import load_ui_widget

# A plan can hold one row per scanned file: the confirmation lists every
# destructive action (bounded) and only the largest transfers, so it never
# builds a 100k-row tree.
DETAIL_CAP = 500
LARGEST_CAP = 20


def _format_time(seconds: float) -> str:
    """Format seconds as the largest unit pair, without empty sub-units."""
    total = max(int(round(seconds)), 0)
    if total < 60:
        return f"{total} {tr('preview_summary.seconds')}"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        suffix = f" {secs} {tr('preview_summary.seconds')}" if secs else ""
        return f"{minutes} {tr('preview_summary.minutes')}{suffix}"
    hours, minutes = divmod(minutes, 60)
    suffix = f" {minutes} {tr('preview_summary.minutes')}" if minutes else ""
    return f"{hours} {tr('preview_summary.hours')}{suffix}"


@dataclass(slots=True)
class PreviewItem:
    """One planned action, as the confirmation lists it."""

    action: str  # "download" | "upload" | "delete" | "rename"
    path: str
    size: int = 0
    src: str = ""  # rename source; ``path`` is the new path


@dataclass
class PreviewStats:
    """What one comparison reports about the plan it produced."""

    to_download: int = 0
    to_upload: int = 0
    to_delete: int = 0
    to_rename: int = 0
    synced: int = 0
    download_size: int = 0
    upload_size: int = 0
    delete_size: int = 0
    # Deletions the client dropped because the policy keeps them.
    skipped_deletes: int = 0
    skipped_delete_size: int = 0
    # Unconfirmed deletions the mass-deletion guard would pause, and the local
    # file count the guard compares them with.
    guard_deletes: int = 0
    guard_local: int = 0
    deletes: list[PreviewItem] = field(default_factory=list)
    renames: list[PreviewItem] = field(default_factory=list)
    largest: list[PreviewItem] = field(default_factory=list)

    def reset(self) -> None:
        """Forget the previous comparison."""
        self.to_download = 0
        self.to_upload = 0
        self.to_delete = 0
        self.to_rename = 0
        self.synced = 0
        self.download_size = 0
        self.upload_size = 0
        self.delete_size = 0
        self.skipped_deletes = 0
        self.skipped_delete_size = 0
        self.guard_deletes = 0
        self.guard_local = 0
        self.deletes.clear()
        self.renames.clear()
        self.largest.clear()

    def has_work(self) -> bool:
        """True when the plan changes anything."""
        return bool(self.to_download or self.to_upload or self.to_delete or self.to_rename)

    @property
    def action_count(self) -> int:
        return self.to_download + self.to_upload + self.to_delete + self.to_rename

    @property
    def transfer_size(self) -> int:
        return self.download_size + self.upload_size

    def record_delete(self, path: str, size: int) -> None:
        """Count a planned deletion and list it while there is room."""
        self.to_delete += 1
        self.delete_size += size
        if len(self.deletes) < DETAIL_CAP:
            self.deletes.append(PreviewItem("delete", path, size))

    def record_rename(self, src: str, dst: str) -> None:
        """Count a planned rename and list it while there is room."""
        self.to_rename += 1
        if len(self.renames) < DETAIL_CAP:
            self.renames.append(PreviewItem("rename", dst, src=src))

    def record_transfer(self, action: str, path: str, size: int) -> None:
        """Count a transfer and keep the largest ones for the list."""
        if action == "download":
            self.to_download += 1
            self.download_size += size
        else:
            self.to_upload += 1
            self.upload_size += size
        self.largest.append(PreviewItem(action, path, size))
        self.largest.sort(key=lambda item: item.size, reverse=True)
        del self.largest[LARGEST_CAP:]

    def truncated_deletes(self) -> int:
        return max(self.to_delete - len(self.deletes), 0)

    def truncated_renames(self) -> int:
        return max(self.to_rename - len(self.renames), 0)


class PreviewSummaryDialog(QDialog):
    """Confirmation of a sync plan: summary, warnings, grouped details.

    ``intent`` is the action that asked for the plan: ``"start"`` (the run is a
    sync that confirms before applying) or ``"preview"`` (the run exists to show
    the plan, so applying is an explicit "Sync now" instead of the default).

    The title follows the intent, because the same dialog is reached from two
    different actions: a preview (and a Simulation Mode run, which is a preview
    by definition) is titled ``preview_summary.title``, a plan that a real sync
    is waiting on is titled ``preview_summary.title_plan`` — a confirmation of a
    run must not read as a preview that never applies anything.
    """

    def __init__(
        self,
        stats: PreviewStats,
        parent: QWidget | None = None,
        *,
        simulation: bool = False,
        download_bps: int | None = None,
        upload_bps: int | None = None,
        direction: str = "bidirectional",
        deletions_kept: bool = False,
        scope: str = "",
        intent: str = "start",
    ) -> None:
        super().__init__(parent)
        self._stats = stats
        self._simulation = simulation
        self._intent = intent
        self._download_bps = download_bps if download_bps and download_bps > 0 else None
        self._upload_bps = upload_bps if upload_bps and upload_bps > 0 else None
        self._direction = direction
        self._deletions_kept = deletions_kept
        self._scope = scope

        self._load_ui()
        self._populate()

    def _load_ui(self) -> None:
        load_ui_widget("preview_summary_dialog", self)

        title = tr(
            "preview_summary.title"
            if self._simulation or self._intent == "preview"
            else "preview_summary.title_plan"
        )
        if self._simulation:
            title += tr("simulation.window_title_suffix")
        self.setWindowTitle(title)

        self._lbl_summary: QLabel = self.findChild(QLabel, "lblSummary")  # type: ignore[assignment]
        self._lbl_context: QLabel = self.findChild(QLabel, "lblContext")  # type: ignore[assignment]
        self._lbl_warning: QLabel = self.findChild(QLabel, "lblWarning")  # type: ignore[assignment]
        self._tree: QTreeWidget = self.findChild(QTreeWidget, "treeDetails")  # type: ignore[assignment]
        self._lbl_footnote: QLabel = self.findChild(QLabel, "lblFootnote")  # type: ignore[assignment]
        self._button_box: QDialogButtonBox = self.findChild(QDialogButtonBox, "buttonBox")  # type: ignore[assignment]

        self._tree.setColumnCount(2)
        self._tree.setHeaderLabels([tr("preview_summary.col_path"), tr("preview_summary.col_size")])
        header = self._tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

    def _populate(self) -> None:
        self._lbl_summary.setText(self._summary_text())
        self._populate_context()
        self._populate_warning()
        self._populate_tree()
        self._populate_footnote()
        self._populate_buttons()

    def _summary_text(self) -> str:
        """One line: how many changes and how much data they move."""
        changes = tr("preview_summary.summary_changes").format(count=self._stats.action_count)
        size = f"{tr('preview_summary.total_size')}: {format_bytes(self._stats.transfer_size)}"
        return f"<b>{changes}</b> · {size}"

    def _populate_context(self) -> None:
        """State the scope, the direction, the simulation and the kept deletions."""
        parts: list[str] = []
        if self._scope:
            parts.append(tr("preview_summary.context_scope").format(path=self._scope))
        if self._direction != "bidirectional":
            key = "menu.sync.direction." + self._direction.replace("-", "_")
            parts.append(f"{tr('menu.sync.direction')}: {tr(key)}")
        if self._simulation:
            parts.append(tr("preview_summary.simulation"))
        if self._stats.skipped_deletes:
            parts.append(
                tr("preview_summary.skipped_deletions").format(count=self._stats.skipped_deletes)
            )
        self._lbl_context.setText(" · ".join(parts))
        self._lbl_context.setVisible(bool(parts))

    def _populate_warning(self) -> None:
        """Destructive plan: say so, and say when the guard will pause it."""
        if self._stats.guard_deletes:
            text = tr("preview_summary.warning_guard").format(
                deletes=self._stats.guard_deletes, local=self._stats.guard_local
            )
        elif self._stats.to_delete:
            text = tr("preview_summary.warning_delete").format(count=self._stats.to_delete)
        else:
            self._lbl_warning.clear()
            self._lbl_warning.setVisible(False)
            return
        self._lbl_warning.setText(f"⚠  {text}")
        self._lbl_warning.setStyleSheet(f"color: {COLOR_DISCONNECTED.name()};")
        self._lbl_warning.setVisible(True)

    def _populate_tree(self) -> None:
        """Every non-empty section, destructive first, transfers by size."""
        stats = self._stats
        self._tree.clear()
        self._add_group(
            label=tr("preview_summary.deletions"),
            count=stats.to_delete,
            suffix=self._size_suffix(stats.delete_size),
            rows=[(item.path, item.size) for item in stats.deletes],
            more=stats.truncated_deletes(),
        )
        self._add_group(
            label=tr("preview_summary.renames"),
            count=stats.to_rename,
            rows=[(f"{item.src} → {item.path}", 0) for item in stats.renames],
            more=stats.truncated_renames(),
        )
        transfers = (
            (
                "download",
                "preview_summary.downloads",
                stats.to_download,
                stats.download_size,
                self._download_bps,
            ),
            (
                "upload",
                "preview_summary.uploads",
                stats.to_upload,
                stats.upload_size,
                self._upload_bps,
            ),
        )
        for action, label_key, count, size, limit in transfers:
            rows = [(item.path, item.size) for item in stats.largest if item.action == action]
            self._add_group(
                label=tr(label_key),
                count=count,
                suffix=self._size_suffix(size) + self._estimate_suffix(size, limit),
                rows=rows,
                more=max(count - len(rows), 0),
            )
        self._tree.setVisible(self._tree.topLevelItemCount() > 0)

    def _add_group(
        self,
        *,
        label: str,
        count: int,
        rows: list[tuple[str, int]],
        suffix: str = "",
        more: int = 0,
    ) -> None:
        """Add one section (only when the plan has actions in it) and its rows."""
        if not count:
            return
        group = QTreeWidgetItem(self._tree, [f"{label}: {count}{suffix}", ""])
        group.setFirstColumnSpanned(True)
        group.setExpanded(True)
        for path, size in rows:
            child = QTreeWidgetItem(group, [path, format_bytes(size) if size else ""])
            child.setTextAlignment(1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if more:
            QTreeWidgetItem(group, [tr("preview_summary.more_items").format(count=more), ""])

    @staticmethod
    def _size_suffix(size: int) -> str:
        return f" · {format_bytes(size)}" if size else ""

    def _estimate_suffix(self, size: int, limit: int | None) -> str:
        """Estimate from the configured limit only: no limit, no number."""
        if not size or not limit:
            return ""
        return " · " + tr("preview_summary.estimate").format(
            time=_format_time(size / limit), rate=format_bytes(limit)
        )

    def _populate_footnote(self) -> None:
        if not self._stats.synced:
            self._lbl_footnote.setVisible(False)
            return
        self._lbl_footnote.setText(f"{tr('preview_summary.synced')}: {self._stats.synced}")
        self._lbl_footnote.setVisible(True)

    def _populate_buttons(self) -> None:
        """Applying the plan is never the default: Escape and Enter decline."""
        self._button_box.clear()
        if not self._stats.has_work():
            ok_btn = QPushButton(tr("preview_summary.ok"))
            ok_btn.setDefault(True)
            self._button_box.addButton(ok_btn, QDialogButtonBox.ButtonRole.RejectRole)
            ok_btn.clicked.connect(self.reject)
            return
        if self._simulation:
            close_btn = QPushButton(tr("preview_summary.close"))
            close_btn.setDefault(True)
            self._button_box.addButton(close_btn, QDialogButtonBox.ButtonRole.AcceptRole)
            close_btn.clicked.connect(self.accept)
            return
        if self._intent == "preview":
            # The user asked to see the plan, not to sync: closing ends the run
            # without applying, and applying is the explicit second click.
            close_btn = QPushButton(tr("preview_summary.close"))
            close_btn.setDefault(True)
            sync_btn = QPushButton(tr("preview_summary.sync_now"))
            self._button_box.addButton(close_btn, QDialogButtonBox.ButtonRole.RejectRole)
            self._button_box.addButton(sync_btn, QDialogButtonBox.ButtonRole.AcceptRole)
            close_btn.clicked.connect(self.reject)
            sync_btn.clicked.connect(self.accept)
            return
        cancel_btn = QPushButton(tr("preview_summary.cancel"))
        cancel_btn.setDefault(True)
        sync_btn = QPushButton(tr("preview_summary.sync"))
        self._button_box.addButton(cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)
        self._button_box.addButton(sync_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn.clicked.connect(self.reject)
        sync_btn.clicked.connect(self.accept)
