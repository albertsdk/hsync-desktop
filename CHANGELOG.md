# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
