# mypy: disable-error-code="attr-defined"
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Regroup the Sync/p2p/Server tabs into ``QGroupBox`` sections.

Each mode tab also opens with its one-line purpose label. Split out of
``SettingsDialog`` (the methods are pure UI construction on the dialog
instance); ``SettingsDialog`` keeps thin wrappers calling these.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from hsync_desktop.docs_links import RENDEZVOUS_SETUP, SERVER_SETUP
from hsync_desktop.i18n import tr
from hsync_desktop.settings.form_helpers import _action_row
from hsync_desktop.settings.tab_indices import (
    _ADVANCED_TAB_INDEX,
    _CONNECTION_TAB_INDEX,
    _GENERAL_TAB_INDEX,
    _SYNC_TAB_INDEX,
)
from hsync_desktop.widgets.forms import add_row
from hsync_desktop.widgets.labels import muted_label
from hsync_desktop.widgets.links import help_link
from hsync_desktop.widgets.text import escape_mnemonics

if TYPE_CHECKING:
    from hsync_desktop.settings.dialog import SettingsDialog

# Desktop settings pages never stretch a form across the whole window: the
# content keeps one bounded column, centred in the page, so controls stay a
# readable width whatever the window size. This is the measure every tab shares;
# ``tab_builders.fit_column_width`` raises it for the one thing that cannot
# reflow inside it — an action button, whose label neither wraps nor elides.
_CONTENT_MAX_WIDTH = 640
# ``tab_builders.finalize_size`` keeps the dialog at least 640 px wide; the mode
# option sentences must wrap inside that page instead of asking for more. The cap
# includes the label's own insets, so it is the text measure plus the 24/20 px
# indents ``_mode_line`` applies.
_TAB_DESCRIPTION_MAX_WIDTH = _CONTENT_MAX_WIDTH - 40


class _CenteredColumn(QWidget):
    """Keep one child centred in one reading column, full height.

    A plain box layout either stretches the column across the whole window or
    leaves it at its size hint beside the spacer items (Qt gives the extra space
    to the spacers). This wrapper gives the child exactly
    ``min(width, max_width)``, so the settings page keeps one bounded reading
    column, centred when the window grows.

    ``max_width`` is a hard cap: every tab keeps the same measure whatever its
    content asks for, and the rows adapt instead (captions wrap, action rows
    stack — see ``widgets/forms.py::add_row`` and ``_ActionRow``). A cap that
    yields to a child's size hint makes the column, and the window behind it,
    follow the widest label of the widest tab — which at a large system font or
    in a long translation is not the same tab on every desktop.

    The width always belongs to the host: a parent layout stretches the wrapper,
    a scroll area sizes it to its viewport. ``reapply_size_on_layout_request``
    exists for the scroll-area host only (see ``event``).
    """

    def __init__(
        self,
        child: QWidget,
        max_width: int,
        *,
        reapply_size_on_layout_request: bool = False,
    ) -> None:
        super().__init__()
        self._child = child
        self._max_width = max_width
        self._reapply_size_on_layout_request = reapply_size_on_layout_request
        child.setParent(self)

    def _max_child_width(self) -> int:
        """The column cap, whatever the content asks for."""
        return self._max_width

    @property
    def max_width(self) -> int:
        """The measure this column was given (``tab_builders.fit_column_width``)."""
        return self._max_width

    def set_max_width(self, width: int) -> None:
        """Change the measure (``tab_builders.fit_column_width`` owns the value)."""
        if width == self._max_width:
            return
        self._max_width = width
        self._apply_child_geometry()
        self.updateGeometry()

    def _apply_child_geometry(self) -> None:
        width = min(self.width(), self._max_child_width())
        self._child.setGeometry((self.width() - width) // 2, 0, width, self.height())

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._apply_child_geometry()

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt override)
        hint = self._child.sizeHint()
        # A child's preferred height can be smaller than what it requires (a
        # label with a reserved minimum height): never advertise less than the
        # child's minimum, or the wrapper clips it.
        height = max(hint.height(), self._child.minimumSizeHint().height())
        return QSize(min(hint.width(), self._max_child_width()), height)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 (Qt override)
        # The scroll area sizes this wrapper to its minimum height when the
        # viewport is shorter, and the form layout then squeezes every row to
        # fit — clipping wrapped labels and action buttons. Demand the height
        # the content actually needs so the page scrolls instead of squashing;
        # the width stays 0 so the column can still shrink horizontally.
        return QSize(0, self._child.sizeHint().height())

    def event(self, event) -> bool:
        # A child layout change (a revealed row, a re-wrapped label) raises this
        # wrapper's minimum height, but the scroll area only re-sizes its widget
        # on a Resize event. Re-apply our own size so that event fires; otherwise
        # the page keeps the stale height and the form squeezes the new rows.
        # Only the scroll-area host may do this: resizing a plain page item to
        # its size hint shrinks it below the width its parent layout gave it, so
        # the tab description stopped matching the column of the groups below.
        if self._reapply_size_on_layout_request and event.type() == QEvent.Type.LayoutRequest:
            self.adjustSize()
        return super().event(event)


