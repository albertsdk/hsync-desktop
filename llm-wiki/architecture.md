# HSYNC Desktop — Architecture

A thin Qt (PySide6) front-end over the `hsync` client binary. The GUI owns
**presentation + configuration**; all sync logic lives in the subprocess.

## Component map

| Layer | Code | Responsibility |
| ----- | ---- | -------------- |
| Entry | `main.py::main` | early `--version`/`--help` without Qt, `QT_QPA_PLATFORMTHEME=generic` harden on Linux, app identity (`main.py::_configure_app`: `setDesktopFileName("hsync-desktop")` + window icon so the taskbar binds to the `.desktop`), single-instance guard, theme, i18n, build `MainWindow`, install the SIGINT handler (`main.py::_install_sigint_handler`, Ctrl+C → clean quit), run Qt loop |
| Window | `main_window.py::MainWindow` | menus/toolbar, log view, file panel; wires engine signals → slots |
| File panel | `file_panel/panel.py::FilePanel`, `file_panel/transfer_table.py::FileTransferTable` | live transfer table, detail pane, file actions |
| Engine | `engine.py::HsyncEngine` | spawn/stop the binary, bridge its event stream to Qt signals |
| Settings | `settings/dialog.py::SettingsDialog` + `config.py` | edit + persist config (QSettings) |
| Args | `settings/cli_args.py::build_hsync_args` | translate persisted config → binary CLI flags |
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
   Qt slots  ◄── Signals ◄── _handle_event(UiEventDict)  (engine.py::HsyncEngine._handle_event)
