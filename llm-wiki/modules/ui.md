# HSYNC Desktop — UI (window, panels, presentation)

Qt widgets that render engine state. All UI mutation stays on the main thread,
driven by `HsyncEngine` signals (see [engine.md](engine.md)).

## main_window/ — MainWindow

`MainWindow` is assembled from responsibility mixins (all sharing `self`):
`window.py` (`MainWindow`, `__init__`, `_connect_signals`), `ui.py`
(UI construction), `events.py` (engine-signal slots), `trust.py`
(trust/pinning + pre-flight), `start.py` (start/stop/compare/pre-flight checks),
`actions.py` (menu actions) and `lifecycle.py` (tray/quit/close/eventFilter).
The mixins suppress `attr-defined` in mypy because they operate on the composed
window's attributes.

| Symbol | Location | Role |
| ------ | -------- | ---- |
| `MainWindow` | `main_window/window.py::MainWindow` | top-level window; owns engine + tray; single open `SettingsDialog` (`_settings_dialog`, re-raised on re-open) |
| `_load_ui` | `main_window/ui.py::UiBuildMixin._load_ui` | build/compose the central UI |
| `_create_menu_bar` | `main_window/ui.py::UiBuildMixin._create_menu_bar` | menus + actions (start/stop/compare/direction/file ops/help) |
| `_connect_signals` | `main_window/window.py::MainWindow._connect_signals` | bind every engine `Signal` to a slot |
| `_apply_translations` | `main_window/ui.py::UiBuildMixin._apply_translations` | re-translate on language change |
| `_update_peers_label_title` | `main_window/ui.py::UiBuildMixin._update_peers_label_title` | status-bar presence title: **Devices** in p2p, **Connected users** in Server Mode |
| `_update_menu_state` | `main_window/ui.py::UiBuildMixin._update_menu_state` | enable/disable actions by run state |
| `_fit_table_width` | `main_window/window.py::MainWindow._fit_table_width` | one-shot startup growth so the file table stays readable (see *Columns*) |
| `_check_auto_sync` | `main_window/start.py::StartMixin._check_auto_sync` | queued at startup only when `settings/cli_args.py::is_auto_sync_enabled` (`sync/auto_sync`) is on |
| `_on_auto_start` | `main_window/start.py::StartMixin._on_auto_start` | runs `_on_start` with `_start_is_automatic` set, so failures and prompts avoid modals on a tray-only window |
| `_quit` | `main_window/lifecycle.py::LifecycleMixin._quit` | tray "Quit": confirm while a sync runs, then `_shutdown` |
| `_shutdown` | `main_window/lifecycle.py::LifecycleMixin._shutdown` | prompt-free close (stop engine, save geometry, hide tray, quit); shared by the SIGINT handler |

Engine→slot wiring (in `_connect_signals`, `main_window/window.py::MainWindow._connect_signals`): `log_received→_append_log`,
`status_changed→_on_status`, `peers_changed`/`master_changed`, `file_transferred→_on_file_transferred`,
`transfer_failed→_on_transfer_failed`, `sync_paused→_on_sync_paused`,
`file_progress`/`file_renamed`, `folder_size_changed→_on_folder_size`,
`file_panel.share_size_changed→_on_share_size_changed`,
`pairing_needed→_on_pairing_needed` / `fingerprint_changed→_on_fingerprint_changed`,
and the two comparison marker pairs (`preview_started`/`preview_ended`,
`status_pass_started`/`status_pass_ended`) → `_on_preview_started` /
`_on_status_pass_started` and `_on_preview_ended` / `_on_status_pass_ended`.
`error_occurred` is always routed to `_on_engine_error` (`main_window/ui.py::UiBuildMixin._on_engine_error`),
which stores the message, mirrors it into the log panel and raises an in-app
error toast through `_notify_error` (an OS notification is sent too, only when a
notifier exists and the window is out of focus).
File-action menu slots: open/open-with/copy-to/rename/trash/
properties (`main_window/ui.py::UiBuildMixin._create_menu_bar`).

**Startup run** (`sync/auto_sync`, the Sync-tab *Auto-sync on startup* switch) is
opt-in: the wizard draft starts from `config.py::DEFAULT_AUTO_SYNC`
(`wizard/model.py::WizardDraft.auto_sync`) and Settings writes the same key, so
`MainWindow.__init__` queues `_check_auto_sync` only when
`settings/cli_args.py::is_auto_sync_enabled` is true. The automatic run follows
the manual path (disclaimer → pre-flight gates), except for the file-deletion
confirmation: `main_window/start.py::StartMixin._check_deletion_risk` is called
with `interactive=False`, which reports the risk instead of prompting, and
`main_window/start.py::StartMixin._report_deletion_risk_needed` surfaces
`notif.deletion_risk_manual` through `_notify_warning` (in-app toast + OS
notification when out of focus) and drops the run. A confirmation nobody was
asked to answer therefore never starts a destructive sync — and a tray-only
`--minimized` launch never raises a modal on a hidden window. The same rule
applies to the one-time disclaimer: `main_window/start.py::StartMixin._show_disclaimer`
takes `interactive=False`, returns without a dialog and
`StartMixin._report_disclaimer_needed` surfaces `notif.disclaimer_manual`. The
user reviews the settings and presses Start, which prompts interactively as
before.
`_on_auto_start` hands the origin over as `MainWindow._pending_start_automatic`
instead of setting `_start_is_automatic` for the duration of the call, because
`_on_start` defers the run by half a second: the flag has to be live when the
deferred continuation and a startup failure are handled, and a manual Start
clears it again.

The presence value (`peersLabel`, set by `_on_peers`) is `connected/total`. p2p
counts **devices** (self + peers); Server Mode counts **share accounts** with a
live WebSocket (admins excluded), so its title is "Connected users"
(`label.users`) — two devices on the same account count once.

**Keyboard shortcuts** live only on the menu-bar actions (a context menu cannot
be reached from the keyboard, so it never displays them): `Return`/`Ctrl+O` open,
`F2` rename, `Delete` trash, `Alt+Return` properties, `Ctrl+Shift+C` copy path,
`Ctrl+Alt+C` copy to, `F5` compare, `Ctrl+Shift+S` start,
`QKeySequence.StandardKey.Preferences` settings and `.Quit` quit (Cmd instead of
Ctrl on macOS), `F1` documentation; the log menu shows `StandardKey.SelectAll` /
`.Copy` and lets the view handle them.

Help menu (`main_window/ui.py::UiBuildMixin._create_menu_bar`): external links
first (Documentation, Project on GitHub), then a separator and the local
app-info dialogs — **License** (`main_window/actions.py::ActionsMixin._show_license`
→ `license_dialog.py::LicenseDialog`, a scrollable read-only view of the bundled
`LICENSE`) and **About** last, the conventional position. The two external
targets come from `docs_links.py` (`DOCS_INDEX`, `GITHUB_REPO`) and open through
`docs_links.open_docs_link`, which only allows the project HTTPS pages.
`DOCS_INDEX` is the documentation landing page (`docs/README.md`), distinct from
`CONNECTION_MODES` (`docs/connection-modes.md`) that the wizard's mode step links to, so
**Help → Documentation** always starts from the docs index.