def _group_box(title_key: str) -> QGroupBox:
    """A titled group box whose title shows its ``&`` literally."""

    return QGroupBox(escape_mnemonics(tr(title_key)))


def _spanning_row(form: QFormLayout, widget: QWidget) -> None:
    """Add *widget* across both columns (see ``form_helpers._action_row``)."""

    form.addRow(widget)


def _scroll_area(widget: QWidget) -> QScrollArea:
    """A frame-less, resizable scroll area hosting ``widget`` (no horizontal scroll)."""

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(widget)
    return scroll


def _page_outer(tab: QWidget) -> QVBoxLayout:
    """The zero-margin outer layout a scrollable page hosts its scroll area in."""

    outer = QVBoxLayout(tab)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)
    return outer


def _scrollable_page(tab: QWidget) -> tuple[QVBoxLayout, QVBoxLayout]:
    """Host a page's content in a scroll area and return ``(outer, inner)``.

    ``outer`` is the page's top-level layout (the scroll area itself); ``inner``
    is the scroll content where the groups go, so a tall page scrolls instead of
    forcing the dialog to grow (see ``tab_builders.finalize_size``). The top
    inset keeps the first group box off the tab bar: the pages carry no purpose
    line, so the breathing room comes from these margins.
    """

    outer = _page_outer(tab)
    content = QWidget()
    inner = QVBoxLayout(content)
    inner.setContentsMargins(4, 16, 4, 12)
    inner.setSpacing(8)
    outer.addWidget(
        _scroll_area(
            _CenteredColumn(content, _CONTENT_MAX_WIDTH, reapply_size_on_layout_request=True)
        ),
        1,
    )
    return outer, inner


def reorganize_general_tab(dlg: SettingsDialog) -> None:
    """Reorganize the General tab into grouped sections using QGroupBox.

    Three sections, the grouping every HIG recommends (2–4 groups, none with a
    single row): appearance first (what a first run needs), then notifications,
    then the window/startup behaviour with the advanced disclosure last.
    """
    general_tab = dlg._tabs.widget(_GENERAL_TAB_INDEX)
    if not general_tab:
        return

    lbl_language: QLabel = dlg.findChild(QLabel, "lblLanguage")  # type: ignore[assignment]
    lbl_theme: QLabel = dlg.findChild(QLabel, "lblTheme")  # type: ignore[assignment]

    # Detach the original form layout.
    old = general_tab.layout()
    if old is not None:
        while old.count():
            old.takeAt(0)
        _tmp = QWidget()
        _tmp.setLayout(old)

    outer, vbox = _scrollable_page(general_tab)

    # Group 1: appearance and language (what a first launch needs).
    dlg._grp_general_appearance = _group_box("settings.group.appearance")
    f1 = QFormLayout(dlg._grp_general_appearance)
    add_row(f1, lbl_language, dlg.lang_combo)
    add_row(f1, lbl_theme, dlg.theme_combo)
    add_row(f1, dlg._lbl_font_scale, dlg.font_scale_combo)
    vbox.addWidget(dlg._grp_general_appearance)

    # Group 2: the master switch and the per-event rows it gates. The category
    # rows are flattened into this same form, so their captions and switches
    # share the page's two columns instead of a nested, differently-indented
    # block.
    dlg._grp_general_notifications = _group_box("settings.group.notifications")
    f2 = QFormLayout(dlg._grp_general_notifications)
    add_row(f2, dlg._lbl_notifications, dlg.notifications_enabled)
    f2.addRow(dlg._lbl_notifications_categories)
    for _category, (toggle, label) in dlg.notification_toggles.items():
        add_row(f2, label, toggle)
    vbox.addWidget(dlg._grp_general_notifications)

    # Group 3: window behaviour and startup. The advanced disclosure closes the
    # page: it changes what the rest of the dialog shows.
    dlg._grp_general_window = _group_box("settings.group.window")
    f3 = QFormLayout(dlg._grp_general_window)
    add_row(f3, dlg._lbl_tooltips, dlg.tooltips_enabled)
    add_row(f3, dlg._lbl_show_log_panel, dlg.show_log_panel)
    add_row(f3, dlg._lbl_start_at_login, dlg.start_at_login)
    add_row(f3, dlg._lbl_update_check, dlg.update_check)
    add_row(f3, dlg._lbl_show_advanced, dlg.show_advanced)
    vbox.addWidget(dlg._grp_general_window)

    vbox.addStretch()


