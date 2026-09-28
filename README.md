<p align="center">
  <img src="docs/assets/hsync-logo-horizontal.svg" alt="HSYNC logo" width="300">
</p>

# HSYNC Desktop

**HSYNC Desktop** is the graphical application for Windows, macOS, and Linux. It
gives you a visual interface to control the HSYNC Client: start or stop sync,
monitor transfer progress, adjust settings, and get desktop notifications — all
without touching the command line.

> The desktop drives the `hsync` client as a subprocess over an explicit,
> versioned contract. See the
> [Architecture Decision Records](https://github.com/albertsdk/hsync-common/blob/main/docs/internal/adr/README.md) — in
> particular the [desktop ↔ client subprocess contract](https://github.com/albertsdk/hsync-common/blob/main/docs/internal/adr/0004-desktop-subprocess-contract.md).

> 👉 **Operational Advisory:** As with any automated filesystem mutation utility, administrators are strongly advised to maintain validated, independent backups prior to initial deployment in production environments.

---

[![License: MPL 2.0](https://img.shields.io/badge/License-MPL_2.0-brightgreen.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Qt 6](https://img.shields.io/badge/Qt-6-41CD52.svg)](https://www.qt.io/)

**Quick navigation:**
- **New to HSYNC?** Start with the [Features](#features) overview above and [Quick Start](#quick-start)
- **Ready to build from source?** Jump to [Build](#build)
- **Want to contribute?** See [Contributing](CONTRIBUTING.md)
- **Looking for detailed documentation?** Navigate to [docs/README.md](docs/README.md)

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
- ⚙️ Settings dialog organized by category (Sync, Server Mode, P2P Mode, Log, Appearance)
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
- The compiled `hsync` binary from [hsync-client](https://github.com/albertsdk/hsync-client)

## Quick Start

```bash
cd hsync-desktop

# Install dependencies
poetry install

# Run the application
poetry run python -m hsync_desktop
```

## Build

### Native (host OS/arch)

```bash
# Compile hsync-client first (required for a self-contained bundle)
cd ../hsync-client && ./compile.sh && cd ../hsync-desktop

# Install dependencies (first time only)
poetry install

# Compile the desktop binary
./compile.sh
# Binary output: dist/<os>-<arch>/hsync-desktop  (e.g. dist/linux-amd64/hsync-desktop)
```

Both compile scripts detect the current platform automatically using `uname`.
The desktop build looks for the client binary at
`../hsync-client/dist/<os>-<arch>/hsync[.exe]` and bundles it into the resulting
executable when found; when it is missing the build warns and the app falls back
to the `hsync` binary on `PATH` at runtime.

### Raspberry Pi OS (64-bit)

```bash
./compile.sh --target rpi
# Binary output: dist/rpi/arm64/hsync-desktop  (Raspberry Pi OS 64-bit / aarch64)
```

The `rpi` target cross-builds the arm64 onefile binary inside an emulated Debian
Bookworm container, so it requires Docker with `qemu-user-static` (binfmt)
configured on the host. To bundle the client as well, build its arm64 Raspberry
Pi binary first with `cd ../hsync-client && ./compile.sh --target rpi`; the
desktop build looks for it at `../hsync-client/dist/rpi/arm64/hsync`.

> **32-bit armhf is not supported for the GUI.** PySide6 publishes no armv7
> Linux wheels, so the Qt desktop cannot be built for 32-bit Raspberry Pi OS;
> only the 64-bit (arm64) target is produced.

### Build Options

```bash
./compile.sh                    # Native host build (default)
./compile.sh --clean            # Clean artifacts and rebuild
./compile.sh --target native    # Explicit native build
./compile.sh --target rpi       # Raspberry Pi OS 64-bit (arm64)
./compile.sh --version 1.2.3    # Override the reported version
./compile.sh --help             # Show help
```

The version can also be set through the `HSYNC_VERSION` environment variable.

## Configuration

All settings are managed through the GUI Settings dialog and persisted via QSettings.

### Server Mode

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

### p2p Mode

| Setting | Description |
|---------|-------------|
| Enable p2p | Peer-to-peer mode without a server |
| Force master / Never master | Control master election for this device |
| Require pairing | Only sync with explicitly paired peers |
| p2p key | Shared secret for the p2p group |
| Bootnode | Hostname of an optional `boot/1` node for cross-network discovery |
| Bootnode fingerprint / Trust on first use | Pin the bootnode certificate (TOFU) |
| Map port with UPnP | Map the master port so peers reached through a bootnode can dial it |
| NTP servers | SNTP servers for p2p clock-offset measurement |

### Log

| Setting | Description |
|---------|-------------|
| Verbose output | Enable verbose (debug-level) logging |
| Quiet mode | Suppress non-warning output |
| Log file | Path to the log file |
| Show log panel | Toggle the in-app log viewer |

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

### Associated Ecosystem Components

- [HSYNC Client](https://github.com/albertsdk/hsync-client/blob/main/README.md) - Sync client (Server Mode and p2p Mode)
- [HSYNC Server](https://github.com/albertsdk/hsync-server/blob/main/README.md) - Central synchronization server (Server Mode)
- [HSYNC Desktop](https://github.com/albertsdk/hsync-desktop/blob/main/docs/README.md) — Desktop client GUI front-end *(in development)*.
- [HSYNC Android](https://github.com/albertsdk/hsync-android/blob/main/docs/README.md) — Android client app *(in development)*.
- [HSYNC Bootnode](https://github.com/albertsdk/hsync-bootnode/blob/main/README.md) — Optional Internet discovery node for P2P topologies; exposed as the p2p *Bootnode* setting *(v1 — stable)*.

> **Note:** The desktop GUI (`HSYNC Desktop`) and the Android app (`HSYNC Android`)
> are still under active development and are not yet ready for production use.

## Security

To report a vulnerability, please use GitHub's **Private Vulnerability Reporting**:

👉 **[Report a vulnerability](https://github.com/albertsdk/hsync-desktop/security/advisories/new)**

See our [Security Policy](SECURITY.md) for supported versions and hardening
recommendations.

## A note from the maintainer

HSYNC is a passion project started by Alberto Basso. It is built in spare time,
with love. Please remember this when you interact with the project: everyone
involved is doing our best to build something great together, but it is not a
paid, full-time job for any of us.

## Disclaimer

> [!WARNING]
> **HSYNC manipulates files and directories** — it creates, overwrites, moves, and deletes data.
> Misconfiguration, software defects, or other unforeseen conditions may lead to **data loss or
> corruption**. **Use at your own risk and always keep verified, independent backups.**

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NONINFRINGEMENT. Although the author has implemented reasonable safety measures, IN NO EVENT SHALL THE AUTHOR OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY — including, without limitation, any direct, indirect, incidental, special, exemplary, or consequential damages, loss of data, or business interruption — WHETHER IN AN ACTION OF CONTRACT, TORT, OR OTHERWISE, ARISING FROM, OUT OF, OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

This disclaimer supplements, and does not replace, Sections 6 ("Disclaimer of Warranty") and 7 ("Limitation of Liability") of the [Mozilla Public License 2.0](LICENSE), which govern this software.
