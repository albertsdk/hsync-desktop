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
(`:615`), `file_progress`/`file_renamed` (`:616`/`:617`). File-action menu slots:
open/open-with/copy-to/rename/trash/properties (`:548`–`:573`).

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
