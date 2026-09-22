# HSYNC Desktop — Architecture

A thin Qt (PySide6) front-end over the `hsync` client binary. The GUI owns
**presentation + configuration**; all sync logic lives in the subprocess.

## Component map

| Layer | Code | Responsibility |
| ----- | ---- | -------------- |
| Entry | `main.py:33` (`main`) | single-instance guard, theme, i18n, build `MainWindow`, run Qt loop |
| Window | `main_window.py:99` (`MainWindow`) | menus/toolbar, log view, file panel; wires engine signals → slots |
| File panel | `file_panel/widgets.py:1280` (`FilePanel`), `:339` (`FileTransferTable`) | live transfer table, detail pane, file actions |
| Engine | `engine.py:188` (`HsyncEngine`) | spawn/stop the binary, bridge its event stream to Qt signals |
| Settings | `settings/dialog.py:162` (`SettingsDialog`) + `config.py` | edit + persist config (QSettings) |
| Args | `settings/cli_args.py:62` (`build_hsync_args`) | translate persisted config → binary CLI flags |
| Presentation | `themes.py`, `icons.py`, `i18n.py`, `system_tray.py`, `notifications.py` | look, localization, tray, OS notifications |

## Runtime flow

```
SettingsDialog ──save──► QSettings (secrets Fernet-encrypted, crypto.py)
        │
MainWindow ──start──► build_hsync_args(local_path) ──► HsyncEngine.start(args)
        │                                                   │
        │                          QProcess(hsync binary) ◄─┘
        │                            │  secrets via --api-key-fd/--p2p-key-fd pipes
        │                            │  events via --events-json-fd (JSON-Lines)
        ▼                            ▼
   Qt slots  ◄── Signals ◄── _handle_event(UiEventDict)  (engine.py:572)
```

1. **Discover binary**: `find_hsync_binary` (`engine.py:145`), version via
   `get_binary_version` (`:176`), compatibility via
   `is_binary_version_compatible` (`:225`); at startup the version is resolved
   asynchronously by `BinaryVersionProbe` (`:324`) and cached in QSettings.
2. **Probe capabilities**: `get_binary_capabilities` (`:194`) →
   `parse_capabilities`; `SettingsDialog` disables unsupported controls (§8).
3. **Build args**: `build_hsync_args` (`cli_args.py:62`) maps every persisted
   setting to the `p2p`/`server` subcommand plus its flags (`--require-pairing`,
   `--yes`, …).
4. **Spawn**: `HsyncEngine.start` (`engine.py:282`) opens pipes, writes secrets,
   launches `QProcess`, and attaches a `QSocketNotifier` to the events FD.
5. **Bridge events**: each JSON-Lines `UiEventName` is mapped to a typed Qt
   `Signal` in `_handle_event` (`:572`); `MainWindow._connect_signals`
   (`main_window.py:599`) binds them to UI updates.
6. **Control**: start/stop/sync/preview + live commands (set direction,
   bandwidth) sent over the process stdin via `_send_command` (`engine.py:459`).

## Boundaries

- **No client imports**: the only coupling to the binary is the CLI/flag +
  event-stream + stdin-command contract (ADR 0004). The shared *vocabulary*
  (`UiEventName`, `CapabilitiesDoc`, protocol versions) is imported from
  `hsync_common.protocol.*` — the SSOT, not desktop-local definitions.
- **Threading**: heavy work (directory scans) runs in `QObject` workers
  (`file_panel/workers.py:27`, `DirectoryScanWorker`); UI mutations stay on the
  Qt main thread, fed by signals.

See [modules/engine.md](modules/engine.md) for the subprocess + event bridge,
[modules/ui.md](modules/ui.md) for widgets, and
[modules/settings.md](modules/settings.md) for config → args.
