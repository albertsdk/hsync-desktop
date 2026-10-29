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

from PySide6.QtCore import QSize, Qt
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

from hsync_desktop.docs_links import BOOTNODE_SETUP, SERVER_SETUP
from hsync_desktop.i18n import tr
from hsync_desktop.settings.tab_indices import (
    _ADVANCED_TAB_INDEX,
    _GENERAL_TAB_INDEX,
    _P2P_TAB_INDEX,
    _SERVER_TAB_INDEX,
    _SYNC_TAB_INDEX,
    _TAB_DESCRIPTION_KEYS,
)
from hsync_desktop.widgets.forms import add_row
from hsync_desktop.widgets.labels import muted_label
from hsync_desktop.widgets.links import help_link
from hsync_desktop.widgets.text import escape_mnemonics

if TYPE_CHECKING:
    from hsync_desktop.settings.dialog import SettingsDialog

# Desktop settings pages never stretch a form across the whole window: the
# content keeps one bounded column, centred in the page, so controls stay a
# readable width whatever the window size. 640 px fits the widest shipped
# translation with room for a two-column form.
_CONTENT_MAX_WIDTH = 640
# ``tab_builders.finalize_size`` keeps the dialog at least 640 px wide; the
# description must wrap inside that page instead of asking for more. The cap
# includes the label's own insets, so it is the text measure plus
# ``_DESCRIPTION_MARGINS`` left/right.
_TAB_DESCRIPTION_MAX_WIDTH = _CONTENT_MAX_WIDTH - 40
# Breathing room around the purpose line, as (left, top, right, bottom): inset
# from the tab edge, below the tab bar and above the first group box. Applied
# with ``setContentsMargins`` so the QSS keeps owning only the muted colour.
_DESCRIPTION_MARGINS = (20, 12, 20, 16)


class _CenteredColumn(QWidget):
    """Keep one child centred, never wider than ``max_width``, full height.

    A plain box layout either stretches the column across the whole window or
    leaves it at its size hint beside the spacer items (Qt gives the extra space
    to the spacers). This wrapper gives the child exactly
    ``min(width, max_width)``, so the settings page keeps one bounded reading
    column, centred when the window grows.
    """

    def __init__(self, child: QWidget, max_width: int) -> None:
        super().__init__()
        self._child = child
        self._max_width = max_width
        child.setParent(self)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        width = min(self.width(), self._max_width)
        self._child.setGeometry((self.width() - width) // 2, 0, width, self.height())

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt override)
        hint = self._child.sizeHint()
        # A child's preferred height can be smaller than what it requires (a
        # label with a reserved minimum height): never advertise less than the
        # child's minimum, or the wrapper clips it.
        height = max(hint.height(), self._child.minimumSizeHint().height())
        return QSize(min(hint.width(), self._max_width), height)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 (Qt override)
        return QSize(0, self._child.minimumSizeHint().height())


