# HSYNC Desktop — Architecture

A thin Qt (PySide6) front-end over the `hsync` client binary. The GUI owns
**presentation + configuration**; all sync logic lives in the subprocess.

## Component map

| Layer | Code | Responsibility |
| ----- | ---- | -------------- |
| Entry | `main.py::main` | early `--version`/`--help` without Qt, `QT_QPA_PLATFORMTHEME=generic` harden on Linux (the GTK3 theme crashes against the bundled GLib), host font resolution (`fonts.py::apply_system_fonts`, applied right after the `QApplication`), app identity (`main.py::_configure_app`: `setDesktopFileName("hsync-desktop")` + window icon so the taskbar binds to the `.desktop`), `--minimized` start-in-tray (`main.py::_should_start_minimized`), single-instance guard, theme, i18n, build `MainWindow`, install the SIGINT handler (`main.py::_install_sigint_handler`, Ctrl+C → clean quit), run Qt loop |
| Window | `main_window/window.py::MainWindow` | menus/toolbar, log view, file panel; wires engine signals → slots |
| File panel | `file_panel/panel.py::FilePanel`, `file_panel/transfer_table.py::FileTransferModel` + `file_panel/transfer_table.py::FileTransferTable` | live transfer table (model/view), detail pane, file actions |
| Engine | `engine/process.py::HsyncEngine` | spawn/stop the binary, bridge its event stream to Qt signals |
| Settings | `settings/dialog.py::SettingsDialog` + `config.py` | edit + persist config (QSettings) |
| Args | `settings/cli_args.py::build_hsync_args` | translate persisted config → binary CLI flags |
| Presentation | `themes.py`, `fonts.py`, `icons.py`, `i18n.py`, `system_tray.py`, `notifications.py` | look, host fonts, localization, tray, OS notifications |
| Startup | `autostart.py` | launch-at-login entry (XDG / LaunchAgent / Windows `Run`), toggled from the General tab |

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
   Qt slots  ◄── Signals ◄── _handle_event(UiEventDict)  (engine/process.py::HsyncEngine._handle_event)
