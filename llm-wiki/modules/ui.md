# HSYNC Desktop — UI (window, panels, presentation)

Qt widgets that render engine state. All UI mutation stays on the main thread,
driven by `HsyncEngine` signals (see [engine.md](engine.md)).

## main_window/ — MainWindow

`MainWindow` is assembled from responsibility mixins (all sharing `self`):
`window.py` (`MainWindow`, `__init__`, `_connect_signals`), `ui.py`
(UI construction), `events.py` (engine-signal slots), `trust.py`
(trust/pinning + pre-flight), `start.py` (start/stop/refresh/pre-flight checks),
`actions.py` (menu actions) and `lifecycle.py` (tray/quit/close/eventFilter).
The mixins suppress `attr-defined` in mypy because they operate on the composed
window's attributes.

| Symbol | Location | Role |
| ------ | -------- | ---- |
| `MainWindow` | `main_window/window.py::MainWindow` | top-level window; owns engine + tray; single open `SettingsDialog` (`_settings_dialog`, re-raised on re-open) |
| `_load_ui` | `main_window/ui.py::MainWindow._load_ui` | build/compose the central UI |
| `_create_menu_bar` | `main_window/ui.py::MainWindow._create_menu_bar` | menus + actions (start/stop/refresh/direction/file ops/help) |
| `_connect_signals` | `main_window/window.py::MainWindow._connect_signals` | bind every engine `Signal` to a slot |
| `_apply_translations` | `main_window/ui.py::MainWindow._apply_translations` | re-translate on language change |
| `_update_menu_state` | `main_window/ui.py::MainWindow._update_menu_state` | enable/disable actions by run state |
| `_quit` | `main_window/lifecycle.py::MainWindow._quit` | tray "Quit": confirm while a sync runs, then `_shutdown` |
| `_shutdown` | `main_window/lifecycle.py::MainWindow._shutdown` | prompt-free close (stop engine, save geometry, hide tray, quit); shared by the SIGINT handler |

Engine→slot wiring (in `_connect_signals`, `main_window/window.py::MainWindow._connect_signals`): `log_received→_append_log`,
`status_changed→_on_status`, `peers_changed`/`master_changed`, `file_transferred→_on_file_transferred`,
`transfer_failed→_on_transfer_failed`, `sync_paused→_on_sync_paused`,
`file_progress`/`file_renamed`, `folder_size_changed→_on_folder_size`,
`file_panel.share_size_changed→_on_share_size_changed`,
`pairing_needed→_on_pairing_needed` / `fingerprint_changed→_on_fingerprint_changed`.
`error_occurred` is always routed to `_on_engine_error` (`main_window/ui.py::MainWindow._on_engine_error`),
which stores the message and mirrors it into the log panel (the desktop
notification is wired separately, only when a notifier exists).
File-action menu slots: open/open-with/copy-to/rename/trash/
properties (`main_window/ui.py::MainWindow._create_menu_bar`).

Help menu (`main_window/ui.py::MainWindow._create_menu_bar`): external links
first (Documentation, Project on GitHub), then a separator and the local
app-info dialogs — **License** (`main_window/actions.py::MainWindow._show_license`
→ `license_dialog.py::LicenseDialog`, a scrollable read-only view of the bundled
`LICENSE`) and **About** last, the conventional position.

### Engine start failure feedback

`_start_engine` (`main_window/start.py::MainWindow._start_engine`) wraps
`HsyncEngine.start`: on failure it records the reason emitted through
`error_occurred` and calls `_report_engine_start_failure`
(`main_window/start.py::MainWindow._report_engine_start_failure`), which raises a
critical `QMessageBox` (title `notif.error`, body `notif.engine_start_failed`,
the engine reason as informative text). Both start sites use it —
`_continue_start_after_disclaimer` and `_retry_after_auth_fix` — so a start that
cannot launch (missing/incompatible binary, spawn failure) no longer looks like a
silent no-op; the caller resets the UI via `_reset_ui_stopped`.

### Remote endpoint icon (`_update_path_display`)