def _group_box(title_key: str) -> QGroupBox:
    """A titled group box whose title shows its ``&`` literally."""

    return QGroupBox(escape_mnemonics(tr(title_key)))


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

    ``outer`` is the page's top-level layout (the description line, then the
    scroll area); ``inner`` is the scroll content where the groups go, so a tall
    page scrolls instead of forcing the dialog to grow (see
    ``tab_builders.finalize_size``).
    """

    outer = _page_outer(tab)
    content = QWidget()
    inner = QVBoxLayout(content)
    inner.setContentsMargins(4, 4, 4, 4)
    inner.setSpacing(8)
    outer.addWidget(_scroll_area(_CenteredColumn(content, _CONTENT_MAX_WIDTH)), 1)
    return outer, inner


def _add_tab_description(dlg: SettingsDialog, vbox: QVBoxLayout, tab_index: int) -> None:
    """Insert the tab's one-line purpose label above its groups.

    The label keeps the ``mutedHint`` style of the wizard helper text and is
    registered on the dialog so re-translation and the "disable this tab"
    state machines can reach it.
    """

    label = muted_label(tr(_TAB_DESCRIPTION_KEYS[tab_index]))
    label.setContentsMargins(*_DESCRIPTION_MARGINS)
    # A word-wrapped QLabel reports its *unwrapped* text width as sizeHint;
    # cap it below the content column so a longer translation wraps instead of
    # forcing the page wider.
    label.setMaximumWidth(_TAB_DESCRIPTION_MAX_WIDTH)
    dlg._tab_descriptions[tab_index] = label
    # The description shares the centred content column of the groups below, so
    # the two stay aligned on a wide window. It stays the page's first item,
    # above the scroll area.
    column = QWidget()
    column_layout = QVBoxLayout(column)
    column_layout.setContentsMargins(0, 0, 0, 0)
    column_layout.addWidget(label)
    vbox.insertWidget(0, _CenteredColumn(column, _CONTENT_MAX_WIDTH))


def equalize_tab_descriptions(dlg: SettingsDialog) -> None:
    """Reserve one shared height for the mode purpose lines.

    Each description wraps to a different number of lines depending on the
    language and the window width, so the shorter one would let its first group
    box sit higher than the other tabs. Reserving the tallest hint on all three
    keeps the forms aligned whatever the locale; the labels' hints do not depend
    on the minimum height, so this never feeds back into the layout.
    """

    labels = [label for label in dlg._tab_descriptions.values() if label is not None]
    if not labels:
        return
    tallest = max(label.sizeHint().height() for label in labels)
    changed = False
    for label in labels:
        if label.minimumHeight() != tallest:
            label.setMinimumHeight(tallest)
            changed = True
    if not changed:
        return
    # The wrapper re-sizes its child by hand, so Qt never sees the child's
    # geometry request: the page layout keeps the item size hint it cached
    # before the minimum was raised. Ask the wrapper to re-measure, then
    # invalidate the page layout, or the reserved height is not allocated and
    # the groups below stay where they were.
    for label in labels:
        column = label.parentWidget()
        if column is None:
            continue
        column.updateGeometry()
        centered = column.parentWidget()
        if centered is None:
            continue
        centered.updateGeometry()
        page = centered.parentWidget()
        layout = page.layout() if page is not None else None
        if layout is not None:
            layout.invalidate()


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
    outer, vbox = _scrollable_page(sync_tab)

    _add_tab_description(dlg, outer, _SYNC_TAB_INDEX)

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
    f4.addRow("", dlg.btn_edit_hsyncignore)

    # Maintenance: forget the folder's sync history (client-side state DB).
    f4.addRow("", dlg.btn_reset_state)
    vbox.addWidget(dlg._grp_advanced)

    vbox.addStretch()


def reorganize_p2p_tab(dlg: SettingsDialog) -> None:
    """Reorganize the p2p tab into grouped sections using QGroupBox."""
    p2p_tab = dlg._tabs.widget(_P2P_TAB_INDEX)
    if not p2p_tab:
        return

    lbl_group: QLabel = dlg.findChild(QLabel, "lblP2pGroup")  # type: ignore[assignment]
    lbl_key: QLabel = dlg.findChild(QLabel, "lblP2pKey")  # type: ignore[assignment]
    lbl_port: QLabel = dlg.findChild(QLabel, "lblP2pPort")  # type: ignore[assignment]
    lbl_discovery: QLabel = dlg.findChild(QLabel, "lblDiscoveryTimeout")  # type: ignore[assignment]

    manage_container: QWidget = dlg.btn_manage_trusted_keys.parent()  # type: ignore[assignment]

    # Detach the original form layout.
    old = p2p_tab.layout()
    if old is not None:
        while old.count():
            old.takeAt(0)
        _tmp = QWidget()
        _tmp.setLayout(old)

    outer, vbox = _scrollable_page(p2p_tab)

    _add_tab_description(dlg, outer, _P2P_TAB_INDEX)

    # Group 1: mode + group identity
    dlg._grp_p2p_mode = _group_box("settings.group.p2p_mode")
    g1 = QFormLayout(dlg._grp_p2p_mode)
    add_row(g1, dlg._lbl_p2p_mode, dlg.p2p_mode)
    add_row(g1, lbl_group, dlg.p2p_group)
    add_row(g1, lbl_key, dlg.p2p_key)
    vbox.addWidget(dlg._grp_p2p_mode)

    # Group 2: cross-network discovery through a bootnode
    dlg._grp_p2p_discovery = _group_box("settings.group.p2p_discovery")
    g2 = QFormLayout(dlg._grp_p2p_discovery)
    add_row(g2, dlg._lbl_p2p_bootnode, dlg.p2p_bootnode)
    add_row(g2, dlg._lbl_p2p_bootnode_trust, dlg.p2p_bootnode_trust)
    # Spanning row: the button pair cannot fit the field column once the captions
    # and the labels are localized (see ``_action_row``).
    g2.addRow(manage_container)
    add_row(g2, dlg._lbl_p2p_upnp, dlg.p2p_upnp)
    dlg._lbl_help_bootnode = help_link("help.bootnode_setup", BOOTNODE_SETUP)
    g2.addRow("", dlg._lbl_help_bootnode)
    vbox.addWidget(dlg._grp_p2p_discovery)

    # Group 3: role election + pairing
    dlg._grp_p2p_role = _group_box("settings.group.p2p_role")
    g3 = QFormLayout(dlg._grp_p2p_role)
    add_row(g3, dlg._lbl_prefer_master, dlg.prefer_master)
    add_row(g3, dlg._lbl_never_master, dlg.never_master)
    add_row(g3, dlg._lbl_p2p_trust, dlg.p2p_trust)
    vbox.addWidget(dlg._grp_p2p_role)

    # Group 4: advanced tuning
    dlg._grp_p2p_advanced = _group_box("settings.group.advanced")
    g4 = QFormLayout(dlg._grp_p2p_advanced)
    add_row(g4, lbl_port, dlg.p2p_port)
    add_row(g4, lbl_discovery, dlg.discovery_timeout)
    add_row(g4, dlg._lbl_ntp_hosts, dlg.ntp_hosts)
    add_row(g4, dlg._lbl_peer_download, dlg.peer_download)
    add_row(g4, dlg._lbl_peer_read_cap, dlg.peer_read_cap)
    add_row(g4, dlg._lbl_peer_sources_max, dlg.peer_sources_max)
    vbox.addWidget(dlg._grp_p2p_advanced)

    vbox.addStretch()


def reorganize_server_tab(dlg: SettingsDialog) -> None:
    """Reorganize the Server Mode tab into grouped sections using QGroupBox."""
    server_tab = dlg._tabs.widget(_SERVER_TAB_INDEX)
    if not server_tab:
        return

    lbl_server_url: QLabel = dlg.findChild(QLabel, "lblServerUrl")  # type: ignore[assignment]
    lbl_api_key: QLabel = dlg.findChild(QLabel, "lblApiKey")  # type: ignore[assignment]
    lbl_ca_cert: QLabel = dlg.findChild(QLabel, "lblCaCert")  # type: ignore[assignment]
    lbl_timeout: QLabel = dlg.findChild(QLabel, "lblHttpTimeout")  # type: ignore[assignment]

    # Action rows keep their own container (they are not labelled fields).
    action_row: QWidget = dlg.btn_manage_trusted_keys_server.parent()  # type: ignore[assignment]

    old = server_tab.layout()
    if old is not None:
        while old.count():
            old.takeAt(0)
        _tmp = QWidget()
        _tmp.setLayout(old)

    outer, vbox = _scrollable_page(server_tab)

    # Orientation first (stable), then the p2p-mode warning that explains why
    # the whole tab is disabled.
    _add_tab_description(dlg, outer, _SERVER_TAB_INDEX)
    vbox.addWidget(dlg._p2p_banner)

    # Group 1: server endpoint, credentials, identity and actions.
    dlg._grp_server = _group_box("settings.group.server")
    g1 = QFormLayout(dlg._grp_server)
    add_row(g1, lbl_server_url, dlg.server_url)
    add_row(g1, lbl_api_key, dlg.api_key)
    add_row(g1, dlg._lbl_server_trust, dlg.server_trust)
    # Spanning row, same reason as the p2p twin above.
    g1.addRow(action_row)
    dlg._lbl_help_server = help_link("help.server_setup", SERVER_SETUP)
    g1.addRow("", dlg._lbl_help_server)
    vbox.addWidget(dlg._grp_server)

    # Group 2: TLS/certificate behaviour.
    dlg._grp_server_certificates = _group_box("settings.group.server_certificates")
    g2 = QFormLayout(dlg._grp_server_certificates)
    add_row(g2, dlg._lbl_insecure, dlg.insecure)
    add_row(g2, lbl_ca_cert, dlg.ca_cert)
    vbox.addWidget(dlg._grp_server_certificates)

    # Group 3: advanced request tuning.
    dlg._grp_server_advanced = _group_box("settings.group.advanced")
    g3 = QFormLayout(dlg._grp_server_advanced)
    add_row(g3, lbl_timeout, dlg.http_timeout)
    vbox.addWidget(dlg._grp_server_advanced)

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
    f3.addRow("", dlg.btn_deletion_risk_reset)
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
