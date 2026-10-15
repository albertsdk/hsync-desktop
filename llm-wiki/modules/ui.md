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
`file_progress`/`file_renamed`,
`pairing_needed→_on_pairing_needed` / `fingerprint_changed→_on_fingerprint_changed`.
`error_occurred` is always routed to `_on_engine_error` (`main_window/ui.py::MainWindow._on_engine_error`),
which stores the message and mirrors it into the log panel (the desktop
notification is wired separately, only when a notifier exists).
File-action menu slots: open/open-with/copy-to/rename/trash/
properties (`main_window/ui.py::MainWindow._create_menu_bar`).

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
always `network-p2p` (the bootnode no longer changes the icon).

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
tab; the settings dialog passes the tab matching the panel that launched it. The
bootnode/server tabs share `_HostAddDialog` and `_build_host_tab` (host:port
stores); *Add* supports "read from node" or manual entry. Device *Add* pre-fills
the bucket from `sync/bucket`. The tab/column labels are localized in the five
locales (`trusted_keys.tabs_peers` = Devices, `trusted_keys.peer` = Device,
`trusted_keys.fingerprint` = the locale's term for the certificate fingerprint).
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

Models for the panel live in `file_panel/models.py` — see
[data-models.md](../data-models.md).

## splash_screen.py — Splash / About

`SplashScreen` (`splash_screen.py::SplashScreen`) loads `ui/splash_screen.ui` and
doubles as the Help → About window. It is a fixed 420×330 frameless window whose
vertical order is: the horizontal brand logo
(`resources/icons/hsync-logo-horizontal.svg`, the same wordmark as the README top
banner, drawn at 240 px wide) above the app name (`app.name`, bold at the default
label size), the bare version (`__version__`, `lblVersion`), the tagline
(`app.tagline`), then the copyright (`about.copyright`) and author
(`about.author`) with space above. `show_and_dismiss` auto-closes after 2500 ms;
`show_as_about` (`splash_screen.py::SplashScreen.show_as_about`) keeps it open.
A click anywhere dismisses it: for the splash it emits `finished`
(`main.py` connects it to reveal the main window), for the About it just closes.
The Help → About menu entry is the short `menu.help.about` label ("About" /
"Informazioni"), no longer carrying the app name.

## Presentation helpers

| Concern | Code | Notes |
| ------- | ---- | ----- |
| Theme | `themes.py` | `detect_system_theme` (`themes.py::detect_system_theme`), palettes `_build_light_palette`/`_build_dark_palette` (`themes.py::_build_light_palette`/`themes.py::_build_dark_palette`), `apply_theme` (`themes.py::apply_theme`) |
| Icons | `icons.py` | themed SVG load `_load_themed_svg` (`icons.py::_load_themed_svg`), `icon` (`icons.py::icon`)/`themed_icon` (`icons.py::themed_icon`), cache `clear_icon_cache` (`icons.py::clear_icon_cache`) |
| Tray | `system_tray.py::SystemTray` | tray icon/menu; `_make_icon` (`system_tray.py::_make_icon`) |
| Notifications | `notifications.py::NotificationManager` | OS notifications (gated by pref) |
| Single instance | `single_instance.py::SingleInstance` | reject a 2nd launch |
| UI loading | `ui/loader.py::UiLoader`, `load_ui_widget` (`ui/loader.py::load_ui_widget`) | load `.ui` resources |

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