def reorganize_sync_tab(dlg: SettingsDialog) -> None:
    """Reorganize the Sync tab into grouped sections using QGroupBox."""
    sync_tab = dlg._tabs.widget(_SYNC_TAB_INDEX)
    if not sync_tab:
        return

    # ── Collect label references from .ui ──────────────────
    lbl_shared: QLabel = dlg.findChild(QLabel, "lblSharedPath")  # type: ignore[assignment]
    lbl_bucket: QLabel = dlg.findChild(QLabel, "lblBucket")  # type: ignore[assignment]
    lbl_resync: QLabel = dlg.findChild(QLabel, "lblResync")  # type: ignore[assignment]
    lbl_retry: QLabel = dlg.findChild(QLabel, "lblRetryDelay")  # type: ignore[assignment]
    lbl_stability: QLabel = dlg.findChild(QLabel, "lblStabilityDelay")  # type: ignore[assignment]
    lbl_max_wait: QLabel = dlg.findChild(QLabel, "lblMaxWait")  # type: ignore[assignment]
    lbl_filter: QLabel = dlg.findChild(QLabel, "lblFilterPath")  # type: ignore[assignment]

    # ── Detach old layout ──────────────────────────────────
    old = sync_tab.layout()
    if old is not None:
        while old.count():
            old.takeAt(0)
        _tmp = QWidget()
        _tmp.setLayout(old)

    # ── Build new grouped layout inside a scroll area ──────
    _, vbox = _scrollable_page(sync_tab)

    # Group 1: Path & Bucket
    dlg._grp_path = _group_box("settings.group.path_bucket")
    f1 = QFormLayout(dlg._grp_path)
    path_row = QHBoxLayout()
    path_row.addWidget(dlg.shared_path)
    path_row.addWidget(dlg.btn_browse_shared)
    add_row(f1, lbl_bucket, dlg.bucket)
    lbl_shared.setBuddy(dlg.shared_path)
    f1.addRow(lbl_shared, path_row)
    vbox.addWidget(dlg._grp_path)

    # Group 2: Sync Mode
    dlg._grp_sync = _group_box("settings.group.sync_mode")
    f2 = QFormLayout(dlg._grp_sync)
    add_row(f2, dlg._lbl_sync_direction, dlg.sync_direction_combo)
    add_row(f2, dlg._lbl_deletion_policy, dlg.deletion_policy)
    add_row(f2, dlg._lbl_continuous, dlg.continuous)
    add_row(f2, dlg._lbl_auto_sync, dlg.auto_sync)
    add_row(f2, dlg._lbl_auto_apply, dlg.auto_apply)
    vbox.addWidget(dlg._grp_sync)

    # Group 3: Timing & Intervals
    dlg._grp_timing = _group_box("settings.group.timing")
    f3 = QFormLayout(dlg._grp_timing)
    add_row(f3, lbl_resync, dlg.resync)
    add_row(f3, lbl_retry, dlg.retry_delay)
    add_row(f3, lbl_stability, dlg.stability_delay)
    add_row(f3, lbl_max_wait, dlg.max_wait)
    vbox.addWidget(dlg._grp_timing)

    # Group 4: Advanced Options
    dlg._grp_advanced = _group_box("settings.group.advanced")
    f4 = QFormLayout(dlg._grp_advanced)
    dlg._lbl_min_free_disk_space = QLabel(tr("settings.min_free_disk_space"))
    add_row(f4, dlg._lbl_min_free_disk_space, dlg.min_free_disk_space)
    dlg._lbl_max_inbound_size = QLabel(tr("settings.max_inbound_size"))
    add_row(f4, dlg._lbl_max_inbound_size, dlg.max_inbound_size)
    add_row(f4, lbl_filter, dlg.filter_path)
    add_row(f4, dlg._lbl_compression_enabled, dlg.compression_enabled)
    add_row(f4, dlg._lbl_dry_run, dlg.dry_run)

    # Extra ignore patterns
    add_row(f4, dlg._lbl_ignore_patterns, dlg.ignore_patterns)

    # Edit .hsyncignore button (no left label, like a regular action)
    _spanning_row(f4, dlg.btn_edit_hsyncignore)

    # Maintenance: forget the folder's sync history (client-side state DB).
    _spanning_row(f4, dlg.btn_reset_state)
    vbox.addWidget(dlg._grp_advanced)

    vbox.addStretch()


