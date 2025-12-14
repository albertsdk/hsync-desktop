# HSYNC Desktop

**HSYNC Desktop** is the graphical application for Windows, macOS, and Linux. It
gives you a visual interface to control the HSYNC Client: start or stop sync,
monitor transfer progress, adjust settings, and get desktop notifications — all
without touching the command line.

> The desktop drives the `hsync` client as a subprocess over an explicit,
> versioned contract. See the
> [Architecture Decision Records](https://github.com/albertobasso/hsync-common/blob/main/docs/adr/README.md) — in
> particular the [desktop ↔ client subprocess contract](https://github.com/albertobasso/hsync-common/blob/main/docs/adr/0004-desktop-subprocess-contract.md).

> [!WARNING]
> **HSYNC manipulates files and directories** — it creates, overwrites, moves, and deletes data.
> Misconfiguration, software defects, or other unforeseen conditions may lead to **data loss or
> corruption**. **Use at your own risk and always keep verified, independent backups.**
> The software is provided "as is", without warranty of any kind — see the full
> [Disclaimer](#disclaimer) and [License](#license) below.

---

**Quick navigation:**
- **New to HSync?** Start with the [Features](#features) overview above and [Quick Start](#quick-start)
- **Ready to build from source?** Jump to [Build](#build)
- **Want to contribute?** See [Contributing](CONTRIBUTING.md)
- **Looking for detailed documentation?** Navigate to [docs/README.md](docs/README.md)

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Build](#build)
- [Configuration](#configuration)
- [hsync Binary Discovery](#hsync-binary-discovery)
- [Project Structure](#project-structure)
- [Version](#version)
- [License](#license)
- [Disclaimer](#disclaimer)

---

## Features

- 🖥️ Real-time log viewer with scrolling output
- 📊 Status panel: connection state, master/client role, bucket, group, peers
- 📈 Transfer statistics (files and bytes sent/received)
- 📂 File transfer panel with per-file progress, status and ETA
- ▶️ Start/Stop/Sync controls with local directory selector
- 👀 Sync preview/summary dialog before applying changes
- 🚦 Bandwidth-limit dialog (transfer throttling)
- 🔔 Desktop push notifications for key events (configurable)
- ⚙️ Settings dialog organized by category (Connection, Sync, LAN, Output, Appearance)
- 🙈 Hidden-file controls + `.hsyncignore` editor (gitignore-style exclusion patterns)
- 🌍 Multi-language UI (EN/IT/DE/ES/FR)
- 🌙 Light and dark themes
- 📌 System tray integration with context menu
- 🔒 Single-instance lock and splash screen on startup
- 💾 Persistent settings and window geometry via QSettings

## Requirements

For building:
- Python ≥3.12, <3.15
- Poetry (for dependency management)

For running:
- The compiled `hsync` binary from [hsync-client](https://github.com/albertobasso/hsync-client)

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
| Delta transfer | Rsync-style block sync for large files (enabled by default) |

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
│   ├── settings_dialog.py    # Settings dialog (delegates to settings/)
│   ├── settings/             # Settings dialog, CLI args, validators
│   ├── file_panel/           # File transfer panel (models, widgets, workers)
│   ├── widgets/              # Custom widgets (progress bar, toggle switch)
│   ├── bandwidth_dialog.py   # Bandwidth-limit dialog
│   ├── preview_summary_dialog.py # Sync preview/summary dialog
│   ├── splash_screen.py      # Startup splash screen
│   ├── single_instance.py    # Single-instance lock
│   ├── system_tray.py        # System tray icon and menu
│   ├── notifications.py      # Desktop notification manager
│   ├── themes.py             # Light/dark theme management
│   ├── i18n.py               # Translation helpers
│   ├── locales/              # Translations (en, it, de, es, fr)
│   ├── config.py             # Settings persistence (QSettings)
│   ├── crypto.py             # Secret encryption helpers
│   ├── icons.py / utils.py   # Icon and utility helpers
│   ├── ui/                   # Qt Designer .ui files + loader
│   ├── bin/                  # Bundled hsync binary (compiled builds)
│   └── resources/            # Icons and assets
├── tests/                    # Test files
├── compile.sh                # Build script (PyInstaller)
├── pyproject.toml            # Project configuration
└── README.md
```

## Version

1.0.0

## License

[Mozilla Public License 2.0](LICENSE)

## Disclaimer

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NONINFRINGEMENT. Although the author has implemented reasonable safety measures, IN NO EVENT SHALL THE AUTHOR OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY — including, without limitation, any direct, indirect, incidental, special, exemplary, or consequential damages, loss of data, or business interruption — WHETHER IN AN ACTION OF CONTRACT, TORT, OR OTHERWISE, ARISING FROM, OUT OF, OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

This disclaimer supplements, and does not replace, Sections 6 ("Disclaimer of Warranty") and 7 ("Limitation of Liability") of the [Mozilla Public License 2.0](LICENSE), which govern this software.