`main_window/start.py::MainWindow._update_path_display` picks the remote icon from
`QSettings`: server mode (`p2p/enabled` false) → `network-cloud`; p2p mode →
always `network-p2p` (the bootnode no longer changes the icon). The role
indicator is p2p-only: `_apply_role_visibility`
(`main_window/ui.py::MainWindow._apply_role_visibility`) shows the icon in p2p
mode and hides the whole indicator in Server Mode. Until the election event the
icon is the neutral `role-unknown` and the text is hidden; the
**Nodo primario/secondario** text appears only when connected and the role is
known (`main_window/events.py::MainWindow._on_master` + `_on_status`), and the
state resets per engine process (`_prepare_engine_run`).

### Share name next to the folder icon

The active share (bucket) is the user-facing identity, so it labels the local
folder in the action bar — next to the folder icon — as a clickable link
(`main_window/start.py::MainWindow._update_path_display`; the name comes from
`main_window/start.py::MainWindow._share_display_name`: detected bucket →
`sync/bucket` → folder name). Clicking it opens the local folder
(`main_window/start.py::MainWindow._on_path_clicked`); the full local path is the
label's tooltip. That tooltip is **intentionally exempt** from the "Show tooltips"
preference (`appearance/tooltips`), which only governs the settings fields. The
window title stays the bare app name (`main_window/events.py::MainWindow._on_bucket_detected`).
The share name is seeded from `sync/bucket` and updated on the client's `bucket`
event (signal `engine/process.py::HsyncEngine.bucket_detected`).

### Trust refusal dialogs (SSH-style, no terminal)

`MainWindow` answers the client's trust refusals with dialogs instead of a
terminal (the client keeps retrying on the mDNS path, so the handlers dedupe):

- `_on_pairing_needed` / `_on_fingerprint_changed` (`main_window/trust.py::MainWindow._on_pairing_needed` / `main_window/trust.py::MainWindow._on_fingerprint_changed`)
  route by `scope`: `master` → `add_peer_pin`/`remove_peer_pin`; `bootnode`/`server`
  → the helpers returned by `_host_trust_actions` (`main_window/trust.py::MainWindow._host_trust_actions`) (`add_bootnode_trust`/
  `remove_bootnode_trust` or `add_server_trust`/`remove_server_trust`). Dedupe is
  `_trust_prompted` `dict[(scope, identity)] → last fingerprint` (`main_window/window.py::MainWindow`) via
  `_should_prompt_trust` (`main_window/trust.py::MainWindow._should_prompt_trust`), cleared on start/stop (`main_window/window.py::MainWindow`): a
  repeated refusal for the same fingerprint reuses no dialog, a changed one
  re-prompts. A dismissed or ignored dialog never touches the stored pin (the
  host branch acts only on the explicit Trust/Forget buttons).
- `_maybe_offer_restart` (`main_window/trust.py::MainWindow._maybe_offer_restart`) offers to restart a stopped sync after a
  bootnode/server pin change (those failures are fatal; mDNS refusals are not).
- `_ensure_bootnode_trust` (`main_window/trust.py::MainWindow._ensure_bootnode_trust`) and `_ensure_server_trust` (`main_window/trust.py::MainWindow._ensure_server_trust`) are the
  start pre-flights, both delegating to `_confirm_host_trust` (`main_window/trust.py::MainWindow._confirm_host_trust`): skip
  unless the mode/policy/URL apply; skip when the known-hosts store already holds
  `host:port`; else `fetch_*_fingerprint` → confirm → `add_*_trust`. They write
  the shared known-hosts stores (no GUI-only fingerprint settings).

## trusted_keys.py — TrustedKeysDialog