**Contextual documentation links**: the Server tab links to the hsync-server
setup guide (`help.server_setup`), the p2p discovery group to the hsync-bootnode
guide (`help.bootnode_setup`), and the wizard's mode step plus its "Not sure?"
dialog to the desktop connection-modes guide (`help.connection_modes`). They are
`QLabel#helpLink` anchors built by `widgets/links.py::help_link`, keyboard
accessible (`LinksAccessibleByKeyboard`), with the URL in the tooltip; the
Settings dialog re-applies the translated text in
`settings/tab_translations.py::apply_translations`. Link colours are themed
through `QPalette.Link`/`LinkVisited` in `themes.py`. The labels are
`widgets/links.py::_HelpLinkLabel`, whose `sizeHint` reports the wrapped height
at the width the label really has: a word-wrapped rich-text `QLabel` otherwise
claims the height of its document's ideal (very narrow) width — three lines for
one line of text — and the form row keeps that dead space.

### Startup disclaimer

`main_window/start.py::StartMixin._show_disclaimer` gates the first start of a
sync. `main_window/start.py::StartMixin._build_disclaimer_dialog` offers two
explicit actions with the app icons: **I understand**
(`disclaimer.acknowledge`, default) and **Not now** (`disclaimer.not_now`,
escape button). Closing the window or pressing Esc defers and never
acknowledges, so only the acknowledge button starts the sync. The "don't show
again" checkbox stores `ui/disclaimer_version` =
`main_window/start.py::DISCLAIMER_VERSION`; the previous bare boolean
(`ui/disclaimer_accepted`) counts as version 1 through
`main_window/start.py::_accepted_disclaimer_version`, so a later wording change
prompts again.

### Pre-flight gates

Before a run starts, `_continue_start_after_disclaimer`
(`main_window/start.py::StartMixin._continue_start_after_disclaimer`) chains the
gates in this order: `_check_deletion_risk`, `_check_keyless_p2p`,
`_check_disk_space`, then `_ensure_trust` (`main_window/trust.py::TrustMixin._ensure_trust`);
the scoped
Send/Receive path (`main_window/actions.py`) reuses the same checks. The
deletion-risk confirmation (`notif.deletion_risk`, p2p without *Prefer primary
role* or Receive-only) is a guard for a run that actually applies changes, so
`_check_deletion_risk` (`main_window/start.py::StartMixin._check_deletion_risk`)
returns early when **Simulation Mode** (`sync/dry_run`) is on or when the
deletion policy is `keep` (`settings/cli_args.py::get_deletion_policy`): neither
can remove a local file, and an automatic startup run must not be dropped for a
risk that cannot materialise. That setting makes
every run a preview-only one-shot: `build_hsync_args` emits `--once -n`, so the
client shows the preview and exits instead of parking in the dry-run "wait for a
`SYNC` command" state, where `SYNC` would flip it to a real sync
(`hsync-client` `preview.py`, function `_run_stdin_wait`). For the same reason
`_show_preview_summary` (`main_window/actions.py`) never sends `SYNC` under
simulation: it logs and toasts `preview.simulation_no_changes` and lets the
one-shot process finish.

### Simulation Mode indicator

While `sync/dry_run` is on the window says so everywhere, because the mode is a
setting the user would otherwise have to remember. `_refresh_simulation_state`
(`main_window/ui.py::UiBuildMixin._refresh_simulation_state`) is the single refresh point, called from `_apply_translations`
(so a language change re-reads it), from `MainWindow.__init__` and from
`_apply_settings_changes` (`main_window/start.py::StartMixin._apply_settings_changes`, the shared post-settings/wizard
hook). It drives:
* `QLabel#simulationBadge` in the bottom bar (`ui/main_window.ui`, `simulation.badge`,
  themed by `QLabel#simulationBadge` in `themes.py`), with the `simulation.tip` tooltip;
* the window title suffix (`simulation.window_title_suffix`) via
  `main_window/ui.py::UiBuildMixin._update_window_title`, also used by
  `_on_bucket_detected`;
* the tray tooltip note (`system_tray.py::SystemTray.set_simulation`) and the Start
  button hint (`tip.start_simulation`).

The run itself opens with `simulation.log_start` (`_prepare_engine_run`,
`main_window/actions.py`) and the preview dialog swaps *Synchronize* for *Close*
(`preview_summary_dialog.py::PreviewSummaryDialog`, `simulation=True`), so no
control ever promises an application that cannot happen.

### Engine start failure feedback

`_start_engine` (`main_window/start.py::StartMixin._start_engine`) wraps
`HsyncEngine.start`: on failure it records the reason emitted through
`error_occurred` and calls `_report_engine_start_failure`
(`main_window/start.py::StartMixin._report_engine_start_failure`), which raises a
critical `QMessageBox` (title `notif.error`, body `notif.engine_start_failed`,
the engine reason as informative text). Both start sites use it —
`_continue_start_after_disclaimer` and `_retry_after_auth_fix` — so a start that
cannot launch (missing/incompatible binary, spawn failure) surfaces the dialog
instead of a silent no-op; the caller resets the UI via `_reset_ui_stopped`.

### Remote endpoint icon (`_update_path_display`)

`main_window/start.py::StartMixin._update_path_display` picks the remote icon from
`QSettings`: server mode (`p2p/enabled` false) → `network-cloud`; p2p mode →
always `network-p2p` (the bootnode does not change the icon). The role
indicator is p2p-only: `_apply_role_visibility`
(`main_window/ui.py::UiBuildMixin._apply_role_visibility`) shows it in p2p mode
once the election has decided the role (`_role_known`) and hides it entirely in
Server Mode and before the election — no placeholder glyph. `_retranslate_role`
renders the primary icon with the theme accent
(`themed_icon("role-master", <Highlight>)`; the SVG uses `currentColor`) and the
secondary icon in the theme text colour; the **Nodo primario/secondario** text
appears only when connected and the role is known
(`main_window/events.py::EventsMixin._on_master` + `_on_status`), and the state
resets per engine process (`_prepare_engine_run`).

### Share name next to the folder icon

The active share (bucket) is the user-facing identity, so it labels the local
folder in the action bar — next to the folder icon — as a clickable link
(`main_window/start.py::StartMixin._update_path_display`; the name comes from
`main_window/start.py::StartMixin._share_display_name`: detected bucket →
`sync/bucket` → folder name). Clicking it opens the local folder
(`main_window/start.py::StartMixin._on_path_clicked`); the full local path is the
label's tooltip. That tooltip is **intentionally exempt** from the "Show tooltips"
preference (`appearance/tooltips`), which only governs the settings fields. The
window title stays the bare app name (`main_window/events.py::EventsMixin._on_bucket_detected`).
The share name is seeded from `sync/bucket` and updated on the client's `bucket`
event (signal `engine/process.py::HsyncEngine.bucket_detected`).

### Trust refusal dialogs (SSH-style, no terminal)

`MainWindow` answers the client's trust refusals with dialogs instead of a
terminal (the client keeps retrying on the mDNS path, so the handlers dedupe):

