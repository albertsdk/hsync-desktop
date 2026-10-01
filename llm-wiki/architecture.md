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

## Build & packaging

`compile.sh` exposes the uniform target interface shared with `hsync-client` and
`hsync-bootnode`:

| Target | Output | How |
| ------ | ------ | --- |
| `native` (default) | `dist/<os>-<arch>/hsync-desktop[.exe]` | host PyInstaller onefile; bundles `../hsync-client/dist/<os>-<arch>/hsync` when present |
| `deb` | `dist/deb/hsync-desktop_<ver>_<arch>.deb` | host PyInstaller onedir staged under `/usr/lib/hsync-desktop` + `.desktop` launcher + icons; `Depends: hsync-client` (no client bundled) |
| `deb-all` | `dist/deb/hsync-desktop_<ver>_{amd64,arm64}.deb` | Docker cross-build from `packaging/deb/Dockerfile.builder`; armhf unsupported (no PySide6 armv7 wheels) |
| `rpi` | `dist/rpi/arm64/hsync-desktop` | arm64 onefile built inside an emulated Debian Bookworm container from `packaging/rpi/Dockerfile.builder` |

- Options: `-c/--clean`, `-t/--target` (default `native`), `-v/--version` (also
  `HSYNC_VERSION`), `-h/--help`.
- Native and rpi share the PyInstaller flags and `--add-data` logic
  (`_onefile_pyi_flags` `compile.sh:295`, `_add_data_args` `compile.sh:331`);
  `build_binary` (`compile.sh:373`) and `build_rpi` (`compile.sh:426`) differ
  only in the runner and output path.
- The `deb`/`deb-all` targets share `_onedir_pyi_flags` and stage
  `packaging/deb/` (DEBIAN control + maintainer scripts, `.desktop` entry,
  hicolor icons) with `_finalize_deb_stage`; `_inject_shlib_depends` resolves
  `libc6`/`zlib1g`. Unlike the onefile builds, no client binary is bundled —
  the package declares `Depends: hsync-client` and the app uses
  `/usr/bin/hsync` from PATH.
- **arm64-only rpi**: PySide6 publishes no armv7 Linux wheels, so the Qt GUI
  cannot be built for 32-bit armhf. The `rpi` target produces arm64 only and
  prints an informational note instead of failing; `deb-all` likewise builds
  amd64 + arm64 only.
- `clean_artifacts` (`compile.sh:233`) removes the whole `dist/` tree (all
  platform outputs including `dist/rpi`), `build` and the spec file.
- Docker is required **only** inside `build_rpi` and `build_deb_all`; the
  `native` and `deb` targets never call Docker.

### Distribution & install entry points

HSYNC Desktop ships as a desktop application — there is **no Docker/server
deployment mode**:

| Method | Files |
|---|---|
| `.deb` (amd64/arm64) | `compile.sh -t deb\|deb-all` + `packaging/deb/` (`Depends: hsync-client`, no client bundled) |
| Standalone bundle | `compile.sh` (`native`, bundles the `hsync` client) and `rpi` (arm64) |
| Installer script | `install.sh` — downloads the self-contained bundle and installs it under `~/.local` (no `sudo`, no Docker) |
| From source | `run.sh` — checks the sibling `hsync-common`, creates `../.venv` via Poetry, launches the GUI |
| Release | `.github/workflows/release.yml` publishes the native archives (client bundled), the `.deb` packages and `install.sh`; no container image |
| Docs | `docs/getting-started.md` chooser + one `getting-started-<method>.md`; `docs/configuration.md` is the settings SSOT, `docs/usage.md` the runtime guide |