def _mode_line(key: str) -> QLabel:
    """The muted sentence under one connection-mode option, capped to the column."""

    label = muted_label(tr(key))
    # Indented under the option's own text, so the two sentences read as the
    # options' subtitles rather than as page paragraphs.
    label.setContentsMargins(24, 0, 20, 8)
    label.setMaximumWidth(_TAB_DESCRIPTION_MAX_WIDTH)
    return label


def reorganize_connection_tab(dlg: SettingsDialog) -> None:
    """Reorganize the connection tab: the mode choice, then its options.

    Both modes keep their own group boxes and the page shows one of them, so it
    is never as tall as the two together (see
    ``SettingsDialog._apply_connection_mode``): the mode not in use is a single
    muted line naming what it holds.
    """

    page = dlg._tabs.widget(_CONNECTION_TAB_INDEX)
    if not page:
        return

    lbl_group: QLabel = dlg.findChild(QLabel, "lblP2pGroup")  # type: ignore[assignment]
    lbl_key: QLabel = dlg.findChild(QLabel, "lblP2pKey")  # type: ignore[assignment]
    lbl_port: QLabel = dlg.findChild(QLabel, "lblP2pPort")  # type: ignore[assignment]
    lbl_rendezvous: QLabel = dlg.findChild(QLabel, "lblRendezvousTimeout")  # type: ignore[assignment]
    lbl_server_url: QLabel = dlg.findChild(QLabel, "lblServerUrl")  # type: ignore[assignment]
    lbl_api_key: QLabel = dlg.findChild(QLabel, "lblApiKey")  # type: ignore[assignment]
    lbl_ca_cert: QLabel = dlg.findChild(QLabel, "lblCaCert")  # type: ignore[assignment]
    lbl_timeout: QLabel = dlg.findChild(QLabel, "lblHttpTimeout")  # type: ignore[assignment]

    # Rebuild the action pairs from the buttons: the containers created in the
    # builders are discarded with the old layout, so capturing their current
    # parent is fragile. A fresh row is a single aligned unit.
    manage_direct = _action_row(dlg.btn_manage_trusted_keys, dlg.btn_test_rendezvous)
    manage_server = _action_row(dlg.btn_manage_trusted_keys_server, dlg.btn_test_connection)

    old = page.layout()
    if old is not None:
        while old.count():
            old.takeAt(0)
        _tmp = QWidget()
        _tmp.setLayout(old)

    _, vbox = _scrollable_page(page)

    # Group 1: the choice itself, with the sentence that explains each option.
    dlg._grp_mode = _group_box("settings.group.connection_mode")
    mode_box = QVBoxLayout(dlg._grp_mode)
    dlg._lbl_mode_direct_desc = _mode_line("settings.p2p.description")
    dlg._lbl_mode_server_desc = _mode_line("settings.server_mode.description")
    mode_box.addWidget(dlg.mode_direct)
    mode_box.addWidget(dlg._lbl_mode_direct_desc)
    mode_box.addWidget(dlg.mode_server)
    mode_box.addWidget(dlg._lbl_mode_server_desc)
    vbox.addWidget(dlg._grp_mode)

    # Direct mode: group identity, device finding, role, tuning.
    dlg._direct_section = QWidget()
    direct = QVBoxLayout(dlg._direct_section)
    direct.setContentsMargins(0, 0, 0, 0)
    direct.setSpacing(8)

    dlg._grp_p2p_group = _group_box("settings.group.p2p_group")
    g1 = QFormLayout(dlg._grp_p2p_group)
    add_row(g1, lbl_group, dlg.p2p_group)
    add_row(g1, lbl_key, dlg.p2p_key)
    # Spanning warning: changing the shared password invalidates the key a
    # discovery server derives from it. Hidden until that condition holds.
    g1.addRow(dlg._lbl_p2p_key_rdv_warning)
    dlg._lbl_p2p_key_rdv_warning.setVisible(False)
    direct.addWidget(dlg._grp_p2p_group)

    dlg._grp_p2p_rendezvous = _group_box("settings.group.p2p_rendezvous")
    g2 = QFormLayout(dlg._grp_p2p_rendezvous)
    add_row(g2, dlg._lbl_p2p_rendezvous, dlg.p2p_rendezvous)
    add_row(g2, dlg._lbl_p2p_rendezvous_trust, dlg.p2p_rendezvous_trust)
    add_row(g2, dlg._lbl_p2p_rendezvous_transport, dlg.p2p_rendezvous_transport)
    # Spanning row: the pair needs more width than the field column leaves, and
    # ``_ActionRow`` trailing-aligns it to the content edge (stacking when even
    # the full width cannot hold both labels).
    g2.addRow(manage_direct)
    # The derived group key only matters for a discovery server, so the action
    # lives with the other discovery-server controls; it is hidden until one is
    # configured (see ``SettingsDialog._refresh_group_key_button``).
    _spanning_row(g2, dlg.btn_show_group_key)
    add_row(g2, dlg._lbl_p2p_upnp, dlg.p2p_upnp)
    add_row(g2, dlg._lbl_no_mdns, dlg.no_mdns)
    dlg._lbl_help_rendezvous = help_link("help.rendezvous_setup", RENDEZVOUS_SETUP)
    g2.addRow(dlg._lbl_help_rendezvous)
    direct.addWidget(dlg._grp_p2p_rendezvous)

    dlg._grp_p2p_role = _group_box("settings.group.p2p_role")
    g3 = QFormLayout(dlg._grp_p2p_role)
    add_row(g3, dlg._lbl_prefer_master, dlg.prefer_master)
    add_row(g3, dlg._lbl_never_master, dlg.never_master)
    add_row(g3, dlg._lbl_p2p_trust, dlg.p2p_trust)
    direct.addWidget(dlg._grp_p2p_role)

    dlg._grp_p2p_advanced = _group_box("settings.group.advanced")
    g4 = QFormLayout(dlg._grp_p2p_advanced)
    add_row(g4, lbl_port, dlg.p2p_port)
    add_row(g4, lbl_rendezvous, dlg.rendezvous_timeout)
    add_row(g4, dlg._lbl_ntp_hosts, dlg.ntp_hosts)
    add_row(g4, dlg._lbl_peer_download, dlg.peer_download)
    add_row(g4, dlg._lbl_peer_read_cap, dlg.peer_read_cap)
    add_row(g4, dlg._lbl_peer_sources_max, dlg.peer_sources_max)
    direct.addWidget(dlg._grp_p2p_advanced)
    vbox.addWidget(dlg._direct_section)

    # Server mode: endpoint and identity, certificates, tuning.
    dlg._server_section = QWidget()
    server_box = QVBoxLayout(dlg._server_section)
    server_box.setContentsMargins(0, 0, 0, 0)
    server_box.setSpacing(8)

    dlg._grp_server = _group_box("settings.group.server")
    s1 = QFormLayout(dlg._grp_server)
    add_row(s1, lbl_server_url, dlg.server_url)
    add_row(s1, lbl_api_key, dlg.api_key)
    add_row(s1, dlg._lbl_server_trust, dlg.server_trust)
    # Spanning row, trailing-aligned to the same content edge as the inputs.
    s1.addRow(manage_server)
    dlg._lbl_help_server = help_link("help.server_setup", SERVER_SETUP)
    s1.addRow(dlg._lbl_help_server)
    server_box.addWidget(dlg._grp_server)

    dlg._grp_server_certificates = _group_box("settings.group.server_certificates")
    s2 = QFormLayout(dlg._grp_server_certificates)
    add_row(s2, dlg._lbl_insecure, dlg.insecure)
    add_row(s2, lbl_ca_cert, dlg.ca_cert)
    server_box.addWidget(dlg._grp_server_certificates)

    dlg._grp_server_advanced = _group_box("settings.group.advanced")
    s3 = QFormLayout(dlg._grp_server_advanced)
    add_row(s3, lbl_timeout, dlg.http_timeout)
    server_box.addWidget(dlg._grp_server_advanced)
    vbox.addWidget(dlg._server_section)

    vbox.addStretch()