```

1. **Discover binary**: `find_hsync_binary` (`engine.py::find_hsync_binary`), version via
   `get_binary_version` (`engine.py::get_binary_version`), compatibility via
   `is_binary_version_compatible` (`engine.py::is_binary_version_compatible`); at startup the version is resolved
   asynchronously by `BinaryVersionProbe` (`engine.py::BinaryVersionProbe`) and cached in QSettings.
2. **Probe capabilities**: `get_binary_capabilities` (`engine.py::get_binary_capabilities`) →
   `parse_capabilities`; `SettingsDialog` disables unsupported controls (§8).
3. **Build args**: `build_hsync_args` (`settings/cli_args.py::build_hsync_args`) maps every persisted
   setting to the `p2p`/`server` subcommand plus its flags (`--require-pairing`,
   `--allow-deletions`, …).
4. **Spawn**: `HsyncEngine.start` (`engine.py::HsyncEngine.start`) opens pipes, writes secrets,
   launches `QProcess`, and attaches a `QSocketNotifier` to the events FD.
5. **Bridge events**: each JSON-Lines `UiEventName` is mapped to a typed Qt
   `Signal` in `_handle_event` (`engine.py::HsyncEngine._handle_event`); `MainWindow._connect_signals`
   (`main_window.py::MainWindow._connect_signals`) binds them to UI updates.
6. **Control**: start/stop/sync/preview + live commands (set direction,
   bandwidth) sent over the process stdin via `_send_command` (`engine.py::HsyncEngine._send_command`).

## Boundaries

- **No client imports**: the only coupling to the binary is the CLI/flag +
  event-stream + stdin-command contract (ADR 0004). The shared *vocabulary*
  (`UiEventName`, `CapabilitiesDoc`, protocol versions) is imported from
  `hsync_common.protocol.*` — the SSOT, not desktop-local definitions.
- **Threading**: heavy work (directory scans) runs in `QObject` workers
  (`file_panel/workers.py::DirectoryScanWorker`); UI mutations stay on the
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
| `deb` | `dist/deb/hsync-desktop_<ver>_<arch>.deb` | host PyInstaller onedir staged under `/usr/lib/hsync-desktop` + `.desktop` launcher + icons, with the host-arch `hsync` client bundled (self-contained) |
| `deb-all` | `dist/deb/hsync-desktop_<ver>_{amd64,arm64}.deb` | Docker cross-build from `packaging/deb/Dockerfile.builder`; armhf unsupported (no PySide6 armv7 wheels) |
| `rpm` | `dist/rpm/hsync-desktop-<ver>-1.<dist>.<arch>.rpm` | host `.venv` + `rpmbuild`; the same onedir payload staged for `/usr/lib/hsync-desktop` with the host-arch `hsync` client bundled + Qt/X runtime libs (self-contained) |
| `rpm-all` | `dist/rpm/hsync-desktop-<ver>-1.el9.{x86_64,aarch64}.rpm` | Docker cross-build from `packaging/rpm/Dockerfile.builder` (Rocky Linux 9) under `qemu-user` binfmt |
| `appimage` | `dist/appimage/hsync-desktop-<ver>-x86_64.AppImage` | host onefile (client bundled) wrapped in an AppDir and packaged with `appimagetool`; Linux x86_64 only |
| `dmg` | `dist/macos/hsync-desktop-<ver>-darwin-<arch>.dmg` | host onefile `--windowed` (client bundled) as `hsync-desktop.app`; `Info.plist` merged from `packaging/macos/Info.plist`, `.icns` via `sips`/`iconutil`, `.dmg` via `hdiutil`; darwin only |
| `rpi` | `dist/rpi/arm64/hsync-desktop` | arm64 onefile built inside an emulated Debian Bookworm container from `packaging/rpi/Dockerfile.builder` |

- Options: `-c/--clean`, `-t/--target` (default `native`), `-v/--version` (also
  `HSYNC_VERSION`), `-h/--help`.
- Native and rpi share the PyInstaller flags and `--add-data` logic
  (`compile.sh::_onefile_pyi_flags`, `compile.sh::_add_data_args`);
  `build_binary` (`compile.sh::build_binary`) and `build_rpi` (`compile.sh::build_rpi`) differ
  only in the runner and output path.
- The `deb`/`deb-all` targets share `_onedir_pyi_flags` and stage
  `packaging/deb/` (DEBIAN control + maintainer scripts, `.desktop` entry,
  hicolor icons) with `_finalize_deb_stage`; `_inject_shlib_depends` computes the
  `Depends:` line from the bootloader's `dpkg-shlibdeps` (versioned, e.g. `libc6`)
  plus the payload's external libraries (`_compute_runtime_depends`: DT_NEEDED
  sonames not shipped in `_internal`, resolved via `ldconfig`/`dpkg -S`) instead
  of a hand-maintained list. They bundle the `hsync` client (`_add_data_args`), so the
  package is self-contained and declares no `hsync-client` dependency; the
  `deb-all`/`rpm-all` Docker builds compile the per-arch client inside the same
  container (same arch and distro, hence the same glibc).
- **arm64-only rpi**: PySide6 publishes no armv7 Linux wheels, so the Qt GUI
  cannot be built for 32-bit armhf. The `rpi` target produces arm64 only and
  prints an informational note instead of failing; `deb-all` likewise builds
  amd64 + arm64 only.
- The `rpm`/`rpm-all` targets reuse the `deb` onedir payload and `packaging/deb/`
  (`.desktop`, icons) plus `packaging/rpm/` (`.spec`, Rocky 9 builder);
  `_semver_to_rpm`/`_arch_to_rpm` mirror the deb helpers. An RPM erase keeps the
  data and the system user (there is no `purge` equivalent), matching the deb
  `remove` semantics.
- The `appimage` target builds the same onefile bundle as `native` (client
  bundled), assembles an AppDir (`AppRun`, `.desktop`, hicolor icons) and runs
  `appimagetool` (`packaging/appimage/.cache/`, run with
  `APPIMAGE_EXTRACT_AND_RUN`). No `linuxdeploy`/Qt plugin: PyInstaller already
  bundles Qt/Python, and linuxdeploy would bundle the system glibc. x86_64 only.
- The `dmg` target (darwin only) reuses the `native` onefile flags with
  `--windowed` (a real `.app`), patches the generated `Info.plist` by merging
  `packaging/macos/Info.plist` (`_macos_apply_info_plist`), builds the `.icns`
  from the PNG with `sips`/`iconutil`, and wraps the `.app` in a `.dmg`
  (`_macos_create_dmg`). One `.dmg` per host arch; a universal2 build would need
  a `lipo`-merged client. Artifacts are **unsigned** (Gatekeeper workaround in
  `docs/getting-started-macos.md`); signing/notarization hooks are absent by
  design.
- `clean_artifacts` (`compile.sh::clean_artifacts`) removes the whole `dist/` tree (all
  platform outputs including `dist/rpi`), `build` and the spec file.
- Docker is required **only** inside `build_rpi`, `build_deb_all` and
  `build_rpm_all`; the `native`, `deb`, `rpm` and `appimage` targets never call
  Docker.

### Distribution & install entry points

HSYNC Desktop ships as a desktop application — there is **no Docker/server
deployment mode**:

| Method | Files |
|---|---|
| `.deb` (amd64/arm64) | `compile.sh -t deb\|deb-all` + `packaging/deb/` (self-contained: client bundled) |
| `.rpm` (x86_64/aarch64) | `compile.sh -t rpm\|rpm-all` + `packaging/rpm/` (self-contained: client bundled) |
| AppImage (x86_64) | `compile.sh -t appimage` — self-contained onefile with the client bundled |
| macOS `.dmg` (arm64/amd64) | `compile.sh -t dmg` — unsigned `.app` (client bundled) in a `.dmg` |
| Windows installer (x64) | built in CI (Inno Setup) from `packaging/windows/hsync-desktop.iss`; per-user, Start Menu shortcut |
| Standalone bundle | `compile.sh` (`native`, bundles the `hsync` client) and `rpi` (arm64) |
| Installer script | `install.sh` — downloads the self-contained bundle and installs it under `~/.local` (no `sudo`, no Docker) |
| From source | `run.sh` — checks the sibling `hsync-common`, creates `../.venv` via Poetry, launches the GUI |
| Release | `.github/workflows/release.yml` publishes the native archives, the Windows installer, the `.dmg` (macOS), the `.deb`/`.rpm` packages, the AppImage and `install.sh`, plus fixed-name `latest` aliases (RELEASES.md §5.8); no container image |
| Docs | `docs/getting-started.md` chooser + one `getting-started-<method>.md`; `docs/configuration.md` is the settings SSOT, `docs/usage.md` the runtime guide |