- `_on_pairing_needed` / `_on_fingerprint_changed` (`main_window/trust.py::TrustMixin._on_pairing_needed` / `main_window/trust.py::TrustMixin._on_fingerprint_changed`)
  build their box through `_trust_prompt` (`main_window/trust.py::TrustMixin._trust_prompt`),
  the single warning-box construction (translated title/body, reject as default,
  returns the clicked button *role*), then
  route by `scope`: `master` → `add_peer_pin`/`remove_peer_pin`; `bootnode`/`server`
  → the helpers returned by `_host_trust_actions` (`main_window/trust.py::TrustMixin._host_trust_actions`) (`add_bootnode_trust`/
  `remove_bootnode_trust` or `add_server_trust`/`remove_server_trust`). Dedupe is
  `_trust_prompted` `dict[(scope, identity)] → last fingerprint` (`main_window/window.py::MainWindow`) via
  `_should_prompt_trust` (`main_window/trust.py::TrustMixin._should_prompt_trust`), cleared on start/stop (`main_window/window.py::MainWindow`): a
  repeated refusal for the same fingerprint reuses no dialog, a changed one
  re-prompts. A dismissed or ignored dialog never touches the stored pin (the
  host branch acts only on the explicit Trust/Forget buttons).
- `_maybe_offer_restart` (`main_window/trust.py::TrustMixin._maybe_offer_restart`) offers to restart a stopped sync after a
  bootnode/server pin change (those failures are fatal; mDNS refusals are not).
- `_ensure_trust` (`main_window/trust.py::TrustMixin._ensure_trust`) is the start
  pre-flight for both hosts: `_pending_trust_checks` collects the
  `_TrustCheck` (`main_window/trust.py::_TrustCheck`) entries that still need an
  operator decision (mode/policy/URL apply and the known-hosts store does not yet
  hold `host:port`), then `_run_next_trust_check` probes them one at a time on
  `engine/async_probe.py::AsyncProbe` and `_on_trust_probe_done`
  (`main_window/trust.py::TrustMixin._on_trust_probe_done`) confirms and pins.
  The run starts only from the `on_ready` continuation, so a refused or
  unreachable host abandons it. The probe never runs on the UI thread, and a
  progress toast (`common.checking`) covers the wait. Pins are written to the
  shared known-hosts stores (no GUI-only fingerprint settings).

## trusted_keys.py — TrustedKeysDialog