`TrustedKeysDialog` (`trusted_keys.py::TrustedKeysDialog`) lists and edits all three stores via
the `engine` subprocess helpers (never the store files directly): three tabs
(bootnodes / servers / devices), each a `QTableWidget` + Add/Remove/Refresh. The
`initial_tab` keyword (`bootnodes` default, or `servers`) selects the opening
tab; the settings dialog passes the tab matching the panel that launched it.
Tabs are filtered by the active mode
(`trusted_keys.py::TrustedKeysDialog._apply_mode_tab_visibility`, reading
`p2p/enabled`): p2p shows **Relay servers** + **Devices** and hides the server
store; Server Mode shows only **Server HSYNC** and hides the p2p stores. When
`initial_tab` is hidden, the dialog falls back to the first visible page. The
server tab is labelled **Server HSYNC** (`trusted_keys.tabs_servers`). The
bootnode/server tabs share `_HostAddDialog` and `_build_host_tab` (host:port
stores); *Add* supports "read from server" or manual entry. Device *Add* pre-fills
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
| `FileTransferTable` | `file_panel/transfer_table.py::FileTransferTable` | per-file rows (status/progress/size) |
| `FileDetailPanel` | `file_panel/detail_panel.py::FileDetailPanel` | selected-file metadata pane |
| `ProgressBarDelegate` / `CenteredIconDelegate` | `file_panel/delegates.py::ProgressBarDelegate` / `file_panel/delegates.py::CenteredIconDelegate` | cell rendering |
| `LoadingOverlay` | `file_panel/overlay.py::LoadingOverlay` | busy overlay during scans |
| `_confirm_dialog` | `file_panel/dialogs.py::_confirm_dialog` | reusable confirm prompt |
| `DirectoryScanWorker` | `file_panel/workers.py::DirectoryScanWorker` | off-thread local tree scan |
| `_classify_file` / `format_mtime` | `file_panel/utils.py::_classify_file` / `file_panel/utils.py::format_mtime` | type/icon + mtime formatting |

Renaming a row (`file_panel/transfer_table.py::FileTransferTable.rename_file`)
keeps its modification date: the new row inherits the previous row's mtime when
the filesystem read returns nothing (the rename event may arrive before the local
rename lands — `main_window/events.py::MainWindow._on_file_renamed` reads the
destination, falling back to the source).

`FileTransferTable.set_connected` (`file_panel/transfer_table.py::FileTransferTable.set_connected`,
driven from `main_window/events.py::MainWindow._on_status`) greys **Local** rows
(`TransferStatus.LOCAL` → `STATUS_COLORS`) only while a connection is active.
When the link is disconnected/connecting/waiting the rows keep the default text
colour, because "Local" is the resting state rather than a comparison result;
real transfer states keep their own colours.

A folder row with no aggregated children (an empty directory) shows the folder's
own status instead of defaulting to *Local*: a directory created by a remote peer
is stored under a trailing-slash key and marked **Synced**
(`main_window/events.py::MainWindow._on_directory_created` normalizes the key;
`file_panel/transfer_table.py` module maps `_STATUS_PRIORITY`/`_FOLDER_STATUS_KEYS`
resolve an empty folder from its transfer status). A folder that does have
children still takes the highest-priority child status.

A scoped **Send now** / **Receive now** reloads the local tree before starting
its one-shot (the preview and the confirmed run both call
`_prepare_engine_run`). `FilePanel.load_local_files(..., restore_view=...)`
forwards the folder and row captured before the reload to
`FileTransferTable.restore_view`, so the user stays in the same folder with the
acted-on row selected instead of jumping to the root. The row is applied as a
sticky selection (`_apply_sticky_selection`) across the asynchronous scan's
refreshes and is cleared on user navigation, a new click, or a panel clear
(`main_window/actions.py::MainWindow._selection_display_name` maps a nested
target to the first path segment below the current folder).

The row context menu (`file_panel/transfer_table.py::FileTransferTable._show_file_context_menu`)
offers `Open` — a **folder** navigates into it inside the panel (same as a
double-click) while a **file** opens with the system default app — followed by
`Open containing folder` (reveals the entry in the OS file manager:
`FileTransferTable._ctx_open_containing`), then **Send now** / **Receive now** —
one-shot upload-only / download-only of the selected subtree (`signals
FileTransferTable.send_selection_requested` / `receive_selection_requested` →
`main_window/actions.py::MainWindow._sync_selection`, scoped through
`settings/cli_args.py::build_selection_args`) — Open With / Copy To / Rename /
Trash / Properties. Send/Receive first run a scoped dry-run preview whose summary
dialog confirms the actions; on accept the real one-shot starts from
`MainWindow._start_selection_run` (the pending selection is carried by
`MainWindow._pending_selection_sync`, consumed by `MainWindow._show_preview_summary`).
The entries are disabled while a sync is running
(`FileTransferTable.set_sync_active`); the File menu hosts the same two actions
(`main_window/actions.py::MainWindow._menu_file_send` / `_menu_file_receive`),
enabled only with a selection and a stopped engine.