```

1. **Discover binary**: `find_hsync_binary` (`engine/cli.py::find_hsync_binary`), version via
   `get_binary_version` (`engine/cli.py::get_binary_version`), compatibility via
   `is_binary_version_compatible` (`engine/cli.py::is_binary_version_compatible`); at startup the version is resolved
   asynchronously by `BinaryVersionProbe` (`engine/cli.py::BinaryVersionProbe`) and cached in QSettings.
2. **Probe capabilities**: `get_binary_capabilities` (`engine/cli.py::get_binary_capabilities`) →
   `parse_capabilities`; `SettingsDialog` disables unsupported controls (§8).
3. **Build args**: `build_hsync_args` (`settings/cli_args.py::build_hsync_args`) maps every persisted
   setting to the `p2p`/`server` subcommand plus its flags (`--p2p-trust`,
   `--allow-deletions`, …).
4. **Spawn**: `HsyncEngine.start` (`engine/process.py::HsyncEngine.start`) opens pipes, writes secrets,
   launches `QProcess`, and attaches a `QSocketNotifier` to the events FD.
5. **Bridge events**: each JSON-Lines `UiEventName` is mapped to a typed Qt
   `Signal` in `_handle_event` (`engine/process.py::HsyncEngine._handle_event`); `MainWindow._connect_signals`
   (`main_window/window.py::MainWindow._connect_signals`) binds them to UI updates.
6. **Control**: start/stop/sync/preview + live commands (set direction,
   bandwidth) sent over the process stdin via `_send_command` (`engine/process.py::HsyncEngine._send_command`).

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
| `deb-all` | `dist/deb/hsync-desktop_<ver>_{amd64,arm64}.deb` | Docker cross-build from `packaging/deb/Dockerfile.builder` with a per-arch base (amd64: `python:3.12-bookworm`, glibc 2.36; arm64: `python:3.12-trixie`, glibc 2.41, required by PySide6's `manylinux_2_39` aarch64 wheel); armhf unsupported (no PySide6 armv7 wheels) |
| `rpm` | `dist/rpm/hsync-desktop-<ver>-1.<dist>.<arch>.rpm` | host `.venv` + `rpmbuild`; the same onedir payload staged for `/usr/lib/hsync-desktop` with the host-arch `hsync` client bundled + Qt/X runtime libs (self-contained) |
| `rpm-all` | `dist/rpm/hsync-desktop-<ver>-1.el9.x86_64.rpm` and `...-1.el10.aarch64.rpm` | Docker cross-build from `packaging/rpm/Dockerfile.builder` under `qemu-user` binfmt with a per-arch base (x86_64: `rockylinux:9`, glibc 2.34, hence `el9`; aarch64: `almalinux:10`, glibc 2.39, hence `el10`, required by PySide6's `manylinux_2_39` aarch64 wheel) |
| `appimage` | `dist/appimage/hsync-desktop-<ver>-x86_64.AppImage` | host onefile (client bundled) wrapped in an AppDir and packaged with `appimagetool`; Linux x86_64 only |
| `dmg` | `dist/macos/hsync-desktop-<ver>-darwin-<arch>.dmg` | host onefile `--windowed` (client bundled) as `hsync-desktop.app`; `Info.plist` merged from `packaging/macos/Info.plist`, `.icns` via `sips`/`iconutil`, `.dmg` via `hdiutil`; darwin only |
| `rpi` | `dist/rpi/arm64/hsync-desktop` | arm64 onefile built inside an emulated Debian Bookworm container from `packaging/rpi/Dockerfile.builder` |
| `windows` | `dist/windows/hsync-desktop-<ver>-windows-amd64-setup.exe` + `dist/windows/hsync-desktop-<ver>-windows-amd64.zip` | host PyInstaller onefile (client bundled) + Inno Setup installer (`ISCC`) + portable zip; the installer refuses Windows older than 10 1809 and Arm64 (`packaging/windows/hsync-desktop.iss`); the Qt runtime needs the ICU library shipped with Windows (no Wine/CrossOver support) |

- Options: `-c/--clean`, `-t/--target` (default `native`), `-v/--version` (also
  `HSYNC_VERSION`), `-h/--help`.
- Native and rpi share the PyInstaller flags and `--add-data` logic
  (`compile.sh::_onefile_pyi_flags`, `compile.sh::_add_data_args`);
  `build_binary` (`compile.sh::build_binary`) and `build_rpi` (`compile.sh::build_rpi`) differ
  only in the runner and output path.
- The `deb`/`deb-all` targets share `_onedir_pyi_flags` and stage
  `packaging/deb/` (DEBIAN control + maintainer scripts, `.desktop` entry,
  hicolor icons) with `_finalize_deb_stage`;
  `packaging/deb/deb-depends.sh::_inject_shlib_depends` computes the `Depends:`
  line from the bootloader's `dpkg-shlibdeps` (versioned, e.g. `libc6`) plus the
  payload's external libraries
  (`packaging/deb/deb-depends.sh::_compute_runtime_depends`: DT_NEEDED sonames
  not shipped in `_internal`, resolved via `ldconfig`/`dpkg -S`) instead of a
  hand-maintained list. `deb-all` runs that same helper inside the target
  container, whose binutils/ldconfig/dpkg match the payload's architecture and
  distro. They bundle the `hsync` client (`_add_data_args`), so the
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
- **Snap** (`snap/snapcraft.yaml`): wraps the prebuilt Linux onefile (client
  bundled) on `base: core24` with `confinement: classic`, `amd64` + `arm64`.
  The release workflow pins the Linux builds to Ubuntu 24.04 and asserts no
  required GLIBC symbol exceeds 2.39 (the onefile carries no glibc; the base
  supplies it). `snap/gui/` carries the launcher/icon and `snap/payload/` is the
  CI staging point. Snapcraft resolves `apps.<app>.desktop` inside `snap/` (the
  value omits the prefix) but the top-level `icon` and the part `source` from
  the project root; the release workflow pins the build to `9.x/stable` because
  those bases changed in earlier majors, and `tests/test_snap_packaging.py`
  guards them. Publishing goes to the Snap Store `edge` (manual promotion,
  gated by the one-time classic review) and the `.snap` files are attached to the
  GitHub release. `autostart.py::_snap_launch_command` writes
  `snap run hsync-desktop` so the login entry survives snap refreshes.
- `clean_artifacts` (`compile.sh::clean_artifacts`) removes the whole `dist/` tree (all
  platform outputs including `dist/rpi`), `build` and the spec file.
- The `windows` target (Windows x64 only) builds the same onefile bundle as
  `native` (client bundled) into `dist/windows-amd64/`, renders
  `packaging/windows/icon.ico` from the app PNG with ImageMagick (`magick`/
  `convert`), runs the Inno Setup compiler (`ISCC`, auto-detected or via `$ISCC`)
  on `packaging/windows/hsync-desktop.iss` for the per-user installer, and
  assembles a portable `.zip` with `shutil.make_archive` (no external `zip`/`7z`
  assumed). Both artifacts are unsigned (SmartScreen warns on first run); the
  installer is x64-only (`ArchitecturesAllowed=x64compatible`).
- Docker is required **only** inside `build_rpi`, `build_deb_all` and
  `build_rpm_all`; the `native`, `deb`, `rpm`, `appimage` and `windows` targets
  never call Docker.

### Distribution & install entry points

HSYNC Desktop ships as a desktop application — there is **no Docker/server
deployment mode**:

| Method | Files |
|---|---|
| `.deb` (amd64/arm64) | `compile.sh -t deb\|deb-all` + `packaging/deb/` (self-contained: client bundled) |
| `.rpm` (x86_64/aarch64) | `compile.sh -t rpm\|rpm-all` + `packaging/rpm/` (self-contained: client bundled) |
| AppImage (x86_64) | `compile.sh -t appimage` — self-contained onefile with the client bundled |
| macOS `.dmg` (arm64/amd64) | `compile.sh -t dmg` — unsigned `.app` (client bundled) in a `.dmg` |
| Windows installer (x64) | `compile.sh -t windows` — per-user Inno Setup installer (`packaging/windows/hsync-desktop.iss`) plus a portable `.zip`; self-contained (client bundled) |
| Standalone bundle | `compile.sh` (`native`, bundles the `hsync` client) and `rpi` (arm64) |
| Installer script | `install.sh` — downloads the self-contained bundle and installs it under `~/.local` (no `sudo`, no Docker) |
| From source | `run.sh` — checks the sibling `hsync-common`, creates `../.venv` via Poetry, launches the GUI |
| Release | `.github/workflows/release.yml` publishes the native archives, the Windows installer, the `.dmg` (macOS), the `.deb`/`.rpm` packages, the AppImage and `install.sh`, plus fixed-name `latest` aliases (RELEASES.md §5.8); no container image |
| Docs | `docs/getting-started.md` chooser + one `getting-started-<method>.md`; `docs/README.md` the journey index; `docs/configuration.md` the settings SSOT; `docs/sync-basics.md`/`docs/file-list.md`/`docs/warnings.md`/`docs/secrets.md`/`docs/reset-sync-state.md` the runtime guides; `docs/choose-*.md` the decision guides; `docs/concepts.md` the GUI vocabulary; `docs/troubleshooting.md` the symptom guide |