def reorganize_advanced_tab(dlg: SettingsDialog) -> None:
    """Reorganize the Advanced tab into grouped sections using QGroupBox."""
    advanced_tab = dlg._tabs.widget(_ADVANCED_TAB_INDEX)
    if not advanced_tab:
        return

    lbl_logfile: QLabel = dlg.findChild(QLabel, "lblLogfile")  # type: ignore[assignment]

    old = advanced_tab.layout()
    if old is not None:
        while old.count():
            old.takeAt(0)
        _tmp = QWidget()
        _tmp.setLayout(old)

    _, vbox = _scrollable_page(advanced_tab)

    # Group 1: performance
    dlg._grp_advanced_perf = _group_box("settings.group.performance")
    f1 = QFormLayout(dlg._grp_advanced_perf)
    add_row(f1, dlg._lbl_autotune, dlg.autotune)
    dlg._lbl_max_concurrent = QLabel(tr("settings.max_concurrent_transfers"))
    add_row(f1, dlg._lbl_max_concurrent, dlg.max_concurrent_transfers)
    vbox.addWidget(dlg._grp_advanced_perf)

    # Group 2: delta transfer
    dlg._grp_advanced_delta = _group_box("settings.group.delta")
    f2 = QFormLayout(dlg._grp_advanced_delta)
    add_row(f2, dlg._lbl_delta_enabled, dlg.delta_enabled)
    dlg._lbl_delta_min = QLabel(tr("settings.delta_min_file_size"))
    add_row(f2, dlg._lbl_delta_min, dlg.delta_min_file_size)
    dlg._lbl_delta_min_p2p = QLabel(tr("settings.delta_min_file_size_p2p"))
    add_row(f2, dlg._lbl_delta_min_p2p, dlg.delta_min_file_size_p2p)
    vbox.addWidget(dlg._grp_advanced_delta)

    # Group 3: deletion protection
    dlg._grp_advanced_guard = _group_box("settings.group.deletion_protection")
    f3 = QFormLayout(dlg._grp_advanced_guard)
    add_row(f3, dlg._lbl_mass_delete_guard, dlg.mass_delete_guard)
    dlg._lbl_guard_threshold = QLabel(tr("settings.mass_delete_threshold"))
    add_row(f3, dlg._lbl_guard_threshold, dlg.mass_delete_threshold)
    dlg._lbl_guard_percent = QLabel(tr("settings.mass_delete_percent"))
    add_row(f3, dlg._lbl_guard_percent, dlg.mass_delete_percent)
    f3.addRow(dlg._lbl_deletion_risk_reset)
    _spanning_row(f3, dlg.btn_deletion_risk_reset)
    vbox.addWidget(dlg._grp_advanced_guard)

    # Group 4: network
    dlg._grp_advanced_network = _group_box("settings.group.network")
    f4 = QFormLayout(dlg._grp_advanced_network)
    dlg._lbl_bandwidth_upload = QLabel(tr("settings.bandwidth_upload"))
    add_row(f4, dlg._lbl_bandwidth_upload, dlg.bandwidth_upload)
    dlg._lbl_bandwidth_download = QLabel(tr("settings.bandwidth_download"))
    add_row(f4, dlg._lbl_bandwidth_download, dlg.bandwidth_download)
    vbox.addWidget(dlg._grp_advanced_network)

    # Group 5: logging
    dlg._grp_advanced_logging = _group_box("settings.group.logging")
    f5 = QFormLayout(dlg._grp_advanced_logging)
    add_row(f5, dlg._lbl_verbose, dlg.verbose)
    add_row(f5, lbl_logfile, dlg.logfile)
    vbox.addWidget(dlg._grp_advanced_logging)

    vbox.addStretch()
