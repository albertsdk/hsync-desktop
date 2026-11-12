# mypy: disable-error-code="attr-defined, has-type, assignment, call-overload, arg-type, operator, index, union-attr, return-value"
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""UiBuildMixin: window construction, action bar, menus and role indicator."""

from __future__ import annotations

import os
from collections import deque
from collections.abc import Callable
from typing import cast
from urllib.parse import urlsplit

from hsync_common.endpoint import parse_host_port
from hsync_common.format import format_bytes
from hsync_common.logger import format_log_line
from PySide6.QtCore import QLocale, QPoint, QSettings, Qt, QTimer, Slot
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QDesktopServices,
    QFontMetrics,
    QKeySequence,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.bandwidth_dialog import BandwidthDialog
from hsync_desktop.busy import BusyText
from hsync_desktop.config import (
    DEFAULT_P2P_ENABLED,
    DEFAULT_P2P_RENDEZVOUS_TRUST,
    DEFAULT_SERVER_TRUST,
    DEFAULT_SYNC_DIRECTION,
)
from hsync_desktop.crypto import decrypt_value
from hsync_desktop.docs_links import TROUBLESHOOTING, WATCHER_LIMITS, open_docs_link
from hsync_desktop.engine import (
    HsyncEngine,
    add_peer_pin,
    add_rendezvous_trust,
    add_server_trust,
    fetch_rendezvous_fingerprint,
    fetch_server_fingerprint,
    find_hsync_binary,
    list_rendezvous_trust,
    list_server_trust,
    remove_peer_pin,
    remove_rendezvous_trust,
    remove_server_trust,
    supports_peer_trust,
)
from hsync_desktop.file_panel import FilePanel
from hsync_desktop.fonts import log_monospace_font
from hsync_desktop.i18n import register_language_callback, tr
from hsync_desktop.log_style import styled_runs
from hsync_desktop.notifications import NotificationManager
from hsync_desktop.preview_summary_dialog import PreviewStats, PreviewSummaryDialog
from hsync_desktop.problems import FAILURE, WARNING, Problem
from hsync_desktop.settings import (
    SETTINGS_APP,
    SETTINGS_ORG,
    ApiKeyDialog,
    P2PKeyDialog,
    SettingsDialog,
    are_notifications_enabled,
    build_hsync_args,
    get_deletion_policy,
    get_saved_theme,
    is_auto_sync_enabled,
    is_log_panel_visible,
    is_simulation_mode,
)
from hsync_desktop.system_tray import SystemTray
from hsync_desktop.themes import (
    COLOR_CONNECTED,
    COLOR_DISCONNECTED,
    COLOR_WAITING,
    THEME_LIGHT,
    apply_theme,
)
from hsync_desktop.ui.loader import load_ui_widget
from hsync_desktop.warnings import remedy_text
from hsync_desktop.widgets.links import help_link, set_help_link_url


def _standard_shortcuts(standard: QKeySequence.StandardKey, fallback: str) -> list[QKeySequence]:
    """Platform bindings for *standard keys*, with the conventional chord as fallback.

    A minimal platform theme (or the QPA offscreen plugin) reports no binding at
    all; using the action's conventional chord then beats leaving it without a
    shortcut. On macOS the binding is reported as ``Ctrl`` but triggers ``Cmd``.
    """
    bindings = list(QKeySequence.keyBindings(standard))
    return bindings if bindings else [QKeySequence(fallback)]


# ── Button styles ────────────────────────────────────────────────────────────
_BTN_PAD = "padding: 4px 10px; border-radius: 3px;"
_BTN_START_ACTIVE = (
    f"QPushButton {{ background-color: #2EA043; color: #FFFFFF;"
    f" border: none; {_BTN_PAD} }}"
    "QPushButton:hover { background-color: #278a39; }"
    "QPushButton:pressed { background-color: #1f7a30; }"
)
_BTN_STOP_ACTIVE = (
    f"QPushButton {{ background-color: #CF222E; color: #FFFFFF;"
    f" border: none; {_BTN_PAD} }}"
    "QPushButton:hover { background-color: #b71d28; }"
    "QPushButton:pressed { background-color: #a01822; }"
)
_BTN_PREVIEW_ACTIVE = (
    f"QPushButton {{ background-color: #0969DA; color: #FFFFFF;"
    f" border: none; {_BTN_PAD} }}"
    "QPushButton:hover { background-color: #0860CA; }"
    "QPushButton:pressed { background-color: #0757BA; }"
)
_BTN_IDLE = f"QPushButton {{ {_BTN_PAD} }}"

# ── Info toast severities ────────────────────────────────────────────────────
# `kind` → severity, used as the dynamic QSS property on #infoBanner.
_SEVERITY_BY_KIND = {
    "progress": "info",
    "info": "info",
    "success": "success",
    "warning": "warning",
    "notice": "warning",  # a transient warning: same tone, auto-hides
    "error": "error",
}
# Non-colour cue (accessibility): a leading glyph for error/warning/success.
_SEVERITY_ICON = {"error": "⛔", "warning": "⚠", "notice": "⚠", "success": "✔"}
# The toast paints its message in bold white on a coloured fill. A rich-text
# anchor ignores the label QSS colour, so the guide link must be coloured inline
# or it falls back to the theme's blue — unreadable on the warning/error fills.
# White matches the message text; the underline (added with the colour) keeps the
# link recognisable without relying on hue alone.
_TOAST_LINK_COLOR = "#FFFFFF"
# Toasts that survive the engine process finishing: the run's outcome stays on
# screen until its own auto-hide runs out. Nothing survives a *new* run — the
# state it described lives in the problems badge, which is reset with the run.
_SURVIVES_FINISH = {"success", "error", "warning"}

#: The log panel keeps at most this many lines: ``QPlainTextEdit`` evicts the
#: oldest block once the cap is reached, so a long-running session cannot grow
#: without bound. Single source of truth (the ``.ui`` declares no cap).
_LOG_MAX_BLOCKS = 10000

#: A single line is capped before it reaches the document: the block cap bounds
#: the line count, not their size, and one pathological line (a pretty-printed
#: payload, an enormous path) would otherwise sit in the document and cost layout
#: on every re-render.
_LOG_LINE_MAX_CHARS = 4000
_LOG_LINE_ELLIPSIS = " …"

#: The connectivity dot overlaid on the endpoint mode icon (a neutral/in-progress
#: state) keeps to this fraction of the icon so it annotates the mode instead of
#: hiding it. Alert/error/stopped states replace the icon entirely instead.
_STATUS_OVERLAY_DOT_RATIO = 0.4


def _insert_log_line(cursor: QTextCursor, line: str, theme: str) -> None:
    """Insert one styled line at *cursor*, capping its length on the text.

    The cap is applied after ``styled_runs`` so an SGR sequence is never cut in
    half; the cut is marked so a truncated line is never silent.
    """
    remaining = _LOG_LINE_MAX_CHARS
    for run in styled_runs(line, theme):
        if remaining <= 0:
            cursor.insertText(_LOG_LINE_ELLIPSIS)
            return
        if len(run.text) > remaining:
            cursor.insertText(run.text[:remaining], run.fmt)
            cursor.insertText(_LOG_LINE_ELLIPSIS)
            return
        cursor.insertText(run.text, run.fmt)
        remaining -= len(run.text)


class UiBuildMixin:
    def _load_ui(self) -> None:
        """Load UI from .ui file and setup widget references."""
        # Load UI into self
        load_ui_widget("main_window", self)

        # Get widget references from .ui file
        self._btn_start: QPushButton = self.findChild(QPushButton, "btnStart")  # type: ignore[assignment]
        self._btn_stop: QPushButton = self.findChild(QPushButton, "btnStop")  # type: ignore[assignment]
        self._btn_preview_changes: QPushButton = self.findChild(QPushButton, "btnPreviewChanges")  # type: ignore[assignment]
        # Set icons for action buttons (icon-only, no text)
        from PySide6.QtCore import QSize

        from hsync_desktop.icons import HEADER_ICON_PX
        from hsync_desktop.icons import icon as get_icon

        icon_size = QSize(18, 18)
        for btn, ico_name in (
            (self._btn_start, "media-playback-start"),
            (self._btn_stop, "media-playback-stop"),
            (self._btn_preview_changes, "view-refresh"),
        ):
            btn.setIcon(get_icon(ico_name))
            btn.setIconSize(icon_size)
            btn.setText("")
        self._path_label: QLabel = self.findChild(QLabel, "pathLabel")  # type: ignore[assignment]
        self._local_path: str = ""
        # Active share name (bucket) shown next to the folder icon; empty until
        # the engine detects one, then seeded from the configured share.
        self._bucket: str = ""

        # Add folder icon label before path label
        self._path_icon_label = QLabel(self.centralWidget())
        self._path_icon_label.setPixmap(
            get_icon("folder-open").pixmap(HEADER_ICON_PX, HEADER_ICON_PX)
        )
        self._path_icon_label.setFixedSize(HEADER_ICON_PX, HEADER_ICON_PX)
        self._path_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._path_icon_label.hide()  # Hidden until path is set

        # Sync direction icon (right of path label)
        self._sync_dir_icon = QLabel(self.centralWidget())
        self._sync_dir_icon.setFixedSize(HEADER_ICON_PX, HEADER_ICON_PX)
        self._sync_dir_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sync_dir_icon.hide()

        # Remote endpoint icon + label (right of sync direction icon)
        self._remote_icon = QLabel(self.centralWidget())
        self._remote_icon.setFixedSize(HEADER_ICON_PX, HEADER_ICON_PX)
        self._remote_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._remote_icon.hide()
        self._remote_label = QLabel(self.centralWidget())
        self._remote_label.hide()
        # The endpoint icon/label open the connectivity badge menu (see eventFilter).
        self._remote_icon.installEventFilter(self)
        self._remote_label.installEventFilter(self)

        # Header share selector: a compact chevron after the share name. Clicking
        # the name or the chevron opens the shares menu (see SharesMixin); the
        # folder icon opens the share's folder (see LifecycleMixin.eventFilter).
        self._shares_button = QToolButton(self.centralWidget())
        # The style also paints its own menu indicator for a button that has a
        # menu, so an explicit arrow type drew two chevrons under some styles;
        # themes.py hides that indicator and this arrow is the only one.
        self._shares_button.setObjectName("sharesButton")
        self._shares_button.setAutoRaise(True)
        self._shares_button.setArrowType(Qt.ArrowType.DownArrow)
        self._shares_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._shares_button.setToolTip(tr("shares.menu.title"))
        self._shares_button.hide()
        self._path_icon_label.installEventFilter(self)
        self._path_icon_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._path_label.installEventFilter(self)
        self._path_label.setCursor(Qt.CursorShape.PointingHandCursor)

        # Insert widgets into the actionBarLayout
        # Layout order: ... [folder-icon] [path-label] [sync-dir-icon] [remote-icon] [remote-label] [browse-btn] ...
        central = self.centralWidget()
        root_layout = central.layout() if central is not None else None
        if root_layout:
            first_item = root_layout.itemAt(0)
            if first_item:
                action_bar_layout = first_item.layout()
                if isinstance(action_bar_layout, QHBoxLayout):
                    for i in range(action_bar_layout.count()):
                        item = action_bar_layout.itemAt(i)
                        if item and item.widget() == self._path_label:
                            action_bar_layout.insertWidget(i, self._path_icon_label)
                            # [folder] [path] [shares ▾] [direction] [endpoint] …
                            action_bar_layout.insertWidget(i + 2, self._shares_button)
                            action_bar_layout.insertWidget(i + 3, self._sync_dir_icon)
                            action_bar_layout.insertWidget(i + 4, self._remote_icon)
                            action_bar_layout.insertWidget(i + 5, self._remote_label)
                            break
        self._main_splitter: QSplitter = self.findChild(QSplitter, "mainSplitter")  # type: ignore[assignment]
        self._log_view: QPlainTextEdit = self.findChild(QPlainTextEdit, "logView")  # type: ignore[assignment]
        self._log_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._log_view.customContextMenuRequested.connect(self._show_log_context_menu)
        # Bound the panel: the oldest line is evicted once the cap is reached, so
        # a long-running session cannot grow without bound.
        self._log_view.setMaximumBlockCount(_LOG_MAX_BLOCKS)
        # Use the desktop's monospace font, two points smaller: the log lines are
        # long, so the extra width keeps them readable without scrolling.
        self._log_view.setFont(log_monospace_font())
        # Per-share log buffers: the panel shows the active share's lines and
        # SharesMixin swaps them on switch. Each share keeps a bounded history.
        self._log_buffers: dict[str, deque[str]] = {}
        self._log_active_share: str = ""

        # Bottom bar widgets
        self._status_dot: QLabel = self.findChild(QLabel, "statusDot")  # type: ignore[assignment]
        self._status_label: QLabel = self.findChild(QLabel, "statusLabel")  # type: ignore[assignment]
        self._simulation_badge: QLabel = self.findChild(QLabel, "simulationBadge")  # type: ignore[assignment]
        self._deletion_badge: QLabel = self.findChild(QLabel, "deletionBadge")  # type: ignore[assignment]
        # The status-bar surface for the problems that currently hold: hidden
        # while there are none, and its menu lists every one of them.
        self._problems_badge: QToolButton = self.findChild(QToolButton, "problemsBadge")  # type: ignore[assignment]
        self._problems_menu = QMenu(self._problems_badge)
        self._problems_badge.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._problems_badge.setMenu(self._problems_menu)
        self._problems.changed.connect(self._refresh_problems_badge)
        # p2p connectivity warnings (master/rendezvous/relay) also drive the
        # endpoint badge's reason, without re-plumbing those events.
        self._problems.changed.connect(self._render_connection_badge)
        self._role_label: QLabel = self.findChild(QLabel, "roleLabel")  # type: ignore[assignment]
        # Add role icon before roleLabel in the bottom bar layout
        self._role_icon = QLabel()
        self._role_icon.setFixedSize(16, 16)
        bottom_layout: QHBoxLayout = self.findChild(QHBoxLayout, "bottomBarLayout")  # type: ignore[assignment]
        if bottom_layout:
            role_idx = bottom_layout.indexOf(self._role_label)
            if role_idx >= 0:
                bottom_layout.insertWidget(role_idx, self._role_icon)
        self._group_label: QLabel = self.findChild(QLabel, "groupLabel")  # type: ignore[assignment]
        self._lbl_peers: QLabel = self.findChild(QLabel, "lblPeers")  # type: ignore[assignment]
        self._peers_label: QLabel = self.findChild(QLabel, "peersLabel")  # type: ignore[assignment]
        self._lbl_sent: QLabel = self.findChild(QLabel, "lblSent")  # type: ignore[assignment]
        self._sent_label: QLabel = self.findChild(QLabel, "sentLabel")  # type: ignore[assignment]
        self._lbl_recv: QLabel = self.findChild(QLabel, "lblRecv")  # type: ignore[assignment]
        self._recv_label: QLabel = self.findChild(QLabel, "recvLabel")  # type: ignore[assignment]

        # Shared-folder size (local / total of the share), right side before Peers.
        self._share_size_label = QLabel(self.centralWidget())
        self._share_size_label.setText("—")
        self._share_size_label.setForegroundRole(self.palette().ColorRole.PlaceholderText)
        self._share_local_bytes: int = -1
        self._share_total_bytes: int = -1
        # Sync state: the link status on the left says whether a device is
        # reachable, never whether the file sets match. This label answers that
        # second question (set by the preview/file-status flow in events.py).
        self._sync_state_label = QLabel(self.centralWidget())
        self._sync_state = ("idle", 0, 0, 0)
        # Data-movement phase reported by the engine (``syncing``/``idle``): it
        # animates this label without changing the text, so the bar keeps
        # answering "do the file sets match?" while a cycle runs.
        self._activity: str | None = None
        self._sync_state_label.setForegroundRole(self.palette().ColorRole.PlaceholderText)
        # Busy feedback for this label, created here so the first
        # ``_render_sync_state`` (from ``_apply_translations``) already finds it.
        self._sync_busy = BusyText(self._sync_state_label)
        if bottom_layout:
            peers_idx = bottom_layout.indexOf(self._lbl_peers)
            if peers_idx >= 0:
                bottom_layout.insertWidget(peers_idx, self._share_size_label)
                bottom_layout.insertSpacing(peers_idx + 1, 14)
                bottom_layout.insertWidget(peers_idx + 2, self._sync_state_label)
                bottom_layout.insertSpacing(peers_idx + 3, 14)
            else:
                bottom_layout.addWidget(self._share_size_label)
                bottom_layout.addWidget(self._sync_state_label)

        # Clicking the state opens the comparison while it reports pending work
        # (``EventsMixin._render_sync_state`` turns the cursor on and
        # ``MainWindow.eventFilter`` handles the click).
        self._sync_state_label.installEventFilter(self)

        # Make bandwidth labels clickable (both the label header and value)
        self._lbl_sent.setCursor(Qt.CursorShape.PointingHandCursor)
        self._lbl_sent.setToolTip(tr("bandwidth.click_to_edit"))
        self._sent_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sent_label.setToolTip(tr("bandwidth.click_to_edit"))
        self._lbl_recv.setCursor(Qt.CursorShape.PointingHandCursor)
        self._lbl_recv.setToolTip(tr("bandwidth.click_to_edit"))
        self._recv_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._recv_label.setToolTip(tr("bandwidth.click_to_edit"))

        # Connect bandwidth label click handlers using event filter
        for label in [self._lbl_sent, self._sent_label, self._lbl_recv, self._recv_label]:
            label.installEventFilter(self)

        # Replace filePanelPlaceholder with actual FilePanel
        placeholder: QWidget = self.findChild(QWidget, "filePanelPlaceholder")  # type: ignore[assignment]
        self._file_panel = FilePanel()
        # Replace placeholder in splitter
        self._file_panel.setMinimumHeight(150)
        idx = self._main_splitter.indexOf(placeholder)
        if idx >= 0:
            placeholder.setParent(None)
            self._main_splitter.insertWidget(idx, self._file_panel)
        # Set initial sizes (2/3 files, 1/3 log)
        self._main_splitter.setSizes([400, 200])

        # Info toast: an overlay child of the central widget (never in the
        # layout, so showing/hiding it cannot move the content).
        self._info_banner = self._create_info_banner()
        self._info_banner.setParent(self.centralWidget())
        self._info_banner.hide()
        self._info_banner_kind: str | None = None
        self._info_timer = QTimer(self)
        self._info_timer.setSingleShot(True)
        self._info_timer.timeout.connect(self._hide_info_banner)

        # Apply log panel visibility setting
        self._apply_log_visibility()

        # Restore saved path and load files
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        saved_path = str(s.value("path/local", "", str))
        self._set_path(saved_path)
        if saved_path:
            self._load_local_files(saved_path)

        # Apply translations
        self._apply_translations()

        # Apply initial button styles (Start green, Stop idle)
        self._apply_button_styles()

        # Create classic menu bar
        self._create_menu_bar()

        # Wire the header share selector (SharesMixin).
        self._init_shares_ui()

        # Set initial button/menu/tray state (disables Start if no path)
        self._update_menu_state()

        # Register for language change notifications
        register_language_callback(self._apply_translations)

    def _apply_translations(self) -> None:
        """Apply i18n translations to UI elements."""
        self._btn_start.setToolTip(tr("tip.start"))
        self._btn_stop.setToolTip(tr("btn.stop"))
        self._update_preview_changes_tooltip()
        self._update_path_display()
        self._status_label.setText(tr("status.disconnected"))
        # Seed the active share name from the configured share; the window title
        # stays the app name (the share is shown next to the folder icon).
        self._on_bucket_detected(
            str(QSettings(SETTINGS_ORG, SETTINGS_APP).value("sync/bucket", "", str)).strip()
        )
        self._retranslate_role()
        self._update_peers_label_title()
        self._share_size_label.setToolTip(tr("tip.share_size"))
        self._render_share_size()
        self._render_sync_state()
        self._lbl_sent.setText(tr("label.sent"))
        self._lbl_recv.setText(tr("label.received"))
        # The file table owns its column headers, so re-localize them here.
        self._file_panel.retranslate_columns()
        # Bandwidth label tooltips
        self._lbl_sent.setToolTip(tr("bandwidth.click_to_edit"))
        self._sent_label.setToolTip(tr("bandwidth.click_to_edit"))
        self._lbl_recv.setToolTip(tr("bandwidth.click_to_edit"))
        self._recv_label.setToolTip(tr("bandwidth.click_to_edit"))
        # Menu bar translations
        if hasattr(self, "_menu_sync"):
            self._menu_sync.setTitle(tr("menu.sync"))
            self._act_start.setText(tr("menu.sync.start"))
            self._act_preview_changes.setText(tr("menu.sync.preview"))
            self._act_stop.setText(tr("menu.sync.stop"))
            # The menu shows these, so a language change must re-translate them
            # like the labels above. The preview wording is state-dependent and
            # owned by ``_update_preview_changes_tooltip``.
            self._act_start.setToolTip(tr("tip.start"))
            self._menu_direction.setTitle(tr("menu.sync.direction"))
            self._act_dir_bidi.setText(tr("menu.sync.direction.bidirectional"))
            self._act_dir_upload.setText(tr("menu.sync.direction.upload_only"))
            self._act_dir_download.setText(tr("menu.sync.direction.download_only"))
            self._act_quit.setText(tr("menu.sync.quit"))
            self._menu_file.setTitle(tr("menu.file"))
            self._act_file_open.setText(tr("menu.file.open"))
            self._act_file_open_containing.setText(tr("menu.file.open_containing"))
            self._act_file_open_with.setText(tr("menu.file.open_with"))
            self._act_file_copy_to.setText(tr("menu.file.copy_to"))
            self._act_file_copy_path.setText(tr("menu.file.copy_path"))
            self._act_file_copy_path_relative.setText(tr("menu.file.copy_path_relative"))
            self._act_file_rename.setText(tr("menu.file.rename"))
            self._act_file_send.setText(tr("action.send_now"))
            self._act_file_receive.setText(tr("action.receive_now"))
            self._act_file_trash.setText(tr("menu.file.trash"))
            self._act_file_properties.setText(tr("menu.file.properties"))
            self._act_settings.setText(tr("menu.settings"))
            self._act_setup_wizard.setText(tr("menu.setup_wizard"))
            self._menu_help.setTitle(tr("menu.help"))
            self._act_help_docs.setText(tr("menu.help.docs"))
            self._act_help_github.setText(tr("menu.help.github"))
            self._act_help_updates.setText(tr("menu.help.updates"))
            self._act_help_license.setText(tr("menu.help.license"))
            self._act_help_about.setText(tr("menu.help.about"))

        # Simulation Mode and backup-policy badges follow the language too.
        self._refresh_simulation_state()
        self._refresh_deletion_badge()
        self._refresh_problems_badge()

    def _refresh_problems_badge(self) -> None:
        """Render the active problems on the status-bar badge.

        The badge is the window's statement of what is wrong *right now*: hidden
        while nothing holds, and otherwise a count with a severity tone (an error
        while a transfer is failing, a warning while only a condition is
        reported) and a menu that names every problem, so the user can tell which
        ones and reach the log line that explains them. It clears itself: each
        entry leaves the registry when its condition heals.
        """
        problems = self._problems.problems
        self._problems_menu.clear()
        if not problems:
            self._problems_badge.hide()
            return
        self._problems_badge.setText(tr("problems.badge").replace("{count}", str(len(problems))))
        self._problems_badge.setToolTip(self._problems_tooltip(problems))
        self._problems_badge.setProperty(
            "severity", "error" if self._problems.failure_count else "warning"
        )
        style = self._problems_badge.style()
        style.unpolish(self._problems_badge)
        style.polish(self._problems_badge)
        for problem in problems:
            action = self._problems_menu.addAction(self._problem_label(problem))
            action.triggered.connect(lambda _=False, key=problem.key: self._reveal_log_line(key))
        # The remedy a toast carries must stay reachable after it expires: the entry
        # outlives the toast, so its guide link does too. One action serves the
        # whole list, opening the first guide it finds — the targets are the
        # watcher-limits page and the troubleshooting page, and in practice one
        # actionable condition is standing at a time.
        guide = next((problem.help_url for problem in problems if problem.help_url), None)
        if guide:
            self._problems_menu.addSeparator()
            open_guide = self._problems_menu.addAction(tr("problems.open_guide"))
            open_guide.triggered.connect(lambda _=False, url=guide: open_docs_link(url))
        self._problems_menu.addSeparator()
        dismiss = self._problems_menu.addAction(tr("problems.dismiss_all"))
        dismiss.triggered.connect(self._dismiss_problems)
        self._problems_badge.show()

    @staticmethod
    def _problem_label(problem: Problem) -> str:
        """The one-line menu label: the identity, with the reason when there is one.

        A warning's title already carries the whole condition, so only a failure
        (whose title is the bare path) is given its reason.
        """
        if problem.kind == FAILURE and problem.detail:
            return f"{problem.title} — {problem.detail}"
        return problem.title

    @staticmethod
    def _problems_tooltip(problems: list[Problem]) -> str:
        """The badge tooltip: every problem on its own line, under its kind.

        The detail is appended here — the tooltip is where the remedy fits
        without turning the menu entries into paragraphs.
        """
        lines: list[str] = []
        failures = [problem for problem in problems if problem.kind == FAILURE]
        warnings = [problem for problem in problems if problem.kind == WARNING]
        if failures:
            lines.append(tr("problems.failures").replace("{count}", str(len(failures))))
            lines.extend(UiBuildMixin._problem_line(problem) for problem in failures)
        if warnings:
            lines.append(tr("problems.warnings").replace("{count}", str(len(warnings))))
            lines.extend(UiBuildMixin._problem_line(problem) for problem in warnings)
        return "\n".join(lines)

    @staticmethod
    def _problem_line(problem: Problem) -> str:
        """One tooltip line: the identity, then its detail when it has one."""
        return f"  {problem.title} — {problem.detail}" if problem.detail else f"  {problem.title}"

    def _dismiss_problems(self) -> None:
        """Drop every active problem: the user acknowledged them."""
        self._problems.clear_all()

    def _reveal_log_line(self, needle: str) -> None:
        """Select and scroll to the last log line mentioning *needle*.

        The problems badge says *what* is wrong; the log line that reported it
        says *why*. The line may already have been evicted by the panel's cap, in
        which case there is nothing to reveal.
        """
        text = self._log_view.toPlainText()
        index = text.rfind(needle)
        if index < 0:
            return
        cursor = self._log_view.textCursor()
        cursor.setPosition(index)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
        self._log_view.setTextCursor(cursor)
        self._log_view.ensureCursorVisible()

    def _refresh_deletion_badge(self) -> None:
        """Show the backup-policy badge while this device keeps deletions.

        Called at build time, on every language change and after the settings
        are applied. Without a permanent indicator, a user who inherited a
        backup setup (or enabled `keep` once) would only notice the policy from
        the deletions that never happen.
        """
        keep = get_deletion_policy() == "keep"
        self._deletion_badge.setText(tr("deletion.badge"))
        self._deletion_badge.setToolTip(tr("deletion.tip") if keep else "")
        self._deletion_badge.setVisible(keep)

    def _update_window_title(self) -> None:
        """App name, with the Simulation Mode suffix while it is active."""
        title = tr("app.name")
        if self._simulation_mode:
            title += tr("simulation.window_title_suffix")
        self.setWindowTitle(title)

    def _refresh_simulation_state(self) -> None:
        """Reflect Simulation Mode in the window and the tray.

        Called at build time and whenever settings change: the badge, the window
        title, the tray tooltip and the Start hint must agree with
        ``sync/dry_run`` without the user reopening anything.
        """
        self._simulation_mode = is_simulation_mode()
        self._simulation_badge.setVisible(self._simulation_mode)
        self._simulation_badge.setText(tr("simulation.badge"))
        self._simulation_badge.setToolTip(tr("simulation.tip") if self._simulation_mode else "")
        self._btn_start.setToolTip(
            tr("tip.start_simulation") if self._simulation_mode else tr("tip.start")
        )
        self._update_window_title()
        tray = getattr(self, "_tray", None)
        if tray is not None:
            tray.set_simulation(self._simulation_mode)
        # The check action depends on the mode (a Simulation run *is* a preview):
        # keep button, F5 and tray in step when settings change mid-session.
        self._update_menu_state()

    def _update_peers_label_title(self) -> None:
        """Label the presence count for what it actually counts.

        p2p counts devices (self + peers); server mode counts the share accounts
        with a live WebSocket, so "Devices" would overstate it when two devices
        share one account.
        """
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        p2p_enabled = bool(s.value("p2p/enabled", DEFAULT_P2P_ENABLED, bool))
        self._lbl_peers.setText(tr("label.peers" if p2p_enabled else "label.users"))

    # ── Menu bar ──────────────────────────────────────────────────────────

    def _create_menu_bar(self) -> None:
        """Create the classic menu bar with Sync, File, Settings, Help."""
        menubar = self.menuBar()
        # Use Qt menu bar (not native) so Alt mnemonics work on GNOME/Ubuntu
        menubar.setNativeMenuBar(False)

        # ── Sync menu ─────────────────────────────────────────────────
        self._menu_sync = menubar.addMenu(tr("menu.sync"))
        # Only Start and Preview changes carry a tooltip; a menu
        # shows them only when asked (QMenu defaults to off), and those labels
        # alone do not explain when an action can be used or what it will not do.
        self._menu_sync.setToolTipsVisible(True)

        self._act_start = QAction(tr("menu.sync.start"), self)
        self._act_start.setShortcut("Ctrl+Shift+S")
        self._act_start.setToolTip(tr("tip.start"))
        self._act_start.triggered.connect(self._on_start)
        self._menu_sync.addAction(self._act_start)

        self._act_preview_changes = QAction(tr("menu.sync.preview"), self)
        # Comparison first, like the analog tools (FreeFileSync compares on F5):
        # one action that answers whether the engine runs or not, with the older
        # preview-only chord kept as a second shortcut.
        self._act_preview_changes.setShortcuts([QKeySequence("F5"), QKeySequence("Ctrl+Shift+P")])
        self._act_preview_changes.setToolTip(tr("tip.preview_changes"))
        self._act_preview_changes.triggered.connect(self._on_preview_changes)
        self._menu_sync.addAction(self._act_preview_changes)

        self._act_stop = QAction(tr("menu.sync.stop"), self)
        self._act_stop.setEnabled(False)
        self._act_stop.triggered.connect(self._on_stop)
        self._menu_sync.addAction(self._act_stop)

        # ── Sync direction submenu ──────────────────────────────────
        self._menu_direction = self._menu_sync.addMenu(tr("menu.sync.direction"))
        self._direction_group = QActionGroup(self)
        self._direction_group.setExclusive(True)

        self._act_dir_bidi = QAction(tr("menu.sync.direction.bidirectional"), self)
        self._act_dir_bidi.setCheckable(True)
        self._act_dir_bidi.setData("bidirectional")
        self._direction_group.addAction(self._act_dir_bidi)
        self._menu_direction.addAction(self._act_dir_bidi)

        self._act_dir_upload = QAction(tr("menu.sync.direction.upload_only"), self)
        self._act_dir_upload.setCheckable(True)
        self._act_dir_upload.setData("upload-only")
        self._direction_group.addAction(self._act_dir_upload)
        self._menu_direction.addAction(self._act_dir_upload)

        self._act_dir_download = QAction(tr("menu.sync.direction.download_only"), self)
        self._act_dir_download.setCheckable(True)
        self._act_dir_download.setData("download-only")
        self._direction_group.addAction(self._act_dir_download)
        self._menu_direction.addAction(self._act_dir_download)

        # Load saved direction and check the right action
        saved_dir = QSettings(SETTINGS_ORG, SETTINGS_APP).value(
            "sync/direction", DEFAULT_SYNC_DIRECTION, str
        )
        for act in self._direction_group.actions():
            if act.data() == saved_dir:
                act.setChecked(True)
                break
        else:
            self._act_dir_bidi.setChecked(True)

        self._direction_group.triggered.connect(self._on_direction_changed)

        self._menu_sync.addSeparator()

        self._act_quit = QAction(tr("menu.sync.quit"), self)
        self._act_quit.setShortcuts(_standard_shortcuts(QKeySequence.StandardKey.Quit, "Ctrl+Q"))
        self._act_quit.triggered.connect(self._quit)
        self._menu_sync.addAction(self._act_quit)

        # ── File menu ─────────────────────────────────────────────────
        self._menu_file = menubar.addMenu(tr("menu.file"))

        self._act_file_open = QAction(tr("menu.file.open"), self)
        # Ctrl+O is the platform-standard "open"; Return stays as the list
        # convenience. "Open with…" has no standard key of its own.
        self._act_file_open.setShortcuts(["Return", QKeySequence("Ctrl+O")])
        self._act_file_open.triggered.connect(self._menu_file_open)
        self._menu_file.addAction(self._act_file_open)

        self._act_file_open_containing = QAction(tr("menu.file.open_containing"), self)
        self._act_file_open_containing.triggered.connect(self._menu_file_open_containing)
        self._menu_file.addAction(self._act_file_open_containing)

        self._act_file_open_with = QAction(tr("menu.file.open_with"), self)
        self._act_file_open_with.triggered.connect(self._menu_file_open_with)
        self._menu_file.addAction(self._act_file_open_with)

        self._menu_file.addSeparator()

        self._act_file_copy_to = QAction(tr("menu.file.copy_to"), self)
        # Ctrl+Shift+C is the conventional "copy as path" below, so the file
        # copy keeps the mnemonic on Ctrl+Alt+C.
        self._act_file_copy_to.setShortcut("Ctrl+Alt+C")
        self._act_file_copy_to.triggered.connect(self._menu_file_copy_to)
        self._menu_file.addAction(self._act_file_copy_to)

        self._act_file_copy_path = QAction(tr("menu.file.copy_path"), self)
        self._act_file_copy_path.setShortcut("Ctrl+Shift+C")
        self._act_file_copy_path.triggered.connect(self._menu_file_copy_path)
        self._menu_file.addAction(self._act_file_copy_path)

        self._act_file_copy_path_relative = QAction(tr("menu.file.copy_path_relative"), self)
        self._act_file_copy_path_relative.triggered.connect(self._menu_file_copy_path_relative)
        self._menu_file.addAction(self._act_file_copy_path_relative)

        self._act_file_rename = QAction(tr("menu.file.rename"), self)
        self._act_file_rename.setShortcut("F2")
        self._act_file_rename.triggered.connect(self._menu_file_rename)
        self._menu_file.addAction(self._act_file_rename)

        self._menu_file.addSeparator()

        self._act_file_send = QAction(tr("action.send_now"), self)
        self._act_file_send.triggered.connect(self._menu_file_send)
        self._menu_file.addAction(self._act_file_send)

        self._act_file_receive = QAction(tr("action.receive_now"), self)
        self._act_file_receive.triggered.connect(self._menu_file_receive)
        self._menu_file.addAction(self._act_file_receive)

        self._menu_file.addSeparator()

        self._act_file_trash = QAction(tr("menu.file.trash"), self)
        self._act_file_trash.setShortcut("Delete")
        self._act_file_trash.triggered.connect(self._menu_file_trash)
        self._menu_file.addAction(self._act_file_trash)

        self._menu_file.addSeparator()

        self._act_file_properties = QAction(tr("menu.file.properties"), self)
        self._act_file_properties.setShortcut("Alt+Return")
        self._act_file_properties.triggered.connect(self._menu_file_properties)
        self._menu_file.addAction(self._act_file_properties)

        # Disable all File menu actions initially (no selection)
        self._set_file_menu_enabled(False)

        # ── Settings (direct menu item) ───────────────────────────────
        self._act_settings = QAction(tr("menu.settings"), self)
        self._act_settings.setShortcuts(
            _standard_shortcuts(QKeySequence.StandardKey.Preferences, "Ctrl+,")
        )
        self._act_settings.triggered.connect(self._open_settings)
        menubar.addAction(self._act_settings)

        self._act_setup_wizard = QAction(tr("menu.setup_wizard"), self)
        self._act_setup_wizard.triggered.connect(self._open_setup_wizard)
        menubar.addAction(self._act_setup_wizard)

        # ── Help menu ─────────────────────────────────────────────────
        # External links first, then a separator and the local app-info
        # dialogs, with "About" kept last (the conventional position).
        self._menu_help = menubar.addMenu(tr("menu.help"))

        self._act_help_docs = QAction(tr("menu.help.docs"), self)
        self._act_help_docs.setShortcut("F1")
        self._act_help_docs.triggered.connect(self._open_documentation)
        self._menu_help.addAction(self._act_help_docs)

        self._act_help_github = QAction(tr("menu.help.github"), self)
        self._act_help_github.triggered.connect(self._open_github)
        self._menu_help.addAction(self._act_help_github)

        self._menu_help.addSeparator()

        self._act_help_updates = QAction(tr("menu.help.updates"), self)
        self._act_help_updates.triggered.connect(self._check_for_updates)
        self._menu_help.addAction(self._act_help_updates)

        self._act_help_license = QAction(tr("menu.help.license"), self)
        self._act_help_license.triggered.connect(self._show_license)
        self._menu_help.addAction(self._act_help_license)

        self._act_help_about = QAction(tr("menu.help.about"), self)
        self._act_help_about.triggered.connect(self._show_about)
        self._menu_help.addAction(self._act_help_about)

    def _set_file_menu_enabled(self, enabled: bool) -> None:
        """Enable or disable all File menu actions."""
        for act in (
            self._act_file_open,
            self._act_file_open_containing,
            self._act_file_open_with,
            self._act_file_copy_to,
            self._act_file_copy_path,
            self._act_file_copy_path_relative,
            self._act_file_rename,
            self._act_file_trash,
            self._act_file_properties,
        ):
            act.setEnabled(enabled)
        # Send/Receive also need a stopped engine.
        selection_sync = enabled and not self._engine.is_running
        self._act_file_send.setEnabled(selection_sync)
        self._act_file_receive.setEnabled(selection_sync)

    def _update_menu_state(self) -> None:
        """Update menu/button/tray enabled state based on app state.

        The comparison action is derived here from
        ``StartMixin._can_preview_changes`` for the action-bar button, the menu
        action and the tray entry: one rule, so the three can never disagree (and
        a comparison in flight greys the control instead of queueing a second
        scan). It stays available while a sync runs, because it is the app's only
        answer to "what would be synced".
        """
        if not hasattr(self, "_act_start"):
            return  # Menu bar not yet created
        is_running = self._engine.is_running
        # A stop in progress is not a usable engine: nothing may be started
        # until the child has reported its exit (cleared by the window slots).
        is_stopping = self._stop_requested
        has_path = bool(self._local_path)

        can_start = not is_running and has_path and not is_stopping
        self._act_start.setEnabled(can_start)
        self._btn_start.setEnabled(can_start)
        if self._tray:
            self._tray.set_start_enabled(can_start)
            # The folder shortcut follows the folder itself: a configured path
            # that is not reachable is not something the tray may promise.
            self._tray.set_open_folder_enabled(
                bool(self._local_path) and os.path.isdir(self._local_path)
            )
        self._act_stop.setEnabled(is_running and not is_stopping)
        # The toolbar Stop button follows the same rule as the menu action. It is
        # not cosmetic: ``_reset_ui_stopped`` disables it, and if the engine is
        # still running (a scoped op finalized early, a continuous run) nothing
        # else re-enabled it — leaving a live run with neither Start nor Stop
        # clickable until the app was restarted.
        self._btn_stop.setEnabled(is_running and not is_stopping)
        can_preview = self._can_preview_changes()
        self._act_preview_changes.setEnabled(can_preview)
        self._btn_preview_changes.setEnabled(can_preview)
        if self._tray:
            self._tray.set_preview_changes_enabled(can_preview)
        # Send/Receive of a selection are one-shot commands: only while stopped.
        idle = not is_running and not is_stopping
        # The File menu follows the whole selection (see
        # ActionsMixin._refresh_file_actions): with a multi-selection an action
        # is enabled only when it applies to every selected entry.
        self._refresh_file_actions()
        self._file_panel._table.set_sync_active(is_running and not is_stopping)
        self._apply_button_styles()
        self._update_preview_changes_tooltip()

    def _update_preview_changes_tooltip(self) -> None:
        """Explain the comparison entry point in its current state.

        One text for the menu action, the icon-only action-bar button and the
        tray entry, so the click never needs a second guess: the merged action
        answers in both engine states, and the tooltip says which answer this
        state produces, why the control is off (a comparison in flight,
        Simulation Mode) and when the folder was last compared — the app also
        compares on its own on every connect, so the recency is what most often
        saves the click.
        """
        button = getattr(self, "_btn_preview_changes", None)
        if button is None:
            return
        if self._comparison_in_flight:
            tooltip = tr("sync.state.checking")
        elif self._engine.is_running and is_simulation_mode():
            tooltip = tr("simulation.tip")
        elif self._engine.is_running and not self._connected:
            tooltip = tr("tip.compare_waiting")
        else:
            tooltip = tr("tip.preview_changes")
            if self._last_check_at is not None:
                # A comparison is a moment, not a run: the stamp outlives the
                # engine and saves a click that would answer the same.
                stamp = QLocale().toString(self._last_check_at, QLocale.FormatType.ShortFormat)
                tooltip = f"{tooltip} · {tr('tip.compare_last').replace('{time}', stamp)}"
        button.setToolTip(tooltip)
        # The menu is built after this helper's first run (see ``_load_ui``).
        act = getattr(self, "_act_preview_changes", None)
        if act is not None:
            act.setToolTip(tooltip)
        if self._tray:
            self._tray.set_preview_changes_tooltip(tooltip)

    @Slot(str)
    def _append_log(self, payload: str) -> None:
        """Append one or more log lines, colored with the engine/theme palette.

        The lines may carry the client's SGR sequences (it is launched with
        ``--color=always``); ``styled_runs`` turns them into char formats and
        strips them from the text, so ``toPlainText()`` stays clean. A burst
        arrives as one payload (the engine batches a whole stdout read), so it is
        split back and inserted in a single edit block.
        """
        lines = payload.split("\n")
        self._buffer_log_lines(lines)
        self._insert_log_lines(lines)

    def _buffer_log_lines(self, lines: list[str]) -> None:
        """Keep the raw lines in the active share's bounded log history.

        The per-line cap mirrors the document path so a pathological line is
        bounded here too; ``maxlen`` drops the oldest lines in C.
        """
        share_id = getattr(self, "_log_active_share", "")
        if not share_id:
            return
        buffer = self._log_buffers.get(share_id)
        if buffer is None:
            buffer = deque(maxlen=_LOG_MAX_BLOCKS)
            self._log_buffers[share_id] = buffer
        for line in lines:
            if len(line) > _LOG_LINE_MAX_CHARS:
                line = line[:_LOG_LINE_MAX_CHARS] + _LOG_LINE_ELLIPSIS
            buffer.append(line)

    def _seed_log_buffer_from_view(self, share_id: str) -> None:
        """Seed *share_id*'s buffer with the lines currently shown (first adopt)."""
        if share_id not in self._log_buffers:
            self._log_buffers[share_id] = deque(
                self._log_view.toPlainText().splitlines(), maxlen=_LOG_MAX_BLOCKS
            )

    def _set_log_share(self, share_id: str) -> None:
        """Show *share_id*'s log history (each share keeps its own buffer)."""
        self._log_active_share = share_id
        self._log_view.clear()
        buffer = self._log_buffers.get(share_id)
        if buffer:
            self._insert_log_lines(list(buffer))

    def _insert_log_lines(self, lines: list[str]) -> None:
        """Insert *lines* at the tail in one edit block, keeping the scroll state.

        One edit block for the whole batch: the document layout, the block
        eviction (``maximumBlockCount``) and the scrollbar settle once, instead
        of once per line (measured 7-17x faster on a panel already at its cap).
        """
        vertical = self._log_view.verticalScrollBar()
        horizontal = self._log_view.horizontalScrollBar()
        # Appending moves the cursor to the end of the new (possibly long) line,
        # which would scroll horizontally to the right edge and hide the start of
        # the line. Keep the user's horizontal position (left by default).
        # Also auto-follow the tail only when the user is already at the bottom;
        # otherwise a reader scrolled up keeps their place.
        horizontal_pos = horizontal.value()
        vertical_pos = vertical.value()
        at_bottom = vertical_pos >= vertical.maximum() - 2

        cursor = self._log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        text_document = self._log_view.document()
        theme = getattr(self, "_log_theme", THEME_LIGHT)
        cursor.beginEditBlock()
        for line in lines:
            if text_document.blockCount() > 1 or not text_document.isEmpty():
                cursor.insertBlock()
            _insert_log_line(cursor, line, theme)
        cursor.endEditBlock()
        self._log_view.setTextCursor(cursor)

        if at_bottom:
            vertical.setValue(vertical.maximum())
        else:
            vertical.setValue(vertical_pos)
        horizontal.setValue(horizontal_pos)

    def _rerender_log(self) -> None:
        """Re-render the log panel after a theme change.

        The document keeps no SGR sequences, so the re-render recolors from the
        shared level/label mapping: same semantic categories, no encoded colors.
        """
        text = self._log_view.toPlainText()
        self._log_view.clear()
        if text:
            self._insert_log_lines(text.splitlines())

    def _append_desktop_log(self, level: str, message: str) -> None:
        """Append a desktop-originated line in the canonical log grammar.

        Client lines carry ``<timestamp> - [pid] [client_id] LEVEL:``; the
        desktop has no client session, so it renders its own pid and puts
        ``desktop`` in the correlation slot. Same layout, same level vocabulary,
        same UTC timestamp: one reader (and one regex, in
        ``hsync_common.logger``) covers both producers, so the panel reads as a
        single log. See ``docs/log-labels.md``.
        """
        self._append_log(format_log_line(level, message, fields=("desktop",)))

    def _mark_new_run(self) -> None:
        """Open a new run in the log; the panel keeps the previous run's lines.

        A restart appends to the panel instead of wiping it, so every run opens
        with an explicit boundary marker and the view jumps to it (the earlier
        lines stay above, reachable by scrolling). Simulation Mode keeps its own
        notice as the boundary, so a run never opens with two markers.
        """
        self._append_desktop_log(
            "INFO",
            tr("simulation.log_start") if is_simulation_mode() else tr("sync.log_start"),
        )
        # The jump waits one event-loop turn: the scroll range is only final
        # once Qt has laid the new block out, and a jump computed before that
        # stops short of the tail.
        QTimer.singleShot(0, self._scroll_log_to_end)

    def _scroll_log_to_end(self) -> None:
        """Bring the newest log line into view."""
        bar = self._log_view.verticalScrollBar()
        bar.setValue(bar.maximum())

    @Slot(str)
    def _on_engine_event_error(self, payload: str) -> None:
        """Record an engine event the desktop could not interpret.

        The payload is truncated by the engine, so it is a diagnostic only: it
        is logged as ``[EVENT ERROR]`` under the desktop's own identity and
        never surfaced as a toast (a malformed envelope is not a user action
        failing).
        """
        self._append_desktop_log("ERROR", f"[EVENT ERROR] {payload}")

    @Slot(str, str, str)
    def _on_engine_error(self, message: str, reason: str = "", code: str = "") -> None:
        """Record an engine error, mirror it into the log, and surface it.

        During a scoped Send/Receive the error is that operation's outcome
        (``_finish_selection_sync``); otherwise it raises the generic error
        notification. An engine launch failure is skipped here — ``_start_engine``
        reports it once with its own dialog.
        """
        self._last_engine_error = message
        if message:
            self._append_desktop_log("ERROR", message)
        if reason == "connection":
            # The link is down and the client retries the comparison on its own:
            # the state says so instead of reading "checking" while nothing can
            # progress, and the per-file rows keep their last known value. ``code``
            # is the stable transport cause the badge shows in its tooltip.
            self._conn_reason_code = code
            self._link_down = True
            self._set_sync_state("offline" if self._ever_connected else "idle")
            self._render_connection_badge()
        if message and self._comparison_in_flight:
            # The preview/classification failed. Its end marker still arrives, so
            # record it here: a failed comparison is never a "last check". The
            # plan will never arrive either, so its preparing toast ends here.
            self._comparison_errored = True
            self._exit_preparing_plan_ui()

        # A structured startup failure: the client is exiting, and
        # ``process_finished`` presents it once with the exit code. Do not toast
        # here and do not finalize a scoped op (the finish handler owns both).
        if reason == "startup":
            self._startup_error_message = message
            return

        # An engine launch failure has its own dialog (see ``_start_engine``);
        # ignore it here so it is never surfaced or finalized twice.
        if self._engine_starting:
            return

        if self._selection_sync_active:
            p2p_enabled = bool(
                QSettings(SETTINGS_ORG, SETTINGS_APP).value(
                    "p2p/enabled", DEFAULT_P2P_ENABLED, bool
                )
            )
            outcome = (
                "server_unreachable" if reason == "connection" and not p2p_enabled else "failed"
            )
            self._finish_selection_sync(outcome)
            return

        if reason == "share_missing":
            self._report_missing_share()
            return

        if message:
            self._notify_error(tr("notif.error"), message)

    def _report_missing_share(self) -> None:
        """Name the share the server does not have, with the remedy.

        The client reports ``reason="share_missing"`` when the first listing of a
        cycle answers 404: the share does not exist on the server, or the account
        cannot reach it. The client's own sentence is technical (it names the
        bucket and the admin command); the window says it in the user's terms and
        points at Settings, where the share can be created.
        """
        share = self._share_store.active()
        name = share.name if share is not None else ""
        title = tr("notif.share_missing_title")
        text = tr("notif.share_missing_msg").replace("{name}", name)
        # The preview fails before the sync does, so the same condition arrives
        # twice per cycle: notify once per episode (the warning clears on the
        # first cycle that completes).
        already = any(w.key == "share_missing" for w in self._problems.warnings)
        self._problems.record_warning("share_missing", title, text)
        if not already:
            self._notify_warning(title, text)

    def _is_p2p_mode(self) -> bool:
        return bool(
            QSettings(SETTINGS_ORG, SETTINGS_APP).value("p2p/enabled", DEFAULT_P2P_ENABLED, bool)
        )

    def _server_configured(self) -> bool:
        """True when Server Mode has an endpoint (engine-reported or configured)."""
        if getattr(self._engine, "server_ip", ""):
            return True
        configured = str(
            QSettings(SETTINGS_ORG, SETTINGS_APP).value("connection/server_url", "", str)
        )
        return bool(configured.strip())

    def _connection_problem_key(self, p2p: bool) -> str:
        """The top connectivity warning (p2p), as a localized reason key, or "".

        Mutually ordered by how actionable the cause is: no master, then the
        discovery server, then the relay, then the one-shot no-peer abort.
        """
        if not p2p:
            return ""
        warnings = {w.key: w for w in self._problems.warnings if w.kind == WARNING}
        if "master" in warnings:
            return "conn.p2p.no_master"
        rendezvous = warnings.get("rendezvous")
        if rendezvous is not None:
            if rendezvous.reason == "token_required":
                return "conn.p2p.rendezvous_token"
            return "conn.p2p.rendezvous_unreachable"
        if "relay" in warnings:
            return "conn.p2p.relay_unavailable"
        if self._conn_reason_override == "no_peers":
            return "conn.p2p.no_peers"
        return ""

    def _derived_connection_badge(self, p2p: bool) -> tuple[str, str]:
        """Derive (state, reason key) from the shared link facts (first match wins)."""
        status = getattr(self, "_link_status", "")
        # Rule 1: a finished/stopped run is neutral, before ``_ever_connected``
        # (reset at process end) can make "disconnected" look like a loss. A
        # never-started app keeps the endpoint's own tooltip: nothing to announce.
        if not self._engine.is_running:
            if (
                self._user_stopped
                or self._ever_connected
                or self._link_down
                or status in ("stopping", "disconnected")
            ):
                return "stopped", "conn.state.stopped"
            return "healthy", ""
        if status in ("stopping", "disconnected") and self._user_stopped:
            return "stopped", "conn.state.stopped"
        if status == "connected":
            return "healthy", ""
        transport = f"conn.reason.{self._conn_reason_code}" if self._conn_reason_code else ""
        problem = self._connection_problem_key(p2p)
        if transport or self._link_down or problem:
            return "problem", transport or problem or "conn.reason.unknown"
        if status == "connecting":
            return "connecting", "conn.state.searching" if p2p else "conn.state.connecting"
        if status in ("", "waiting") and not self._ever_connected:
            if p2p and status == "waiting":
                return "connecting", "conn.state.waiting_device"
            return "connecting", "conn.state.searching" if p2p else "conn.state.connecting"
        if status in ("waiting", "disconnected") and self._ever_connected:
            return "lost", "conn.state.lost"
        return "stopped", "conn.state.stopped"

    def _connection_tooltip(self, state: str, p2p: bool) -> str:
        lines = [self._conn_reason] if self._conn_reason else []
        if state in ("problem", "lost") and not p2p:
            lines.append(tr("conn.tip.retry"))
        lines.append(tr("conn.tip.details"))
        return "\n".join(line for line in lines if line)

    @staticmethod
    def _compose_status_badge(
        base, state: str, dpr: float, size_px: int, *, replace_base: bool = False
    ):
        """Draw the status glyph for the endpoint.

        Healthy is handled by the caller with the plain mode icon. An alert,
        error or stopped state replaces the icon entirely (``replace_base``) so
        the mode is never visible underneath the badge; a neutral/in-progress
        state overlays a small corner dot that annotates — without hiding — the
        mode icon.
        """
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap

        colors = {
            "connecting": QColor("#f0a000"),
            "lost": QColor("#d32f2f"),
            "problem": QColor("#d32f2f"),
            "stopped": QColor("#9e9e9e"),
        }
        glyphs = {"connecting": "", "lost": "!", "problem": "!", "stopped": "\u2013"}
        if replace_base:
            # A glyph that replaces the icon: centred and large enough to read.
            diameter = max(6, round((size_px - 4) * dpr))
            pixmap = QPixmap(base.size())
            pixmap.fill(Qt.GlobalColor.transparent)
            x = (pixmap.width() - diameter) // 2
            y = (pixmap.height() - diameter) // 2
        else:
            # A dot that only annotates the icon: small and in the bottom-right
            # corner, so the mode icon stays readable (a full-size overlay hid it).
            diameter = max(4, round(size_px * _STATUS_OVERLAY_DOT_RATIO * dpr))
            pixmap = base
            x = pixmap.width() - diameter
            y = pixmap.height() - diameter
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor("#ffffff"), max(1, round(dpr))))
        painter.setBrush(colors.get(state, QColor("#9e9e9e")))
        painter.drawEllipse(x, y, diameter, diameter)
        glyph = glyphs.get(state, "")
        if glyph:
            font = QFont(painter.font())
            font.setPixelSize(max(6, round(diameter * 0.8)))
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(QRect(x, y, diameter, diameter), Qt.AlignmentFlag.AlignCenter, glyph)
        painter.end()
        if replace_base:
            pixmap.setDevicePixelRatio(dpr)
        return pixmap

    def _render_connection_badge(self) -> None:
        """Render the endpoint connectivity badge from the shared link state."""
        icon = getattr(self, "_remote_icon", None)
        if icon is None:
            return
        p2p = self._is_p2p_mode()
        state, reason_key = self._derived_connection_badge(p2p)
        self._conn_state = state
        self._conn_reason = tr(reason_key) if reason_key else ""
        if not self._local_path or (not p2p and not self._server_configured()):
            # Nothing to announce: `_update_path_display` owns the hidden widgets.
            self._conn_state = "stopped"
            self._conn_badge_replaces_icon = False
            return
        from hsync_desktop.icons import HEADER_ICON_PX
        from hsync_desktop.icons import icon as get_icon

        base_name = "network-p2p" if p2p else "network-cloud"
        dpr = icon.devicePixelRatioF() or 1.0
        base = get_icon(base_name).pixmap(round(HEADER_ICON_PX * dpr), round(HEADER_ICON_PX * dpr))
        base.setDevicePixelRatio(dpr)
        label = getattr(self, "_remote_label", None)
        if state == "healthy":
            self._conn_badge_replaces_icon = False
            icon.setPixmap(base)
            tip = getattr(self, "_remote_base_tip", "") or ""
            icon.setToolTip(tip)
            icon.setAccessibleName(tip)
            icon.setCursor(Qt.CursorShape.ArrowCursor)
            if label is not None:
                label.setToolTip(tip)
            return
        # A warning (alert/error or a stopped run) replaces the mode icon so it is
        # never visible underneath the badge; only the in-progress dot overlays it.
        # Clearing the warning (healthy above) brings the mode icon back.
        replace_base = state in ("problem", "lost", "stopped")
        self._conn_badge_replaces_icon = replace_base
        icon.setPixmap(
            self._compose_status_badge(base, state, dpr, HEADER_ICON_PX, replace_base=replace_base)
        )
        tip = self._connection_tooltip(state, p2p)
        icon.setToolTip(tip)
        icon.setAccessibleName(tip)
        icon.setCursor(Qt.CursorShape.PointingHandCursor)
        if label is not None:
            label.setToolTip(tip)

    def _show_connection_badge_menu(self) -> None:
        """Menu for the endpoint badge: open the log, or the server settings."""
        if self._conn_state == "healthy" or not self._local_path:
            return
        menu = QMenu(self)
        act_log = menu.addAction(tr("conn.menu.show_log"))
        act_settings = None
        if not self._is_p2p_mode():
            act_settings = menu.addAction(tr("conn.menu.settings"))
        chosen = menu.exec(self._remote_icon.mapToGlobal(self._remote_icon.rect().bottomLeft()))
        if chosen is act_log:
            self._show_log_panel()
        elif act_settings is not None and chosen is act_settings:
            from hsync_desktop.settings.tab_indices import _SERVER_TAB_INDEX

            self._open_settings(initial_tab=_SERVER_TAB_INDEX)

    @Slot(QPoint)
    def _show_log_context_menu(self, pos: QPoint) -> None:
        """Show custom context menu for the log viewer."""
        menu = QMenu(self._log_view)
        act_select_all = menu.addAction(tr("log.select_all"))
        act_select_all.setShortcuts(
            _standard_shortcuts(QKeySequence.StandardKey.SelectAll, "Ctrl+A")
        )
        act_copy = menu.addAction(tr("log.copy"))
        act_copy.setShortcuts(_standard_shortcuts(QKeySequence.StandardKey.Copy, "Ctrl+C"))
        menu.addSeparator()
        act_clear = menu.addAction(tr("log.clear"))
        # Enable/disable based on state
        act_copy.setEnabled(self._log_view.textCursor().hasSelection())
        act_select_all.setEnabled(bool(self._log_view.toPlainText()))
        act_clear.setEnabled(bool(self._log_view.toPlainText()))
        # Execute and handle
        action = menu.exec(self._log_view.mapToGlobal(pos))
        if action == act_select_all:
            self._log_view.selectAll()
        elif action == act_copy:
            self._log_view.copy()
        elif action == act_clear:
            self._log_view.clear()

    def _create_info_banner(self) -> QFrame:
        """Create a hidden overlay toast for transient feedback."""
        banner = QFrame()
        banner.setObjectName("infoBanner")
        banner.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # 640px keeps the toast comfortable without spanning the window; the
        # effective width is sized in _position_info_banner (220px..this cap).
        banner.setMaximumWidth(640)
        banner.setStyleSheet(
            "#infoBanner {"
            "  background-color: rgba(13, 110, 253, 0.85);"
            "  border-radius: 8px;"
            "  padding: 8px 16px;"
            "}"
            '#infoBanner[severity="success"] { background-color: rgba(25, 135, 84, 0.85); }'
            '#infoBanner[severity="warning"] { background-color: rgba(180, 83, 9, 0.85); }'
            '#infoBanner[severity="error"] { background-color: rgba(220, 53, 69, 0.85); }'
            "#infoBannerLabel {"
            "  color: #ffffff;"
            "  font-weight: bold;"
            "  font-size: 14px;"
            "}"
            "#infoBannerClose {"
            "  color: #ffffff;"
            "  font-weight: bold;"
            "  font-size: 18px;"
            "  background: transparent;"
            "  border: none;"
            "  padding: 0 4px;"
            "}"
            "#infoBannerClose:hover { color: #ccc; }"
            "#infoBannerLink {"
            "  color: #ffffff;"
            "  font-size: 12px;"
            "}"
            "#infoProgress {"
            "  background: rgba(255, 255, 255, 0.35);"
            "  border: none;"
            "  border-radius: 2px;"
            "}"
            "#infoProgress::chunk {"
            "  background: #ffffff;"
            "  border-radius: 2px;"
            "}"
        )
        outer = QVBoxLayout(banner)
        outer.setContentsMargins(14, 8, 10, 8)
        outer.setSpacing(4)
        row = QHBoxLayout()
        self._info_banner_label = QLabel("", banner)
        self._info_banner_label.setObjectName("infoBannerLabel")
        self._info_banner_label.setWordWrap(True)
        row.addWidget(self._info_banner_label, 1)
        close_btn = QPushButton("✕", banner)
        close_btn.setObjectName("infoBannerClose")
        close_btn.setFixedSize(26, 26)
        close_btn.clicked.connect(self._hide_info_banner)
        row.addWidget(close_btn)
        outer.addLayout(row)
        # Indeterminate bar for ongoing work (shown only for kind="progress").
        self._info_progress = QProgressBar(banner)
        self._info_progress.setObjectName("infoProgress")
        self._info_progress.setRange(0, 0)
        self._info_progress.setFixedHeight(5)
        self._info_progress.setTextVisible(False)
        self._info_progress.hide()
        outer.addWidget(self._info_progress)
        # Actionable warnings carry a link to the guide that holds the
        # per-platform remedy: the banner is an overlay, so the text alone cannot
        # be selected or clicked. Created once (the only target is the guide) and
        # toggled, so language changes rebuild it through set_help_link_text.
        self._info_banner_link = help_link(
            "notif.open_guide", TROUBLESHOOTING, color=_TOAST_LINK_COLOR
        )
        self._info_banner_link.setObjectName("infoBannerLink")
        self._info_banner_link.hide()
        outer.addWidget(self._info_banner_link)
        banner.hide()
        return banner

    def _position_info_banner(self) -> None:
        """Place the toast bottom-right, above the bottom bar."""
        # isHidden() is the explicit hide state; isVisible() is also false when
        # the main window is not shown yet (startup/background), which must not
        # skip the placement.
        if self._info_banner.isHidden():
            return
        central = self.centralWidget()
        if central is None:
            return
        # Comfortably larger than the old 420px cap, but not full-width; at
        # least 220px and never wider than the window. Re-applied on resize.
        width = min(640, max(220, central.width() - 32))
        self._info_banner.setFixedWidth(width)
        self._info_banner.adjustSize()
        margin = 16
        status_top = self._status_label.mapTo(central, QPoint(0, 0)).y()
        y = status_top - self._info_banner.height() - 8
        x = central.width() - self._info_banner.width() - margin
        self._info_banner.move(max(margin, x), max(margin, y))

    def _show_info_banner(
        self,
        message: str,
        auto_hide_ms: int | None = None,
        kind: str = "info",
        *,
        title: str = "",
        help_url: str | None = None,
    ) -> None:
        """Show the overlay toast.

        ``kind`` is ``progress``, ``info``, ``success``, ``warning``, ``notice``
        or ``error``. Every kind auto-hides: a toast is a notification, and the
        problems that still hold are listed by the status-bar badge instead of
        parked on screen. An outcome lingers a little longer than a status line.
        ``auto_hide_ms`` overrides the default (``<= 0`` keeps it visible until
        ``_hide_info_banner``). ``help_url`` reveals the guide link inside the
        toast (an actionable warning); every other toast hides it.
        """
        severity = _SEVERITY_BY_KIND.get(kind, "info")
        self._info_banner_kind = kind
        self._info_banner_label.setText(self._toast_text(kind, title, message))
        self._info_banner_link.setVisible(bool(help_url))
        if help_url:
            set_help_link_url(self._info_banner_link, "notif.open_guide", help_url)
        # The background colour is driven by a dynamic property so a single
        # stylesheet carries every severity; repolish applies the new match.
        self._info_banner.setProperty("severity", severity)
        style = self._info_banner.style()
        style.unpolish(self._info_banner)
        style.polish(self._info_banner)
        self._info_progress.setVisible(kind == "progress")
        self._info_banner.adjustSize()
        self._info_banner.show()
        self._position_info_banner()
        self._info_banner.raise_()
        if auto_hide_ms is None:
            # Every kind auto-hides: a toast is a notification, not a state, and
            # what still holds lives in the problems badge. An outcome lingers a
            # little longer than a status line.
            auto_hide_ms = 20000 if kind in ("error", "warning") else 15000
        if auto_hide_ms > 0:
            self._info_timer.start(auto_hide_ms)
        else:
            self._info_timer.stop()

    @staticmethod
    def _toast_text(kind: str, title: str, message: str) -> str:
        """Compose the toast label, adding a severity glyph and title.

        ``info``/``progress`` keep their plain message; ``error``/``warning``/
        ``success`` prefix a glyph and (when given) the translated title, so the
        severity is recognisable without relying on colour.
        """
        icon = _SEVERITY_ICON.get(kind)
        if not icon:
            return message
        return f"{icon} {title} — {message}" if title else f"{icon} {message}"

    def _notify_error(self, title: str, message: str) -> None:
        """Surface an error in-app (always) and via the OS when out of focus."""
        if self._user_stopped:
            return
        self._show_info_banner(message, kind="error", title=title)
        if self._notifier:
            self._notifier.error(title, message)

    def _notify_warning(
        self,
        title: str,
        message: str,
        category: str = "connection",
        *,
        help_url: str | None = None,
    ) -> None:
        """Surface a warning in-app (always) and via the OS when out of focus.

        ``help_url`` adds the guide link inside the banner only: a system
        notification is not clickable, so an actionable warning must keep its
        remedy visible in the window as well.
        """
        self._show_info_banner(message, kind="warning", title=title, help_url=help_url)
        if self._notifier:
            self._notifier.warning(title, message, category=category)

    def _on_engine_warning(
        self,
        message: str,
        source: str = "",
        transient: bool = False,
        details: dict[str, object] | None = None,
    ) -> None:
        """Surface a non-fatal engine warning.

        ``transient`` marks a condition that heals itself (dropped real-time
        events, a file that kept changing, unreadable files recovered by the next
        scan): it shows an auto-hiding toast and never a system notification,
        because the user cannot act on it.

        A persistent warning (a degraded watcher, an unreachable rendezvous, a
        stalled safety net, a missing shared folder, low disk space) is a *state*:
        it is recorded in the problems badge, which names it and outlives the
        toast, and it raises a notification that auto-hides. The client retracts
        it with ``warning_cleared`` when the condition heals, so the badge never
        reports a problem that is gone.

        A persistent warning also carries the remediation the client's ``reason``
        and numbers imply (a host kernel limit the user must raise) plus a link
        to the guide: the fallback keeps syncing, so without the remedy the same
        warning returns at every start.

        The client already deduplicates the stream per ``(source, message)``
        window, which is what keeps a flapping condition from becoming a storm.
        """
        if not message:
            return
        self._append_desktop_log("WARNING", message)
        if self._user_stopped:
            # The user stopped the run: a degraded watcher/rendezvous is no longer
            # actionable and must not reopen a notification they just dismissed.
            return
        remedy = remedy_text(source, details)
        text = f"{message}\n{remedy}" if remedy else message
        if transient:
            self._show_info_banner(text, kind="notice", title=tr("notif.warning"))
            return
        # The host-remedy guide is only useful for the watcher causes that carry
        # the commands; every other persistent warning (including the rendezvous
        # token refusal, whose remedy points at Settings) keeps the desktop
        # symptom guide.
        help_url = WATCHER_LIMITS if source == "watcher" and remedy else TROUBLESHOOTING
        self._problems.record_warning(
            source, message, remedy, help_url, str((details or {}).get("reason", ""))
        )
        self._notify_warning(tr("notif.warning"), text, category="warnings", help_url=help_url)

    @Slot(str)
    def _on_engine_warning_cleared(self, source: str) -> None:
        """The condition *source* reported no longer holds: drop it from the badge."""
        self._problems.clear_warning(source)

    def _hide_info_banner(self) -> None:
        """Hide the toast and stop its auto-hide timer."""
        self._info_timer.stop()
        self._info_banner.hide()
        self._info_banner_kind = None

    def _clear_run_toast(self, *, across_runs: bool = False) -> None:
        """Hide the toast on a run boundary.

        A finished process keeps its outcome on screen until the toast's own
        auto-hide runs out. A new run clears whatever the previous one left: the
        state it described was the previous run's problems, and those were reset
        with it.
        """
        if across_runs or self._info_banner_kind not in _SURVIVES_FINISH:
            self._hide_info_banner()

    def _apply_button_styles(self) -> None:
        """Apply colored styles to the Start/Stop/Check-for-changes buttons."""
        from hsync_desktop.icons import themed_icon

        # Start button: green background when enabled
        self._btn_start.setStyleSheet(
            _BTN_START_ACTIVE if self._btn_start.isEnabled() else _BTN_IDLE
        )
        # Start icon: white when enabled, dark when disabled
        start_icon_color = "#FFFFFF" if self._btn_start.isEnabled() else "#424242"
        self._btn_start.setIcon(themed_icon("media-playback-start", start_icon_color))

        # Stop button: red background when enabled
        self._btn_stop.setStyleSheet(_BTN_STOP_ACTIVE if self._btn_stop.isEnabled() else _BTN_IDLE)
        # Stop icon: white when enabled, dark when disabled
        stop_icon_color = "#FFFFFF" if self._btn_stop.isEnabled() else "#424242"
        self._btn_stop.setIcon(themed_icon("media-playback-stop", stop_icon_color))

        self._btn_preview_changes.setStyleSheet(
            _BTN_PREVIEW_ACTIVE if self._btn_preview_changes.isEnabled() else _BTN_IDLE
        )
        # Check-for-changes icon: white when enabled, dark when disabled
        preview_icon_color = "#FFFFFF" if self._btn_preview_changes.isEnabled() else "#424242"
        self._btn_preview_changes.setIcon(themed_icon("view-refresh", preview_icon_color))

    # ── Actions ──────────────────────────────────────────────────────────

    def _refresh_icons_for_theme(self) -> None:
        """Refresh all icons after theme change."""
        from hsync_desktop.icons import clear_icon_cache

        clear_icon_cache()
        # Check-for-changes button icon with theme-appropriate colors
        self._apply_button_styles()
        # Refresh role icon (neutral/known, re-coloured for the theme)
        self._retranslate_role()
        # Refresh path display (includes folder, sync direction, and remote icons)
        self._update_path_display()
        # Refresh file panel icons
        self._file_panel.refresh_icons_for_theme()

    def _retranslate_role(self) -> None:
        """Render the role icon/label once the election has decided the role.

        Nothing is shown before the election: a neutral placeholder icon read as
        an unfinished/unknown state. Icon and text appear together once known.
        """
        from PySide6.QtGui import QPalette

        from hsync_desktop.icons import icon as get_icon
        from hsync_desktop.icons import themed_icon

        if self._is_master is None:
            self._role_label.setText("")
            self._role_label.setToolTip("")
            self._role_icon.clear()
            self._role_icon.setToolTip("")
        elif self._is_master:
            self._role_label.setText(tr("role.master"))
            self._role_label.setToolTip(tr("role.master_tip"))
            accent = self._role_icon.palette().color(QPalette.ColorRole.Highlight).name()
            self._role_icon.setPixmap(themed_icon("role-master", accent).pixmap(16, 16))
            self._role_icon.setToolTip(tr("role.master_tip"))
        else:
            self._role_label.setText(tr("role.client"))
            self._role_label.setToolTip(tr("role.client_tip"))
            self._role_icon.setPixmap(get_icon("role-client").pixmap(16, 16))
            self._role_icon.setToolTip(tr("role.client_tip"))
        self._apply_role_visibility()

    def _apply_role_visibility(self) -> None:
        """Show the role in p2p once known; the text also requires a connection."""
        p2p_enabled = bool(
            QSettings(SETTINGS_ORG, SETTINGS_APP).value("p2p/enabled", DEFAULT_P2P_ENABLED, bool)
        )
        self._role_icon.setVisible(p2p_enabled and self._role_known)
        self._role_label.setVisible(p2p_enabled and self._role_known and self._connected)

    def _render_share_size(self) -> None:
        """Render the shared-folder size as ``local / total`` (``-1`` = unknown)."""
        local = self._share_local_bytes
        total = self._share_total_bytes
        if local < 0:
            text = "—"
        else:
            total_text = format_bytes(total) if total >= 0 else "—"
            text = (
                tr("label.share_size_fmt")
                .replace("{local}", format_bytes(local))
                .replace("{total}", total_text)
            )
        self._share_size_label.setText(text)

    @Slot(object)
    def _on_share_size_changed(self, total_bytes: int) -> None:
        """Update the local size from the folder scan."""
        self._share_local_bytes = total_bytes
        self._render_share_size()

    @Slot(str, str)
    def _on_import_finished(self, message: str, kind: str) -> None:
        """Surface the outcome of a drag & drop import as a toast."""
        title = tr("notif.success") if kind == "success" else tr("notif.warning")
        self._show_info_banner(message, kind=kind, title=title)

    def _apply_log_visibility(self) -> None:
        """Show or hide the log panel based on settings."""
        show_log = is_log_panel_visible()
        if show_log:
            self._log_view.show()
            # Restore splitter sizes if log was hidden
            sizes = self._main_splitter.sizes()
            if sizes[1] == 0:
                self._main_splitter.setSizes([400, 200])
        else:
            self._log_view.hide()
            # Give all space to file panel
            sizes = self._main_splitter.sizes()
            total = sum(sizes)
            self._main_splitter.setSizes([total, 0])

    def _show_log_panel(self) -> None:
        """Reveal the log panel (the startup-failure dialog's "Show log")."""
        self._log_view.show()
        sizes = self._main_splitter.sizes()
        if sizes[1] == 0:
            self._main_splitter.setSizes([400, 200])

    # ── Window management ────────────────────────────────────────────────