The table re-localizes its **column headers** on a live language change
(`file_panel/transfer_table.py::FileTransferTable.retranslate`, called through
`file_panel/panel.py::FilePanel.retranslate_columns` from
`main_window/ui.py::MainWindow._apply_translations`).

**Columns**: the table ships the standard columns plus two optional ones —
**Speed** (`file.speed`, the live `speed_bps` rate, blank when not transferring)
and **Direction** (`file.direction`, the ↑/↓ arrow) — both hidden by default.
Visibility is toggled from the header menu and persisted as stable keys in
`ui/file_columns_hidden` (`FileTransferTable._save_column_visibility` /
`FileTransferTable._restore_column_visibility`). `FileTransfer.speed_bps`
(`file_panel/models.py::FileTransfer.speed_bps`) also backs the ETA, so the two
stay consistent.

**Clickable links**: the share name, the breadcrumb segments and the detail-panel
file path use the default text colour with `text-decoration: underline` instead
of the palette link colour, so they read as normal text; the hand cursor and the
`linkActivated` handlers still mark them as clickable.

Models for the panel live in `file_panel/models.py` — see
[data-models.md](../data-models.md).

### Scoped Send/Receive outcome

A user-invoked *Send now* / *Receive now* is tracked as a one-shot with its own
lifecycle so its result is surfaced exactly once:

- State: `MainWindow._selection_sync_active`, `_selection_sync_phase`
  (`"preview"` | `"confirm"` | `"run"`), `_selection_result_count` and
  `_pending_selection_sync` (`(subdir, direction)`) — `main_window/window.py::MainWindow`.
  `_begin_selection_sync` arms them and shows a persistent progress toast
  (`_show_info_banner(..., auto_hide_ms=0, kind="progress")`); `_finish_selection_sync`
  (`main_window/actions.py::MainWindow._finish_selection_sync`) clears them and is
  **idempotent**, so a later engine event never re-surfaces the same result.
- Progress toast: the phase text is `sync.sel_search` (p2p) / `sync.sel_server`
  (server); `_on_peers` (`main_window/events.py::MainWindow._on_peers`) adds the
  other-device count (`sync.sel_peers_fmt`) while the op is active.
- Outcome: `_surface_selection_outcome` (`main_window/actions.py::MainWindow._surface_selection_outcome`)
  routes an *important* result (no devices, server unreachable, failed) through
  `_important_selection_outcome` — a modal dialog when the window is in the
  foreground, otherwise a warning notification — and a *non-critical* result
  (already up to date, sent/received counts) through `_info_selection_outcome`
  (outcome toast + info notification, the latter suppressed while the window is
  focused, so exactly one surface shows).
- Wiring (in `_connect_signals`): `error_occurred → _on_engine_error`
  (`main_window/ui.py::MainWindow._on_engine_error`, `reason="connection"` in
  server mode → *server unreachable*; a launch failure is skipped and reported by
  `_start_engine`), `no_peers_warning → _on_no_peers`,
  `sync_completed → _on_sync_completed` and `process_finished → _on_process_finished`
  finalize. `_on_file_transferred` counts real transfers during the `run` phase.
- `_ever_connected` (`main_window/window.py::MainWindow`) is set on the first
  `connected` and reset per engine process, so a one-shot that never linked does
  not claim a lost connection (`_on_status`, `main_window/events.py::MainWindow._on_status`).

### Transient feedback (overlay toast)

