# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Max inbound file size setting**: new *Advanced* spinbox controlling the
  client `--max-inbound-size` flag (absolute cap on a single inbound file,
  `0` = disabled, default 10 GB). Without a desktop-side passthrough, files
  larger than the client default would have been aborted with no way to
  raise the cap from the UI

### Changed
- **Setting/flag rename**: the max inbound file size setting now passes
  `--max-inbound-size` (renamed from `--max-download-size` in the client).
  The QSettings key changed from `sync/max_download_size` to
  `sync/max_inbound_size`. Existing custom values reset to the default
  (10 GB) on upgrade.
- **Delta transfer compatibility**: the desktop GUI is now compatible with
  the delta transfer protocol (rsync-style block sync). No UI changes are
  required — delta transfer is transparent to the user and automatically
  reduces bandwidth for large files with small changes when both peers support
  it. The capability negotiation ensures backward compatibility with older
  clients/servers.

### Changed
- **Deps**: Updated development and transitive dependencies: cffi 2.1.0,
  coverage 7.15.2, filelock 3.31.2, librt 0.13.0, mypy 2.3.0,
  platformdirs 4.10.1, ruff 0.15.22, virtualenv 21.6.1,
  aiofiles 25.1.0 (via hsync-common)

## [1.0.0] — 2025-12-xx

### Added
- Initial release: cross-platform desktop GUI for HSYNC Client (PySide6 / Qt 6)
- Real-time log viewer with scrolling output
- Status panel: connection state, master/client role, bucket, group, peers
- Transfer statistics (files and bytes sent/received)
- File transfer panel with per-file progress, status and ETA
- Start/Stop/Sync controls with local directory selector
- Sync preview/summary dialog before applying changes
- Bandwidth-limit dialog (transfer throttling)
- Desktop push notifications for key events
- Settings dialog organized by category (Connection, Sync, LAN, Output, Appearance)
- Hidden-file controls + `.hsyncignore` editor
- Multi-language UI (EN/IT/DE/ES/FR)
- Light and dark themes
- System tray integration with context menu
- Single-instance lock and splash screen
- Persistent settings and window geometry via QSettings
- Compilable to standalone binary (PyInstaller)
- Subprocess bridge to `hsync-client` via stdin command protocol

[1.0.0]: https://github.com/albertobasso/hsync-desktop/releases/tag/v1.0.0
