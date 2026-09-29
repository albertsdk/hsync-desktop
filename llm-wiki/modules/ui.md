# HSYNC Desktop — UI (window, panels, presentation)

Qt widgets that render engine state. All UI mutation stays on the main thread,
driven by `HsyncEngine` signals (see [engine.md](engine.md)).

## main_window.py — MainWindow

| Symbol | Line | Role |
| ------ | ---- | ---- |
| `MainWindow` | `main_window.py:99` | top-level window; owns engine + tray |
| `_load_ui` | `:138` | build/compose the central UI |
| `_create_menu_bar` | `:337` | menus + actions (start/stop/refresh/direction/file ops/help) |
| `_connect_signals` | `:599` | bind every engine `Signal` to a slot |
| `_apply_translations` | `:291` | re-translate on language change |
| `_update_menu_state` | `:478` | enable/disable actions by run state |

Engine→slot wiring (in `_connect_signals`, `:599`+): `log_received→_append_log`
(`:607`), `status_changed→_on_status` (`:608`), `peers_changed`/`master_changed`
(`:609`/`:610`), `file_transferred→_on_file_transferred` (`:613`),
`transfer_failed→_on_transfer_failed` (`:614`), `sync_paused→_on_sync_paused`
(`:615`), `file_progress`/`file_renamed` (`:616`/`:617`),
`pairing_needed→_on_pairing_needed` / `fingerprint_changed→_on_fingerprint_changed`
(`:635`/`:636`). File-action menu slots: open/open-with/copy-to/rename/trash/
properties (`:548`–`:573`).

### Trust refusal dialogs (SSH-style, no terminal)

`MainWindow` answers the client's trust refusals with dialogs instead of a
terminal (the client keeps retrying on the mDNS path, so the handlers dedupe):

- `_on_pairing_needed` / `_on_fingerprint_changed` (`main_window.py:1075`/`:1109`)
  route by `scope`: `master` → `add_peer_pin`/`remove_peer_pin`; `bootnode`/`server`
  → the helpers returned by `_host_trust_actions` (`:1028`) (`add_bootnode_trust`/
  `remove_bootnode_trust` or `add_server_trust`/`remove_server_trust`). Dedupe is
  `_trust_prompted` `dict[(scope, identity)] → last fingerprint` (`:136`) via
  `_should_prompt_trust` (`:998`), cleared on start/stop (`:1642`/`:1809`): a
  repeated refusal for the same fingerprint reuses no dialog, a changed one
  re-prompts. A dismissed or ignored dialog never touches the stored pin (the
  host branch acts only on the explicit Trust/Forget buttons).
- `_maybe_offer_restart` (`:1043`) offers to restart a stopped sync after a
  bootnode/server pin change (those failures are fatal; mDNS refusals are not).
- `_ensure_bootnode_trust` (`:1701`) and `_ensure_server_trust` (`:1730`) are the
  start pre-flights, both delegating to `_confirm_host_trust` (`:1757`): skip
  unless the mode/policy/URL apply; skip when the known-hosts store already holds
  `host:port`; else `fetch_*_fingerprint` → confirm → `add_*_trust`. They write
  the shared known-hosts stores (no GUI-only fingerprint settings).

## trusted_keys.py — TrustedKeysDialog

`TrustedKeysDialog` (`trusted_keys.py:159`) lists and edits all three stores via
the `engine` subprocess helpers (never the store files directly): three tabs
(bootnodes / servers / peers), each a `QTableWidget` + Add/Remove/Refresh. The
bootnode/server tabs share `_HostAddDialog` and `_build_host_tab` (host:port
stores); *Add* supports "read from node" or manual entry. Peer *Add* pre-fills
the bucket from `sync/bucket`. The peers tab shows
`trusted_keys.capability_missing` when the binary lacks the `trust` subcommand
(`supports_peer_trust`).

## file_panel/ — live transfer view

| Symbol | Line | Role |
| ------ | ---- | ---- |
| `FilePanel` | `widgets.py:1280` | container: table + detail pane + overlay |
| `FileTransferTable` | `widgets.py:339` | per-file rows (status/progress/size) |
| `FileDetailPanel` | `widgets.py:228` | selected-file metadata pane |
| `ProgressBarDelegate` / `CenteredIconDelegate` | `widgets.py:87` / `:108` | cell rendering |
| `LoadingOverlay` | `widgets.py:159` | busy overlay during scans |
| `_confirm_dialog` | `widgets.py:129` | reusable confirm prompt |
| `DirectoryScanWorker` | `workers.py:27` | off-thread local tree scan |
| `_classify_file` / `format_mtime` | `utils.py:260` / `:274` | type/icon + mtime formatting |

Models for the panel live in `file_panel/models.py` — see
[data-models.md](../data-models.md).

## Presentation helpers

| Concern | Code | Notes |
| ------- | ---- | ----- |
| Theme | `themes.py` | `detect_system_theme:23`, palettes `_build_light/_dark_palette:74`/`:97`, `apply_theme:257` |
| Icons | `icons.py` | themed SVG load `_load_themed_svg:46`, `icon:157`/`themed_icon:176`, cache `clear_icon_cache:229` |
| Tray | `system_tray.py:42` (`SystemTray`) | tray icon/menu; `_make_icon:24` |
| Notifications | `notifications.py:27` (`NotificationManager`) | OS notifications (gated by pref) |
| Single instance | `single_instance.py:21` (`SingleInstance`) | reject a 2nd launch |
| UI loading | `ui/loader.py:60` (`UiLoader`), `load_ui_widget:80` | load `.ui` resources |

> Strings shown here must be looked up via `i18n.tr` and exist in all 5 locales
> (see [settings.md](settings.md)).