`MainWindow._info_banner` is an **overlay child of `centralWidget()`**, never in
`rootLayout` (`main_window/ui.py::MainWindow._create_info_banner`), so
showing/hiding it cannot reflow the splitter. `_show_info_banner(message,
auto_hide_ms, kind)` places it bottom-right above the bottom bar
(`_position_info_banner`, kept anchored on `resizeEvent`) and sets `kind`:
`progress` (indeterminate bar, persistent until hidden), `warning`, `info` or
`outcome`. Lifecycle: `_prepare_engine_run` clears any toast; `_on_process_finished`
and `_reset_ui_stopped` clear run-scoped toasts **except** `outcome`, so a result
survives the engine exiting; the normal `connected` path hides the `progress`
toast. One instance `QTimer` (`_info_timer`) owns the auto-hide, so a newer
message is never hidden by an older timeout.

### Desktop log lines

Client log lines arrive verbatim (`<timestamp> - [pid] [client_id] LEVEL:`).
Desktop-originated events use `MainWindow._append_desktop_log(level, message)`
(`main_window/ui.py`), which renders the same shape with `[desktop]` in place of
the pid/CID (no client session exists), reusing
`hsync_common.logger.format_timestamp`: `<timestamp> - [desktop] LEVEL: message`.
Events surfaced to the user (Send/Receive busy, nothing to sync, connection
results) additionally raise a toast, so their outcome is visible without the log
panel.

### Share size

The status bar (right side, before Peers) shows a muted `QLabel`, rendered by
`main_window/ui.py::MainWindow._render_share_size` as
`label.share_size_fmt` ("Local X · Total Y") or, when the total is unknown,
`label.share_size_local_fmt`. **Local** reuses the existing
`DirectoryScanWorker` scan: it already `stat`s every file, so the total is an
integer sum with no extra I/O (`workers.py::DirectoryScanWorker.size_progress` →
`file_panel/panel.py::FilePanel.share_size_changed` →
`main_window/ui.py::MainWindow._on_share_size_changed`). **Total** is the
client's `folder_size` event (see the client wiki), computed from the
remote/master listing already fetched plus local-only pending uploads; scoped
runs skip it. While stopped the total is `—` and the scan value is kept;
`_on_process_finished` clears the total and `_prepare_engine_run` clears it for
the new session. Sizes use `hsync_common.format.format_bytes`.

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
"Informazioni"), no longer carrying the app name.

## Presentation helpers

| Concern | Code | Notes |
| ------- | ---- | ----- |
| Theme | `themes.py` | `detect_system_theme` (`themes.py::detect_system_theme`), palettes `_build_light_palette`/`_build_dark_palette` (`themes.py::_build_light_palette`/`themes.py::_build_dark_palette`), `apply_theme` (`themes.py::apply_theme`) |
| Fonts | `fonts.py` | `resolve_system_fonts` (`fonts.py::resolve_system_fonts`), `apply_system_fonts` (`fonts.py::apply_system_fonts`), `monospace_font` (`fonts.py::monospace_font`), `small_monospace_font` (`fonts.py::small_monospace_font`) — desktop UI/monospace fonts + text scaling |
| Icons | `icons.py` | themed SVG load `_load_themed_svg` (`icons.py::_load_themed_svg`), `icon` (`icons.py::icon`)/`themed_icon` (`icons.py::themed_icon`), cache `clear_icon_cache` (`icons.py::clear_icon_cache`) |
| Tray | `system_tray.py::SystemTray` | tray icon/menu; `_make_icon` (`system_tray.py::_make_icon`) |
| Notifications | `notifications.py::NotificationManager` | OS notifications gated by the notifications pref and the tray being visible; routine (info) events are suppressed while the main window is in the foreground (`is_foreground` callback wired in `main.py`), warnings/errors always delivered |
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
not load the bundled GLib. No fonts are bundled. The log viewer and the license
dialog use `small_monospace_font` (`fonts.py::small_monospace_font`): the desktop
monospace one point smaller, floored at 8 pt. The fonts are set programmatically
(`main_window/ui.py::MainWindow._load_ui`, `license_dialog.py::LicenseDialog`);
the QSS no longer pins a `font-family`/`font-size` (`themes.py::_COMMON_QSS`).

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
