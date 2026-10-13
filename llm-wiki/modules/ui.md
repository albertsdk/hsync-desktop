# HSYNC Desktop — UI (window, panels, presentation)

Qt widgets that render engine state. All UI mutation stays on the main thread,
driven by `HsyncEngine` signals (see [engine.md](engine.md)).

## main_window.py — MainWindow

| Symbol | Location | Role |
| ------ | -------- | ---- |
| `MainWindow` | `main_window.py::MainWindow` | top-level window; owns engine + tray; single open `SettingsDialog` (`_settings_dialog`, re-raised on re-open) |
| `_load_ui` | `main_window.py::MainWindow._load_ui` | build/compose the central UI |
| `_create_menu_bar` | `main_window.py::MainWindow._create_menu_bar` | menus + actions (start/stop/refresh/direction/file ops/help) |
| `_connect_signals` | `main_window.py::MainWindow._connect_signals` | bind every engine `Signal` to a slot |
| `_apply_translations` | `main_window.py::MainWindow._apply_translations` | re-translate on language change |
| `_update_menu_state` | `main_window.py::MainWindow._update_menu_state` | enable/disable actions by run state |

Engine→slot wiring (in `_connect_signals`, `main_window.py::MainWindow._connect_signals`): `log_received→_append_log`,
`status_changed→_on_status`, `peers_changed`/`master_changed`, `file_transferred→_on_file_transferred`,
`transfer_failed→_on_transfer_failed`, `sync_paused→_on_sync_paused`,
`file_progress`/`file_renamed`,
`pairing_needed→_on_pairing_needed` / `fingerprint_changed→_on_fingerprint_changed`.
File-action menu slots: open/open-with/copy-to/rename/trash/
properties (`main_window.py::MainWindow._create_menu_bar`).

### Remote endpoint icon (`_update_path_display`)

`main_window.py::MainWindow._update_path_display` picks the remote icon from
`QSettings`: server mode (`p2p/enabled` false) → `network-cloud`; p2p mode →
`network-cloud` when `p2p/bootnode` is non-empty (cross-network via bootnode),
`network-p2p` when no bootnode is configured (pure LAN mDNS).

### Trust refusal dialogs (SSH-style, no terminal)

`MainWindow` answers the client's trust refusals with dialogs instead of a
terminal (the client keeps retrying on the mDNS path, so the handlers dedupe):

- `_on_pairing_needed` / `_on_fingerprint_changed` (`main_window.py::MainWindow._on_pairing_needed` / `main_window.py::MainWindow._on_fingerprint_changed`)
  route by `scope`: `master` → `add_peer_pin`/`remove_peer_pin`; `bootnode`/`server`
  → the helpers returned by `_host_trust_actions` (`main_window.py::MainWindow._host_trust_actions`) (`add_bootnode_trust`/
  `remove_bootnode_trust` or `add_server_trust`/`remove_server_trust`). Dedupe is
  `_trust_prompted` `dict[(scope, identity)] → last fingerprint` (`main_window.py::MainWindow`) via
  `_should_prompt_trust` (`main_window.py::MainWindow._should_prompt_trust`), cleared on start/stop (`main_window.py::MainWindow`): a
  repeated refusal for the same fingerprint reuses no dialog, a changed one
  re-prompts. A dismissed or ignored dialog never touches the stored pin (the
  host branch acts only on the explicit Trust/Forget buttons).
- `_maybe_offer_restart` (`main_window.py::MainWindow._maybe_offer_restart`) offers to restart a stopped sync after a
  bootnode/server pin change (those failures are fatal; mDNS refusals are not).
- `_ensure_bootnode_trust` (`main_window.py::MainWindow._ensure_bootnode_trust`) and `_ensure_server_trust` (`main_window.py::MainWindow._ensure_server_trust`) are the
  start pre-flights, both delegating to `_confirm_host_trust` (`main_window.py::MainWindow._confirm_host_trust`): skip
  unless the mode/policy/URL apply; skip when the known-hosts store already holds
  `host:port`; else `fetch_*_fingerprint` → confirm → `add_*_trust`. They write
  the shared known-hosts stores (no GUI-only fingerprint settings).

## trusted_keys.py — TrustedKeysDialog

`TrustedKeysDialog` (`trusted_keys.py::TrustedKeysDialog`) lists and edits all three stores via
the `engine` subprocess helpers (never the store files directly): three tabs
(bootnodes / servers / peers), each a `QTableWidget` + Add/Remove/Refresh. The
bootnode/server tabs share `_HostAddDialog` and `_build_host_tab` (host:port
stores); *Add* supports "read from node" or manual entry. Peer *Add* pre-fills
the bucket from `sync/bucket`. The peers tab shows
`trusted_keys.capability_missing` when the binary lacks the `trust` subcommand
(`supports_peer_trust`).

## file_panel/ — live transfer view

| Symbol | Location | Role |
| ------ | -------- | ---- |
| `FilePanel` | `file_panel/widgets.py::FilePanel` | container: table + detail pane + overlay |
| `FileTransferTable` | `file_panel/widgets.py::FileTransferTable` | per-file rows (status/progress/size) |
| `FileDetailPanel` | `file_panel/widgets.py::FileDetailPanel` | selected-file metadata pane |
| `ProgressBarDelegate` / `CenteredIconDelegate` | `file_panel/widgets.py::ProgressBarDelegate` / `file_panel/widgets.py::CenteredIconDelegate` | cell rendering |
| `LoadingOverlay` | `file_panel/widgets.py::LoadingOverlay` | busy overlay during scans |
| `_confirm_dialog` | `file_panel/widgets.py::_confirm_dialog` | reusable confirm prompt |
| `DirectoryScanWorker` | `file_panel/workers.py::DirectoryScanWorker` | off-thread local tree scan |
| `_classify_file` / `format_mtime` | `file_panel/utils.py::_classify_file` / `file_panel/utils.py::format_mtime` | type/icon + mtime formatting |

Models for the panel live in `file_panel/models.py` — see
[data-models.md](../data-models.md).

## Presentation helpers

| Concern | Code | Notes |
| ------- | ---- | ----- |
| Theme | `themes.py` | `detect_system_theme` (`themes.py::detect_system_theme`), palettes `_build_light_palette`/`_build_dark_palette` (`themes.py::_build_light_palette`/`themes.py::_build_dark_palette`), `apply_theme` (`themes.py::apply_theme`) |
| Icons | `icons.py` | themed SVG load `_load_themed_svg` (`icons.py::_load_themed_svg`), `icon` (`icons.py::icon`)/`themed_icon` (`icons.py::themed_icon`), cache `clear_icon_cache` (`icons.py::clear_icon_cache`) |
| Tray | `system_tray.py::SystemTray` | tray icon/menu; `_make_icon` (`system_tray.py::_make_icon`) |
| Notifications | `notifications.py::NotificationManager` | OS notifications (gated by pref) |
| Single instance | `single_instance.py::SingleInstance` | reject a 2nd launch |
| UI loading | `ui/loader.py::UiLoader`, `load_ui_widget` (`ui/loader.py::load_ui_widget`) | load `.ui` resources |

> Strings shown here must be looked up via `i18n.tr` and exist in all 5 locales
> (see [settings.md](settings.md)).
