# HSYNC Desktop

Cross-platform desktop GUI for HSYNC Client, built with PySide6 (Qt 6).

## Features

- 🖥️ Real-time log viewer with scrolling output
- 📊 Status panel: connection state, master/client role, bucket, group, peers
- 📈 Transfer statistics (files and bytes sent/received)
- ▶️ Start/Stop/Sync controls with local directory selector
- 🔔 Desktop push notifications for key events (configurable)
- ⚙️ Settings dialog organized by category (Connection, Sync, LAN, Output, Appearance)
- 🙈 Hidden-file controls + `.hsyncignore` editor (gitignore-style exclusion patterns)
- 🌙 Light and dark themes
- 📌 System tray integration with context menu
- 💾 Persistent settings and window geometry via QSettings

## Requirements

For building:
- Python ≥3.12, <3.14
- Poetry (for dependency management)

For running:
- The compiled `hsync` binary from [hsync-client](../hsync-client)

## Quick Start

```bash
cd hsync-desktop

# Install dependencies
poetry install

# Run the application
poetry run python -m hsync_desktop
```

## Build

```bash
# Compile hsync-client first (required)
cd ../hsync-client && ./compile.sh && cd ../hsync-desktop

# Install dependencies (first time only)
poetry install

# Compile the desktop binary
./compile.sh
# Binary output: dist/<os>-<arch>/hsync-desktop  (e.g. dist/linux-amd64/hsync-desktop)
```

Both compile scripts detect the current platform automatically using `uname`.
The desktop build looks for the client binary at `../hsync-client/dist/<os>-<arch>/hsync[.exe]`
and bundles it into the resulting executable when found.

### Build Options

```bash
./compile.sh           # Build the binary
./compile.sh --clean   # Clean artifacts and rebuild
./compile.sh --help    # Show help
```

## Configuration

All settings are managed through the GUI Settings dialog and persisted via QSettings.

### Connection

| Setting | Description |
|---------|-------------|
| Server URL | HSYNC server address |
| API Key | Authentication key |
| SSL verification | Skip or use custom CA certificate |
| HTTP Timeout | Request timeout in seconds |

### Sync

| Setting | Description |
|---------|-------------|
| Bucket | Bucket name (required) |
| Continuous | Watch for changes |
| Re-sync interval | Force full sync every N seconds |
| Ignore deletions | Backup mode |
| Compression | Enable/disable transfer compression |

### LAN Mode

| Setting | Description |
|---------|-------------|
| Enable LAN | Peer-to-peer mode without server |
| Group | LAN group name |
| Shared Secret | Authentication key for LAN peers |
| HTTPS | Use encrypted LAN connections |
| Persistent | Stay active waiting for peers |

### Appearance

| Setting | Description |
|---------|-------------|
| Theme | Light or Dark |
| Notifications | Enable/disable desktop push notifications |

## hsync Binary Discovery

The application searches for the `hsync` binary in this order:

1. **Bundled**: `hsync_desktop/bin/hsync[.exe]` (included in compiled builds)
2. **System PATH**: `which hsync`
3. **Sibling project** (development): `../hsync-client/dist/<os>-<arch>/hsync[.exe]`
   — the platform tag (e.g. `linux-amd64`, `darwin-arm64`) is detected at runtime

## Project Structure

```
hsync-desktop/
├── hsync_desktop/
│   ├── __init__.py           # Package version
│   ├── __main__.py           # Module entry point
│   ├── main.py               # Application entry point
│   ├── engine.py             # hsync-client subprocess bridge
│   ├── main_window.py        # Main window UI
│   ├── settings_dialog.py    # Settings dialog with tabs
│   ├── system_tray.py        # System tray icon and menu
│   ├── notifications.py      # Desktop notification manager
│   ├── themes.py             # Light/dark theme management
│   └── resources/            # Icons and assets
├── tests/                    # Test files
├── compile.sh                # Build script (PyInstaller)
├── pyproject.toml            # Project configuration
└── README.md
```

## License

MPL-2.0 - See [LICENSE](../LICENSE) for details.

## Version

1.0.0
