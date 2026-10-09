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

[![License: BSD 3-Clause](https://img.shields.io/badge/License-BSD_3--Clause-brightgreen.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/albertsdk/hsync-desktop)](https://github.com/albertsdk/hsync-desktop/releases/latest)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Qt 6](https://img.shields.io/badge/Qt-6-41CD52.svg)](https://www.qt.io/)

**Quick navigation:**
- **New to HSYNC?** Start with the [What you can do](#what-you-can-do-with-hsync-desktop) overview and [Getting started](#getting-started)
- **Configuring the app?** See the [Configuration Reference](docs/configuration.md)
- **Want to contribute?** See [Contributing](CONTRIBUTING.md)
- **Looking for detailed documentation?** Navigate to [docs/README.md](docs/README.md)

---

## What you can do with HSYNC Desktop

...basically the same things as [HSYNC Client](https://github.com/albertsdk/hsync-client/blob/main/README.md), but with this GUI you also have:

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

## Privacy & security

The desktop app drives the `hsync` client, so it inherits its security model:
TLS on every transport, a stable cryptographic device identity, trust-on-first-
use fingerprint pinning, and no telemetry. Runs on Windows, macOS and Linux —
see the [Getting Started](docs/getting-started.md) chooser.

## Requirements

For building:
- Python ≥3.12, <3.15
- Poetry (for dependency management)

For running:
- The compiled `hsync` binary from [hsync-client](https://github.com/albertsdk/hsync-client),
  bundled in the standalone builds or installed as the `hsync-client` package

## Getting started

HSYNC Desktop installs with one command, as a standalone download, as a `.deb`,
or from source. It is a **desktop application only** — there is no Docker or
server mode. Pick one method in the [Getting Started](docs/getting-started.md)
chooser:

- [Installer script](docs/getting-started-script.md) — one `curl` command (Linux/macOS);
- [Standalone binary](docs/getting-started-binary.md) — download and extract;
- [Debian package](docs/getting-started-deb.md) — system package for Debian/Ubuntu;
- [RPM package](docs/getting-started-rpm.md) — system package for RHEL/Rocky/Alma/Fedora;
- [AppImage](docs/getting-started-appimage.md) — portable Linux x86_64 file, no install;
- [macOS .dmg](docs/getting-started-macos.md) — Apple silicon or Intel;
- [Windows installer](docs/getting-started-windows.md) — per-user `.exe` setup;
- [From source](docs/getting-started-source.md) — clone and run.

Then configure a connection in the [Configuration Reference](docs/configuration.md)
and run a sync with the [Usage Guide](docs/usage.md).

## Associated Ecosystem Components

The other components of the HSYNC ecosystem:

- [HSYNC Main](https://github.com/albertsdk/hsync/blob/main/README.md) — Umbrella repository and project overview.
- [HSYNC Common](https://github.com/albertsdk/hsync-common/blob/main/README.md) — Shared library: data models, protocol, delta transfer, hashing.
- [HSYNC Server](https://github.com/albertsdk/hsync-server/blob/main/README.md) — Central sync hub: REST API, WebSocket relay, file storage.
- [HSYNC Client](https://github.com/albertsdk/hsync-client/blob/main/README.md) — CLI client: Server Mode and p2p Mode.
- [HSYNC Android](https://github.com/albertsdk/hsync-android/blob/main/README.md) — Android client app. *(in development)*
- [HSYNC Bootnode](https://github.com/albertsdk/hsync-bootnode/blob/main/README.md) — Optional Internet discovery node for P2P (`boot/1`, no-log, RAM-only).

## Security

To report a vulnerability, please use GitHub's **Private Vulnerability Reporting**:

👉 **[Report a vulnerability](https://github.com/albertsdk/hsync-desktop/security/advisories/new)**

See our [Security Policy](SECURITY.md) for supported versions and hardening
recommendations.

## 🙋‍♂️ A note from the maintainer

This project was born out of the need for a system capable of replicating the contents of a folder from a PC or Android device to a NAS, primarily for backup purposes. There were already several solutions available for this purpose, but I could not find one that met all the requirements I ultimately needed. This led to the somewhat questionable idea of developing one from scratch and, in the process, gaining a deeper understanding of various programming languages, algorithms, frameworks, and so on.

Originally conceived as a hobby project, although it has been under constant development ever since, I believe I can now say that it has evolved to the point where its capabilities are comparable to those of commercial products, while also offering some distinctive features. As such, it could potentially be deployed in a variety of production environments as well.

HSYNC is a passion project developed in my spare time, currently primarily led by me. Please remember this when you interact with the project: everyone involved is doing our best to build something great together, but it is not a paid, full-time job for any of us.

## Disclaimer

> [!WARNING]
> **HSYNC manipulates files and directories** — it creates, overwrites, moves, and deletes data.
> Misconfiguration, software defects, or other unforeseen conditions may lead to **data loss or
> corruption**. **Use at your own risk and always keep verified, independent backups.**

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NONINFRINGEMENT. Although the author has implemented reasonable safety measures, IN NO EVENT SHALL THE AUTHOR OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY — including, without limitation, any direct, indirect, incidental, special, exemplary, or consequential damages, loss of data, or business interruption — WHETHER IN AN ACTION OF CONTRACT, TORT, OR OTHERWISE, ARISING FROM, OUT OF, OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

This disclaimer supplements, and does not replace, the warranty disclaimer and limitation of liability provisions of the [BSD 3-Clause License](LICENSE), which govern this software.