`TrustedKeysDialog` (`trusted_keys.py::TrustedKeysDialog`) lists and edits all three stores via
the `engine` subprocess helpers (never the store files directly): three tabs
(bootnodes / servers / devices), each a `QTableWidget` + Add/Remove/Refresh. The
`initial_tab` keyword (`bootnodes` default, or `servers`) selects the opening
tab; the settings dialog passes the tab matching the panel that launched it.
Tabs are filtered by the active mode
(`trusted_keys.py::TrustedKeysDialog._apply_mode_tab_visibility`, reading
`p2p/enabled`): p2p shows **Discovery servers** + **Devices** and hides the server
store; Server Mode shows only **Server HSYNC** and hides the p2p stores. When
`initial_tab` is hidden, the dialog falls back to the first visible page. The
server tab is labelled **Server HSYNC** (`trusted_keys.tabs_servers`). The
bootnode/server tabs share `_HostAddDialog` and `_build_host_tab` (host:port
stores); *Add* supports "read from server" or manual entry. *Read from server*
(`trusted_keys.py::_HostAddDialog._read_from_node`) runs the fingerprint probe on
`engine/async_probe.py::AsyncProbe` and labels the button `common.checking`
meanwhile. Device *Add* pre-fills
the bucket from `sync/bucket`. The tab/column labels are localized in every
locale (`trusted_keys.tabs_peers` = Devices, `trusted_keys.peer` = Device,
`trusted_keys.fingerprint` = the locale's term for the certificate fingerprint).

The bootnode/server tabs show host, fingerprint, **source** and **added** date.
The raw client `source` (`cli` / `tofu` / `prompt` / `flag`, from
`hsync-client known_hosts.py::TRUST_SOURCES`) is humanized by
`trusted_keys.py::_source_label` (`trusted_keys.source_cli` …), and the
`first_seen` column is labelled **Added on** (`trusted_keys.first_seen`), not the
SSH jargon "first seen". The devices tab shows device, fingerprint and the
**Added on** date: the client's peer pin store (`hsync-client pinning.py::PinStore`)
records `{fingerprint, first_seen}` per `(cid, bucket)`, exposed by
`hsync trust peer list --json`.

The devices tab shows
`trusted_keys.capability_missing` when the binary lacks the `trust` subcommand
(`supports_peer_trust`).

## file_panel/ — live transfer view

| Symbol | Location | Role |
| ------ | -------- | ---- |
| `FilePanel` | `file_panel/panel.py::FilePanel` | container: table + detail pane + overlay |
| `FileTransferTable` | `file_panel/transfer_table.py::FileTransferTable` | `QTableView` showing per-file rows (status/progress/size) |
| `FileTransferModel` | `file_panel/transfer_table.py::FileTransferModel` | `QAbstractTableModel` holding the visible rows and rendering each cell on demand |
| `FileDetailPanel` | `file_panel/detail_panel.py::FileDetailPanel` | selected-file metadata pane |
| `ProgressBarDelegate` | `file_panel/delegates.py::ProgressBarDelegate` | progress-bar cell rendering |
| `LoadingOverlay` | `file_panel/overlay.py::LoadingOverlay` | busy overlay during scans |
| `_confirm_dialog` | `file_panel/dialogs.py::_confirm_dialog` | reusable confirm prompt |
| `DirectoryScanWorker` | `file_panel/workers.py::DirectoryScanWorker` | off-thread local tree scan |
| `_classify_file` / `format_mtime` | `file_panel/utils.py::_classify_file` / `file_panel/utils.py::format_mtime` | type/icon + mtime formatting |

The table is a **model/view pair** (`file_panel/transfer_table.py::FileTransferModel`
+ `FileTransferTable`): the view computes one `(display_name, transfer,
folder_data)` row per visible folder/file and hands the list to `FileTransferModel.set_rows`;
cells are produced through `QAbstractTableModel.data` roles (Display, Decoration,
Foreground, Font, ToolTip, UserRole for the progress bar), so no per-cell
`QTableWidgetItem` is retained and the rows are virtualized. Column-header sorting
is model-side (`FileTransferModel.sort`): it stays off until the user sorts, and a
refresh re-applies the recorded sort, preserving the user's order across rebuilds.
`FileTransferTable` keeps the navigation, context-menu, column-visibility/width
and selection logic and exposes `_model` (and `model().display_name(row)`) to
callers that need a row's transfer or display name.

The panel lists exactly what the engine synchronises: the local scan, the
consistency pass and the status-bar size share
`file_panel/filter.py::is_synced_entry`, built on the engine's
`hsync_common.ignore.IgnoreMatcher` (so `.hsyncignore`, the built-in default
patterns, internal names and `*.part` artifacts are excluded) plus an explicit
`.hsynckeep` exclusion — the sentinel is synced by the engine but stays internal
to the UI, and the client's folder-size totals exclude it too. `.hsyncignore` is
re-read when its `(mtime_ns, size)` changes (`filter.py::ignore_file_stamp`).

Dot-prefixed names are only a **view** option: `ui/show_hidden_files`
(`FileTransferTable._SHOW_HIDDEN_SETTINGS_KEY`) hides an item when its own name
at the current level starts with `.`, toggled from the header context menu next
to the column toggles (`FileTransferTable.set_show_hidden`). It changes neither
`_transfers` nor the scanned size; a non-dot folder whose children are all
view-hidden stays listed, with counts from its visible children only. The
default is off (hidden).

Renaming a row (`file_panel/transfer_table.py::FileTransferTable.rename_file`)
keeps its modification date: the new row inherits the previous row's mtime when
the filesystem read returns nothing (the rename event may arrive before the local
rename lands — `main_window/events.py::EventsMixin._on_file_renamed` reads the
destination, falling back to the source).

`FileTransferTable.set_connected` (`file_panel/transfer_table.py::FileTransferTable.set_connected`,
driven from `main_window/events.py::EventsMixin._on_status`) greys **Local** rows
(`TransferStatus.LOCAL` → `STATUS_COLORS`) only while a connection is active.
When the link is disconnected/connecting/waiting the rows keep the default text
colour, because "Local" is the resting state rather than a comparison result;
real transfer states keep their own colours.

A folder row with no aggregated children (an empty directory) shows the folder's
own status instead of defaulting to *Local*: a directory created by a remote peer
is stored under a trailing-slash key and marked **Synced**
(`main_window/events.py::EventsMixin._on_directory_created` normalizes the key;
`file_panel/transfer_table.py` module maps `_STATUS_PRIORITY`/`_FOLDER_STATUS_KEYS`
resolve an empty folder from its transfer status). A folder that does have
children still takes the highest-priority child status.

A **"Synced" row is a claim about the remote copy**, so it is asserted only while a
link exists: `file_panel/transfer_table.py::FileTransferModel._row_status` swaps
the label for `detail.synced_stale` (and `_foreground` uses the same muted grey as
*Local*) whenever `FileTransferTable.set_connected(False)` has cleared the link.
The timestamp of the last full comparison (`FileTransferTable.mark_verified`,
stamped from `_on_preview_ended` and `_on_sync_completed`) feeds the tooltip, so
an offline row reads "last checked at HH:MM". It is deliberately *not* turned into
*Local*: that label means the remote side was never compared (a different, and
misleading, statement).

A scoped **Send now** / **Receive now** reloads the local tree before starting
its one-shot (the preview and the confirmed run both call
`_prepare_engine_run`). `FilePanel.load_local_files(..., restore_view=...)`
forwards the folder and row captured before the reload to
`FileTransferTable.restore_view`, so the user stays in the same folder with the
acted-on row selected instead of jumping to the root. The row is applied as a
sticky selection (`_apply_sticky_selection`) across the asynchronous scan's
refreshes and is cleared on user navigation, a new click, or a panel clear
(`main_window/actions.py::ActionsMixin._selection_display_name` maps a nested
target to the first path segment below the current folder).

The row context menu (`file_panel/transfer_table.py::FileTransferTable._show_file_context_menu`)
offers `Open` — a **folder** navigates into it inside the panel (same as a
double-click) while a **file** opens with the system default app — followed by
`Open containing folder` (reveals the entry in the OS file manager:
`FileTransferTable._ctx_open_containing`), then **Send now** / **Receive now** —
one-shot upload-only / download-only of the selected subtree (`signals
FileTransferTable.send_selection_requested` / `receive_selection_requested` →
`main_window/actions.py::ActionsMixin._sync_selection`, scoped through
`settings/cli_args.py::build_selection_args`) — Open With / Copy To / Rename /
Trash / Properties. Send/Receive first run a scoped dry-run preview whose summary
dialog confirms the actions; on accept the real one-shot starts from
`MainWindow._start_selection_run` (the pending selection is carried by
`MainWindow._pending_selection_sync`, consumed by `MainWindow._show_preview_summary`).
The entries are disabled while a sync is running
(`FileTransferTable.set_sync_active`); the File menu hosts the same two actions
(`main_window/actions.py::ActionsMixin._menu_file_send` / `_menu_file_receive`),
enabled only with a selection and a stopped engine.

The menu is built by `FileTransferTable._build_file_context_menu` (split from the
`exec` so its order is asserted in tests) and groups the entries by kind: open ▸
send/receive ▸ copy ▸ rename ▸ destructive ▸ properties (last, the conventional
position). The **copy group** holds `Copy to…` (`_ctx_copy_to`, a file copy) and
the two clipboard commands `Copy path` / `Copy relative path`
(`FileTransferTable.copy_path`): the first puts the absolute path, the second the
path inside the shared folder, both through `os.path.normpath` because the wire
keys use `/` and a folder key ends with `/` (a host would otherwise get mixed
separators and a trailing one). The same two commands are in the **File** menu
(`main_window/actions.py::ActionsMixin._menu_file_copy_path` /
`_menu_file_copy_path_relative`), which is the keyboard-reachable surface, with
`Ctrl+Shift+C` on the absolute form (the conventional "copy as path" chord) and
no shortcut on the relative one; `Copy to…` moved to `Ctrl+Alt+C` to free it.

The table re-localizes its **column headers** on a live language change
(`file_panel/transfer_table.py::FileTransferTable.retranslate`, called through
`file_panel/panel.py::FilePanel.retranslate_columns` from
`main_window/ui.py::UiBuildMixin._apply_translations`). The same path (and
`refresh_fonts`, the restored layout and `_toggle_column` when a hidden column is
shown again) runs
`file_panel/transfer_table.py::FileTransferTable._ensure_readable_headers`: a
section narrower than its own header hint is widened, because the header is
centred and would otherwise clip the label on both sides (the `Estimated time`
column started at the 100 px style default).

**Columns**: the default order is `file_panel/utils.py::_COLUMN_KEYS` — Name,
Direction, Size, Type, Modified, Progress, Status, Estimated Time, Speed. The row
icon is a **decoration of the Name cell** (`FileTableModel.data` `DecorationRole`,
no icon column), so identity leads; Direction follows the name because it is the
one column that says what will happen to the row (the transfer-queue convention)
and it stays on screen in a narrow window instead of being the first section
scrolled out. **Type** and **Speed** are optional and start hidden
(`FileTransferTable._DEFAULT_HIDDEN`): the icon already conveys the type and the
live rate (`file.speed`, `speed_bps`) matters only while a transfer runs.
Direction (`file.direction`, the ↑/↓ arrow — ✕ on a deleted row, ⇄ on a rename) is
**empty at rest** (the dash placeholder is noise in a dense column) and its
operative glyphs are **bold**, a second cue beside the status colour. Visibility
is toggled from the header menu (`FileTransferTable._show_header_context_menu`),
which omits **Name** (the primary column carries the row identity); Name is also
pinned as the first section (`QHeaderView.setFirstSectionMovable`), so a reorder
cannot push the identity column inward. The **data columns are user-resizable**
(`Interactive`, floor `_MIN_COLUMN_WIDTH`, which is also the header's
`setMinimumSectionSize`, so Qt enforces it on a drag), **Name** stays `Stretch`
(the flexible column, still sized by the window); a double-click on a section
handle fits that column to its content
(`FileTransferTable._fit_column_to_contents`).

The whole layout — widths, visual order and hidden sections — is one
`QHeaderView` state blob persisted in `ui/file_table_header_state_v2`
(`FileTransferTable._save_header_state` / `_restore_header_state`), written after
the drag settles (`_STATE_SAVE_DELAY_MS` debounce, flushed by
`FileTransferTable.hideEvent`). **Bump the `_vN` suffix whenever the column set
changes** (as `_v2` did when the icon column became a cell decoration):
`restoreState` does not validate the section count and would apply a
stale blob to the wrong sections. Widths are seeded once from the content on the
first populated refresh (`FileTransferTable._size_columns_to_contents`) when
nothing is stored. Stretch-driven resizes are **not** persisted: Name also
resizes when the window grows, which is not a layout the user chose, so a plain
window resize never marks the profile as having a saved layout. The blob stores
the sort indicator too, which `FileTransferTable._restore_sort_indicator` clears
after the restore (the table starts in the natural folders-first order until the
user clicks a header). **Reset columns** (`file.reset_columns`,
`FileTransferTable._reset_columns`) removes the blob, restores the default
order/visibility and re-fits the widths without persisting, so the next launch is
again a first run.

Because **Name** is the stretch column, Qt answers a shortage by shrinking it
down to the minimum section size instead of extending the scroll range, so the
persisted widths in a narrow window leave file names
unusable while the horizontal scrollbar stays empty:
`FileTransferTable.required_viewport_width` therefore reports the width the
visible sections need with `FileTransferTable.name_floor()` reserved for Name —
`_MIN_NAME_WIDTH` normally, or the roomier `_MIN_NAME_FIRST_RUN` while the
profile has never saved a layout (`FileTransferTable.has_saved_layout`,
captured at construction because the header persists its initial section sizes
on the first layout pass) — and the one-shot
startup fit (`main_window/window.py::MainWindow._fit_table_width`, re-scheduled
from `MainWindow.showEvent` and the model's `rowsInserted` through
`MainWindow._schedule_table_fit`) grows the window by that deficit, clamped to
`QScreen.availableGeometry`. The default and minimum window size live in
`ui/main_window.ui` (not in code), so the fit only ever grows the window beyond
them. The fit is consumed only after a valid measurement
(rows present, window visible) and never fights a later manual resize
(`MainWindow._table_width_fitted`). `FileTransfer.speed_bps`
(`file_panel/models.py::FileTransfer.speed_bps`) also backs the ETA, so the two
stay consistent. A folder keeps the neutral aggregate status (`folder.status.to_sync`)
because it can mix operations; its tooltip spells out the planned actions
(`folder.ops_item`, e.g. "To upload: 3, To download: 1") while files keep the
precise per-action label (`detail.to_upload`, `detail.to_download`, …).

**Live progress**: a received file does not exist on disk before it completes, so
its row cannot come from the scan. `update_transfer_progress`
(`file_panel/transfer_table.py::FileTransferTable.update_transfer_progress`)
creates the row on the first `progress` event (direction taken from the event's
`op`, `size` from the event's total) and the completion handler writes the final
size (`file_panel/models.py::FileTransfer`), so a receive shows its percentage
and rate while it happens and its real size afterwards. The same events arrive
when this app is the device the others sync from (the p2p master): the client
reports the files it serves (`op=upload`) and the pushes it receives
(`op=download`), so the panel shows activity in both roles — the contract lives
in the client wiki (`hsync-client/llm-wiki/modules/sync-core.md`). A transfer
that gives up is flagged `TransferStatus.ERROR`
(`file_panel/transfer_table.py::FileTransferTable.mark_failed`); rows still marked
in flight when the engine stops are reset or dropped
(`file_panel/transfer_table.py::FileTransferTable.clear_transient_progress`).
The rate is the bytes moved over the last `SPEED_WINDOW_SECONDS` of progress
samples (`file_panel/models.py::FileTransfer.note_progress`), not
`bytes / (now - start_time)`: the column follows the real stream, drops back to
the sustained rate within a second and hides the per-chunk pacing of the
limiter. `progress_total` keeps the wire total (compressed upload size, delta
payload) separate from the on-disk `size`.

Row changes that arrive in bursts are **coalesced**: the preview/status
(`FileTransferTable.update_file_status`), live-progress and scan-batch paths
schedule a single debounced rebuild (`FileTransferTable._schedule_refresh`,
100 ms) instead of rebuilding the whole table per event, and the periodic
consistency pass batches its additions and removals
(`FileTransferTable.add_transfers_batch` / `FileTransferTable.remove_transfers`).
Tests that assert rendered cells right after such a call must flush the debounce
with `FileTransferTable.refresh_view()`.

The consistency pass walks with an iterative `os.scandir` and derives each
relative key by slicing the prefix `file_panel/panel.py::_scandir_child_prefix`
builds, matching `os.scandir`'s own `base`/`name` join (a separator is appended
only when the share path does not already end with one, alt separator included).
It recurses only into real directories and, like `os.walk(onerror=None)`, skips a
nested unreadable or vanished directory instead of aborting the whole pass; an
unreadable share root aborts the pass rather than diffing an empty set.

**Clickable links**: the share name, the ancestor breadcrumb segments and the
detail-panel file path use the default text colour with
`text-decoration: underline` instead of the palette link colour, so they read as
normal text; the hand cursor and the `linkActivated` handlers still mark them as
clickable. The current breadcrumb segment is plain text, and the root icon is
inert when the list already shows the root, so a click never targets the folder
already displayed.

**Breadcrumb notation**: segments are joined by
`file_panel/panel.py::_breadcrumb_separator` — `" / "` (GNOME Files, and every
textual path on macOS) or `" > "` on Windows (Explorer) — and the breadcrumb
never starts with a separator: the root icon is the first segment, so a leading
`/` would read as an absolute path. The navigation buttons and the root icon
render at `panel.py::_NAV_ICON_PX` (20 px, a downscale of the bundled 24×24
SVGs); the root icon keeps a `panel.py::_NAV_ICON_BOX_PX` (24 px) click target,
the WCAG 2.2 minimum. `panel.py::FilePanel._refresh_breadcrumb_icon` is the only
place that re-renders that icon, including after a theme change.

Models for the panel live in `file_panel/models.py` — see
[data-models.md](../data-models.md).

### Scoped Send/Receive outcome

A user-invoked *Send now* / *Receive now* is tracked as a one-shot with its own
lifecycle so its result is surfaced exactly once:

- State: `MainWindow._selection_sync_active`, `_selection_sync_phase`
  (`"preview"` | `"confirm"` | `"run"`) and `_pending_selection_sync`
  (`(subdir, direction)`) — `main_window/window.py::MainWindow`.
  `_begin_selection_sync` arms them and shows a persistent progress toast
  (`_show_info_banner(..., auto_hide_ms=0, kind="progress")`); `_finish_selection_sync`
  (`main_window/actions.py::ActionsMixin._finish_selection_sync`) clears them and is
  **idempotent**, so a later engine event never re-surfaces the same result.
- Outcome: `main_window/events.py::_scoped_outcome` derives it from the counters
  on `sync_complete` (the engine's `SyncCycleResult`): `done` when any of
  `downloaded`/`uploaded`/`deleted`/`renamed` is non-zero, `already_synced` when
  the cycle applied nothing, `failed` on failures. Counting `file_transferred`
  events was wrong for renames and deletes, which move no bytes.
- Progress toast: the phase text is `sync.sel_search` (p2p) / `sync.sel_server`
  (server); `_on_peers` (`main_window/events.py::EventsMixin._on_peers`) adds the
  other-device count (`sync.sel_peers_fmt`) while the op is active.
- Outcome: `_surface_selection_outcome` (`main_window/actions.py::ActionsMixin._surface_selection_outcome`)
  routes an *important* result (no devices, server unreachable, failed) through
  `_important_selection_outcome` — a modal dialog when the window is in the
  foreground, otherwise a warning notification (`_notify_warning`, which also
  raises the in-app warning toast) — and a *non-critical* result through
  `_info_selection_outcome` (a green `success` toast for a sent/received count, a
  plain `info` toast for *already up to date* / *nothing to do*, plus an info
  notification suppressed while the window is focused, so exactly one surface
  shows).
- Wiring (in `_connect_signals`): `error_occurred → _on_engine_error`
  (`main_window/ui.py::UiBuildMixin._on_engine_error`, `reason="connection"` in
  server mode → *server unreachable*; a launch failure is skipped and reported by
  `_start_engine`), `no_peers_warning → _on_no_peers`,
  `sync_pending → _on_sync_pending`,
  `sync_completed → _on_sync_completed` and `process_finished → _on_process_finished`
  finalize. `_on_file_transferred` counts real transfers during the `run` phase.
- `_ever_connected` (`main_window/window.py::MainWindow`) is set on the first
  `connected` and reset per engine process, so a one-shot that never linked does
  not claim a lost connection (`_on_status`, `main_window/events.py::EventsMixin._on_status`).

### Transient feedback (overlay toast)

`MainWindow._info_banner` is an **overlay child of `centralWidget()`**, never in
`rootLayout` (`main_window/ui.py::UiBuildMixin._create_info_banner`), so
showing/hiding it cannot reflow the splitter. `_show_info_banner(message,
auto_hide_ms, kind, title)` places it bottom-right above the bottom bar
(`_position_info_banner`, kept anchored on `resizeEvent`) and maps `kind`
(`progress`, `info`, `success`, `warning`, `error`) to a severity colour through a
dynamic `severity` QSS property; `error`/`warning`/`success` also prefix a
severity glyph and the given title, so the severity is recognisable without
relying on colour. Persistence: `error`/`warning` stay until dismissed (`✕`) and
survive both the engine process finishing and a new run, `success` survives the
process finishing, `progress`/`info` auto-hide (`_clear_run_toast` with
`_SURVIVES_FINISH`/`_PERSISTENT_ACROSS_RUNS`). Errors and warnings are surfaced
in-app regardless of the notifications preference:

- `_notify_error` (`main_window/ui.py::UiBuildMixin._notify_error`) and
  `_notify_warning` (`main_window/ui.py::UiBuildMixin._notify_warning`) always show
  the in-app toast and, when the window is out of focus, the OS notification.
- Per-file transfer failures are consolidated into a single error toast at the end
  of a non-scoped run (`_on_transfer_failed` increments `_transfer_failure_count`,
  `_on_process_finished` aggregates).
- `info`/`progress` keep the plain message; the normal `connected` path hides the
  `progress` toast.

One instance `QTimer` (`_info_timer`) owns the auto-hide, so a newer message is
never hidden by an older timeout.

### Desktop log lines

Client log lines arrive verbatim (`<timestamp> - [pid] [client_id] LEVEL:`).
Desktop-originated events use `_append_desktop_log(level, message)`
(`main_window/ui.py::UiBuildMixin._append_desktop_log`), which renders the same shape with `[desktop]` in place of
the pid/CID (no client session exists), reusing
`hsync_common.logger.format_timestamp`: `<timestamp> - [desktop] LEVEL: message`.
Events surfaced to the user (Send/Receive busy, nothing to sync, connection
results) additionally raise a toast, so their outcome is visible without the log
panel. Master role changes (`_on_master_conflict`,
`main_window/events.py::EventsMixin._on_master_conflict`) are informational: a
takeover by a peer that prefers the primary role is logged only (the role
indicator updates), while a genuine two-prefer_master conflict raises a warning.

### Sync state (link status ≠ file-set state)

The status dot answers "is a device reachable"; it never says whether the file
sets match. A second muted label sits in the bottom bar (built in
`main_window/ui.py::UiBuildMixin._load_ui`, right of the share size) and is
rendered by `main_window/events.py::EventsMixin._render_sync_state` from the
state remembered in `EventsMixin._set_sync_state`:

| State | When | Key |
| --- | --- | --- |
| `idle` | no engine run, or the link was never up | `sync.state.idle` |
| `offline` | the link dropped after a real connection; per-file statuses keep their last known value | `sync.state.offline` |
| `checking` | on `connected` and on every comparison start `preview_start` or `status_pass_start` | `sync.state.checking` |
| `waiting_inventory` | `sync_pending` with `reason="awaiting_inventory"` (a device is connected but has not published its inventory) | `sync.state.waiting_inventory` |
| `no_devices` | `no_peers` (one-shot abort) or p2p with `total <= 1` | `sync.state.no_devices` |
| `in_sync` | a comparison end (`preview_end` or `status_pass_end`) with no pending action | `sync.state.in_sync` |
| `pending` | a comparison end with downloads/uploads | `sync.state.pending` (`{download}`/`{upload}`) |
| `pending_other` | a comparison end with only deletes/renames | `sync.state.pending_other` (`{count}`) |

The counts come from `PreviewStats` (`preview_summary_dialog.py`), accumulated by
`EventsMixin._on_file_status` during the comparison; `_sync_state_after_preview`
turns them into the state, and `EventsMixin._begin_comparison` resets them on
every start, so repeated comparisons never inflate the counts. The label is
re-rendered on a language change from `_apply_translations`, and its tooltip is
`tip.sync_state`. A p2p serving device produces the events through the client's
own classification (see the client wiki `modules/p2p-mode.md`), so the same
states cover both roles.

Per-file statuses are a **last known value**, not a live-only signal: dropping
the link sets the summary to `offline` but never rewrites rows to "Local". Only a
new preview/classification (or a fresh scan after an engine restart) changes
them, so a synced file does not look unsynced just because the peer went away.

Every per-file status burst is bracketed by exactly one marker pair, and both
pairs share one rendering path (`EventsMixin._begin_comparison` /
`EventsMixin._finish_comparison`), so the window never infers the end of a burst:

* `preview_start`/`preview_end` — the preview **this window** requested through
  `engine/process.py::HsyncEngine.preview`. Only its end may confirm a pending
  sync: `EventsMixin._on_preview_ended` credits `_pending_initial_reconcile` and
  opens `ActionsMixin._show_preview_summary`.
* `status_pass_start`/`status_pass_end` — the classification pass a **serving
  device** runs on its own share (whenever the client re-classifies the share it
  serves; see the client wiki).
  `EventsMixin._on_status_pass_ended` renders the rows and the file-set state and
  stops there: the device that serves the share has nothing to pull, so there is
  no summary and no `SYNC`.

Keeping the pairs distinct is what protects the confirmation one-shot: a
background pass can never consume the preview the window is waiting for.

**Check for changes** (`main_window/start.py::StartMixin._on_check_changes`) writes
`PREVIEW` on the client's stdin and leaves the rest to the role: a secondary node
answers with the preview cycle (the summary then offers the sync), a primary node
with its classification pass. `_awaiting_preview_for_sync` is therefore armed only
for the requester side, and the action is enabled for as long as the engine runs
(`ActionsMixin._enter_running_ui`), so the action works in both roles. The action
bar button is **icon-only** (`main_window/ui.py::UiBuildMixin._load_ui` clears its
text) and uses the bundled `system-search` icon, so the tooltip (`tip.check_changes`) is
the control's only text and describes the comparison instead of restating a verb;
its name is `menu.sync.check_changes`, shared with the tray entry and with the log line
the click writes (`StartMixin._on_check_changes`).

The p2p **post-initial-sync catch-up** (`EventsMixin._on_connected_refresh`) is
credited only when the preview answers: it arms
`EventsMixin._pending_initial_reconcile` and
`EventsMixin._on_preview_ended` sets `_initial_reconcile_done`. A command the
client never consumed (or a failed preview) therefore cannot burn the one-shot.

The **initial dry-run** launch (`main_window/start.py` → `_on_start` with
`force_dry_run`) ends with a `SYNC` from
`ActionsMixin._show_preview_summary`. That command is written to the client's
stdin, which only the **slave** role reads, while a freshly started node serves
as master first and runs its own dry-run preview before it yields: the phase is
therefore re-armed (`_awaiting_preview_for_sync`) and the `SYNC` is retried on the
next preview, until a live link clears `_is_dry_run_preview` in
`EventsMixin._on_status`. `_dry_run_preview_reported` keeps the "nothing to sync"
toast to a single message.

### Share size

The status bar (right side, before Peers) shows a muted `QLabel`, rendered by
`main_window/ui.py::UiBuildMixin._render_share_size` from the single key
`label.share_size_fmt` ("Shared: X / Y"; `Condivisi: X / Y` in Italian). **X** is
the local size and **Y** the whole-share size; when the total is unknown the
label reads "X / —", and it is a bare `—` before the first value arrives.
**Local** reuses the existing `DirectoryScanWorker` scan: it already `stat`s
every file, so the total is an integer sum with no extra I/O
(`workers.py::DirectoryScanWorker.size_progress` →
`file_panel/panel.py::FilePanel.share_size_changed` →
`main_window/ui.py::UiBuildMixin._on_share_size_changed`). **Total** is the
`folder_size` event's sync-set union (see the client wiki): the remote/master
listing sizes plus local-only pending uploads, so it is the whole share, not
local + remote; scoped runs skip it. While stopped the total is `—` and the scan
value is kept; `_on_process_finished` clears the total and `_prepare_engine_run`
clears it for the new session.

The client emits `folder_size` once per cycle, *before* that cycle's transfers,
so the value it leaves behind describes the folder as of the cycle start.
`FilePanel.refresh_share_size` (`file_panel/panel.py::FilePanel.refresh_share_size`)
therefore re-runs the walk in size-only mode
(`workers.py::DirectoryScanWorker` with `emit_rows=False`: one pass, no counting
pass, no `files_found`/`progress`) when a cycle completes
(`main_window/events.py::EventsMixin._on_sync_completed`) and when the process
ends (`main_window/events.py::EventsMixin._on_process_finished`), without
reloading the file table. It is skipped while a full scan is already running.
Sizes use `hsync_common.format.format_bytes`.

## splash_screen.py — Splash / About

`SplashScreen` (`splash_screen.py::SplashScreen`) loads `ui/splash_screen.ui` and
doubles as the Help → About window. It is a fixed 420×330 frameless window whose
vertical order is: the horizontal brand logo
(`resources/icons/hsync-logo-horizontal.svg`, the same wordmark as the README top
banner, drawn at 240 px wide) above the app name (`app.name`, bold at the default
label size), the bare version (`__version__`, `lblVersion`), the tagline
(`app.tagline`), then the copyright (`about.copyright`) and author
(`about.author`) with space above. As the startup welcome it is a short,
click-dismissible overlay (`main.py::SPLASH_MS`, 1500 ms): it is shown **only on
the first launch** (`main.py::_should_show_splash`: `ui/splash_shown` absent and
`path/local` empty, so an upgraded install with a configured folder never sees it
again) and **never delays** the main window — `main.py::main` calls
`activate_window()` first, then shows the overlay, and connects its `finished` to
the setup-wizard hook. On later launches the window is revealed immediately with
no overlay. `show_as_about`
(`splash_screen.py::SplashScreen.show_as_about`) keeps it open.
A click anywhere dismisses it: for the splash it emits `finished`
(`main.py` connects it to the setup-wizard hook), for the About it just closes.
The Help → About menu entry is the short `menu.help.about` label ("About" /
"Informazioni"), without the app name.

**Frame.** Being frameless, the window draws a 1 px border from the theme's
`QWidget#SplashScreen` rule (`themes.py::_COMMON_QSS`, colours `window_bg` /
`window_border`), so it follows light/dark like the rest of the app. A plain
`QWidget` ignores its stylesheet background/border unless `WA_StyledBackground`
is set, so `SplashScreen.__init__` opts into it; `ui/splash_screen.ui`
deliberately carries no stylesheet.
`tests/test_splash_screen.py::TestSplashFrame` guards both halves.

## Presentation helpers


| Concern | Code | Notes |
| ------- | ---- | ----- |
| Theme | `themes.py` | `detect_system_theme` (`themes.py::detect_system_theme`), palettes `_build_light_palette`/`_build_dark_palette` (`themes.py::_build_light_palette`/`themes.py::_build_dark_palette`), `apply_theme` (`themes.py::apply_theme`). KDE/GTK INI reads (`kdeglobals`, `settings.ini`) go through `kde.py` (`kde.py::read_ini`, `kde.py::config_home`) |
| Confirmations | `widgets/dialogs.py` | `confirm` (`widgets/dialogs.py::confirm`) / `build_confirm_box` (`widgets/dialogs.py::build_confirm_box`) — one localized Yes/No box (safe `No` default, optional app icons) used by every hand-built confirmation in the main window and the Settings dialog |
| Form rows | `widgets/forms.py` | `add_row` (`widgets/forms.py::add_row`) — the labelled `QFormLayout` row shared by the Settings dialog and the setup wizard: caption in the label column, control in the field column, `setBuddy` for focus/mnemonics, alignment left to the platform style hints |
| Fonts | `fonts.py` | `resolve_system_fonts` (`fonts.py::resolve_system_fonts`), `apply_system_fonts` (`fonts.py::apply_system_fonts`), `ui_font` (`fonts.py::ui_font`), `monospace_font` (`fonts.py::monospace_font`), `table_font` (`fonts.py::table_font`), `small_monospace_font` (`fonts.py::small_monospace_font`), `log_monospace_font` (`fonts.py::log_monospace_font`) — desktop UI/monospace fonts + text scaling |
| Icons | `icons.py` | themed SVG load `_load_themed_svg` (`icons.py::_load_themed_svg`), `icon` (`icons.py::icon`)/`themed_icon` (`icons.py::themed_icon`), cache `clear_icon_cache` (`icons.py::clear_icon_cache`) |
| Tray | `system_tray.py::SystemTray` | tray icon/menu; `_make_icon` (`system_tray.py::_make_icon`) |
| Notifications | `notifications.py::NotificationManager` | OS notifications gated by the notifications pref and the tray being visible; suppressed while the main window is in the foreground (`is_foreground` callback wired in `main.py`) and delivered only when out of focus — errors/warnings are then covered by the in-app toast |
| Single instance | `single_instance.py::SingleInstance` | reject a 2nd launch |
| UI loading | `ui/loader.py::UiLoader`, `load_ui_widget` (`ui/loader.py::load_ui_widget`) | load `.ui` resources |

### Host fonts

The GUI follows the desktop's configured fonts instead of Qt's generic default.
`main.py` forces `QT_QPA_PLATFORMTHEME=generic` on Linux (the GTK3 theme plugin
crashes against the bundled GLib/schemas), so `fonts.py` reads the settings
directly: GNOME/Ubuntu via `gsettings` (`font-name`, `monospace-font-name`,
`text-scaling-factor`) and KDE via `~/.config/kdeglobals` (`[General] font`,
`fixed`), then `apply_system_fonts` sets the UI font on the `QApplication` and
caches the monospace font for the log viewer and license dialog. A configured
family that is not installed is kept (Qt/fontconfig substitutes it, as in a
native app) so the configured size is preserved; only a failed probe or an
unknown desktop falls back to `QFontDatabase.systemFont`. The `gsettings`
subprocess runs with
`LD_LIBRARY_PATH`/`PYTHONHOME`/`PYTHONPATH`/`GI_TYPELIB_PATH`/
`GDK_PIXBUF_MODULE_FILE` removed (`fonts.py::_host_env`) so the host binary does
not load the bundled GLib. No fonts are bundled. All three sizes derive from the
same cached monospace font (`fonts.py::_point_smaller_monospace`): the license
dialog uses `small_monospace_font` (`fonts.py::small_monospace_font`, one point
smaller, floor 8 pt) and the log viewer uses `log_monospace_font`
(`fonts.py::log_monospace_font`, two points smaller, floor 7 pt) because its lines
are long — at a 9 pt desktop monospace that is 13 visible lines and ~22% more
characters per line than the 8 pt size. `appearance/font_scale` (`standard`
default / `compact`) scales the resolved UI and monospace bases in
`fonts.py::resolve_system_fonts` (`compact` = one point smaller, floor 8 pt), so
every derived font follows. The file table uses `table_font`
(`fonts.py::table_font`), the cached UI font with no extra delta: desktop size
with `standard`, one point smaller with `compact` (UI labels `Standard` /
`Slightly reduced`, `locales/en.py` keys `settings.font_size_standard` /
`settings.font_size_compact`). `table_row_height`
(`fonts.py::table_row_height`, WCAG 2.2 target size) is applied in
`file_panel/transfer_table.py::FileTransferTable.refresh_fonts`, which
`main_window/start.py::StartMixin._apply_settings_changes` calls when the preference changes.
A live scale change re-resolves the whole window:
`main_window/start.py::StartMixin._apply_settings_changes` applies the new
application font and then calls `fonts.py::reset_widget_fonts`, which clears the
font of every widget in the tree. That step is mandatory because the stylesheet
resolves each widget's font at polish time and Qt then treats it as explicitly
set, so `QApplication.setFont` alone leaves the status bar and the share/mode
labels at the previous size (only the widgets that receive an explicit
`setFont` — file table, log view, menus — followed). Those explicit fonts are
re-applied right after the reset.
The fonts are set programmatically
(`main_window/ui.py::UiBuildMixin._load_ui`, `license_dialog.py::LicenseDialog`);
the QSS pins no `font-family`/`font-size` (`themes.py::_COMMON_QSS`) but
does frame the log box via `QPlainTextEdit#logView` (the selector must match the
object name in `ui/main_window.ui`; `tests/test_themes.py::TestObjectNameSelectors`
guards it).

### Log panel colors

`build_hsync_args` (`settings/cli_args.py`) launches the engine with
`--color=always` (the client's `--color` contract, `hsync_common.runtime.ColorMode`),
so the raw stdout feed carries the SGR sequences loguru builds from
`hsync_common.logger.LEVEL_STYLES` and `hsync_common.labels.LABEL_STYLES`.
`ansi.py::parse_sgr` splits each line into `ansi.py::AnsiRun`s (foreground index,
bold, dim) and `log_style.py::styled_runs` turns them into `QTextCharFormat`s via
`LOG_COLORS` (`log_style.py`, per theme). Lines without SGR — the Desktop's own
`[desktop] LEVEL:` markers, plain logs — fall back to the same two shared
mappings, matched by `log_style.py::_LEVEL_RE` / `log_style.py::_LABEL_RE`
(labels longest-first so `[REMOTE DOWNLOAD]` never collapses into `[DOWNLOAD]`).

`main_window/ui.py::UiBuildMixin._append_log` inserts the runs with a `QTextCursor` (never
`appendPlainText` for styled lines), so the escape sequences are stripped from
`toPlainText()` (copy, tests, `maximumBlockCount` unchanged). Colors are baked
into the formats, so `_rerender_log` (`main_window/ui.py::UiBuildMixin._rerender_log`) re-renders the document when the
theme changes, called from `_apply_settings_changes` and
`_on_system_color_scheme_changed`; the re-render works from the plain text and
therefore re-applies the level/label fallback colors.

Dialog buttons use the **bundled (app-theme)** icons: `icon(name)` always prefers
the bundled SVG (recoloured per light/dark) over the system theme, falling back
to the system theme only when no bundled icon exists. The application icon
`hsync-desktop` is bundled in `resources/icons/` and applied in
`main.py::_configure_app` together with `setDesktopFileName("hsync-desktop")`, so
the running window's WM_CLASS/app_id matches `hsync-desktop.desktop` and the
taskbar shows the app icon. The app-icon SVG keeps `<svg` at the very top of the
file (no long leading comment): gdk-pixbuf/GNOME only recognizes an SVG when the
root element is within the first bytes, otherwise the icon renders blank. The Settings **Save** /
**Cancel** buttons and the `TrustedKeysDialog` add dialogs use
`style_ok_cancel_button_box` (`icons.py::style_ok_cancel_button_box`) with
`document-save` / `dialog-cancel` (the latter bundled for this purpose, plus the
translated `settings.save`/`settings.cancel` labels); the `TrustedKeysDialog`
**Close** button uses `window-close` with the `action.close` label (translated in
every locale).

> Strings shown here must be looked up via `i18n.tr` and exist in all locales
> (see [settings.md](settings.md)).

> **Ampersands.** `QGroupBox`, `QAbstractButton` and the tab bar read `&` as a
> mnemonic marker and underline the character after it, so prose such as
> "Share & Path" or "Save & Retry" renders as "Share_Path" / "Save_Retry"
> unless the sink escapes it. Those sinks must receive
> `widgets/text.py::escape_mnemonics` output; menus keep
> the single `&`, which there *is* the Alt shortcut. A `QLabel` without a buddy,
> the combo-box items, window titles and message boxes already show the
> ampersand and take the raw string. `tests/test_mnemonic_escaping.py` scans
> every locale for a leftover single `&` in the Settings and credential dialogs.

## Safety badges in the bottom bar

Two independent indicators sit next to the status label of
`ui/main_window.ui` (both hidden by default, both refreshed by
`main_window/ui.py::UiBuildMixin` on build, on language change and after the
settings are applied):

- `simulationBadge` — `ui.py::UiBuildMixin._refresh_simulation_state`, driven by
  `settings/cli_args.py::is_simulation_mode` (window title suffix and tray
  tooltip change with it).
- `deletionBadge` — `ui.py::UiBuildMixin._refresh_deletion_badge`, driven by
  `settings/cli_args.py::get_deletion_policy`: visible only while the deletion
  policy is `keep`, so a device that silently never deletes always says so.
  `get_deletion_policy` is the single read of `sync/deletion_policy`, also used
  by `settings/cli_args.py::build_hsync_args`, so the badge cannot disagree
  with the flag the engine receives.
