<p align="center">
  <img src="docs/assets/hsync-logo-horizontal.svg" alt="HSYNC logo" width="300">
</p>

# HSYNC Desktop

**HSYNC Desktop** is the graphical application for Windows, macOS, and Linux. It
gives you a visual interface to control the HSYNC Client: start or stop sync,
monitor transfer progress, adjust settings, and get system notifications — all
without touching the command line.

New to HSYNC? Start with the [HSYNC Ecosystem](https://github.com/albertsdk/hsync/blob/main/README.md) for an overview of the platform before using HSYNC Desktop.

> 👉 **Operational Advisory:** As with any automated filesystem mutation utility, administrators are strongly advised to maintain validated, independent backups prior to initial deployment in production environments.

---

[![License: BSD 3-Clause](https://img.shields.io/badge/License-BSD_3--Clause-brightgreen.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/albertsdk/hsync-desktop)](https://github.com/albertsdk/hsync-desktop/releases/latest)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Qt 6](https://img.shields.io/badge/Qt-6-41CD52.svg)](https://www.qt.io/)

[![Debian/Ubuntu .deb](https://img.shields.io/badge/DEB-Debian%2FUbuntu-A81D33?logo=debian&logoColor=white)](docs/getting-started-deb.md)
[![RPM](https://img.shields.io/badge/RPM-RHEL%2FFedora-EE0000?logo=redhat&logoColor=white)](docs/getting-started-rpm.md)
[![AppImage](https://img.shields.io/badge/AppImage-Linux_x86__64-6DA741?logo=linux&logoColor=white)](docs/getting-started-appimage.md)
[![Snap](https://img.shields.io/badge/Snap-classic-82BEA0?logo=snapcraft&logoColor=white)](docs/getting-started-snap.md)
[![macOS](https://img.shields.io/badge/macOS-Apple_silicon_%7C_Intel-000000?logo=apple&logoColor=white)](docs/getting-started-macos.md)
[![Windows](https://img.shields.io/badge/Windows-x64-0078D4?logo=windows&logoColor=white)](docs/getting-started-windows.md)

<p align="center">
  <img src="docs/assets/hsync-desktop-gui.png" alt="HSYNC Desktop main window: file transfer panel with per-file progress, status bar and live log" width="720">
</p>

**Quick navigation:**
- **New to HSYNC?** Start with the [What you can do](#what-you-can-do-with-hsync-desktop) overview and [Getting started](#getting-started)
- **Configuring the app?** See the [Configuration Reference](docs/configuration.md)
- **Want to contribute?** See [Contributing](CONTRIBUTING.md)
- **Looking for detailed documentation?** Navigate to [docs/README.md](docs/README.md)

---

## What you can do with HSYNC Desktop

It offers the same core capabilities as [HSYNC Client](https://github.com/albertsdk/hsync-client/blob/main/README.md), plus a graphical layer on top:

- ▶️ Start/Stop/Sync controls with a local directory selector
- 📂 File transfer panel with per-file progress, status and ETA
- 👀 Sync preview/summary dialog before applying changes
- 📊 Status panel: connection state, primary/secondary role, bucket, group, peers and transfer statistics
- 🖥️ Real-time log viewer
- 🚦 Bandwidth-limit dialog (transfer throttling)
- 🔔 Desktop notifications for key events (configurable)
- 🙈 Hidden-file controls + `.hsyncignore` editor (gitignore-style exclusion)
- 📌 System tray integration with context menu
- 🌍 Multi-language UI (11 languages)
- 🌙 Light and dark themes

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
  bundled in every package (standalone binary, AppImage, `.deb`, `.rpm`, Snap)

## Getting started

HSYNC Desktop installs with one command, as a standalone download, as a `.deb`,
as a Snap, or from source. It is a **desktop application only** — there is no
Docker or server mode. Pick one method in the [Getting Started](docs/getting-started.md)
chooser:

- [Installer script](docs/getting-started-script.md) — one `curl` command (Linux/macOS);
- [Standalone binary](docs/getting-started-binary.md) — download and extract;
- [Debian package](docs/getting-started-deb.md) — system package for Debian/Ubuntu;
- [RPM package](docs/getting-started-rpm.md) — system package for RHEL/Rocky/Alma/Fedora;
- [AppImage](docs/getting-started-appimage.md) — portable Linux x86_64 file, no install;
- [Snap package](docs/getting-started-snap.md) — Linux with `snapd`, automatic updates;
- [macOS .dmg](docs/getting-started-macos.md) — Apple silicon or Intel;
- [Windows installer](docs/getting-started-windows.md) — per-user `.exe` setup;
- [From source](docs/getting-started-source.md) — clone and run.

Then configure a connection in the [Configuration Reference](docs/configuration.md)
and run a sync with the [Usage Guide](docs/usage.md).

## Associated Ecosystem Components

The other components of the HSYNC ecosystem:

- [HSYNC Main](https://github.com/albertsdk/hsync/blob/main/README.md) — Umbrella repository and project overview.
- [HSYNC Client](https://github.com/albertsdk/hsync-client/blob/main/README.md) — Command-line sync client.
- [HSYNC Server](https://github.com/albertsdk/hsync-server/blob/main/README.md) — Central sync hub: REST API, WebSocket relay, file storage.
- [HSYNC Bootnode](https://github.com/albertsdk/hsync-bootnode/blob/main/README.md) — Optional Internet discovery node for P2P (`boot/1`, no-log, RAM-only).
- [HSYNC Common](https://github.com/albertsdk/hsync-common/blob/main/README.md) — Shared library: data models, protocol, delta transfer, hashing.
- [HSYNC Android](https://github.com/albertsdk/hsync-android/blob/main/README.md) — Android client app. *(in development)*

## Security

To report a vulnerability, please use GitHub's **Private Vulnerability Reporting**:

👉 **[Report a vulnerability](https://github.com/albertsdk/hsync-desktop/security/advisories/new)**

See our [Security Policy](SECURITY.md) for supported versions and hardening
recommendations.

## 🙋‍♂️ A note from the maintainer

This project was born out of the need for a system capable of replicating the contents of a folder from a PC or Android device to a NAS, primarily for backup purposes. Several solutions were already available, but I couldn't find one that met all my requirements. This led to the somewhat questionable decision to develop one from scratch, while also providing an opportunity to gain a deeper understanding of programming languages, algorithms, frameworks, and related technologies.

Originally conceived as a hobby project, HSYNC has been under continuous development ever since. I believe it has now evolved to the point where its capabilities are comparable to those of commercial solutions, while also offering some distinctive features. As a result, it may also be suitable for deployment in certain production environments.

HSYNC is a passion project that I primarily develop and maintain in my spare time. Please keep this in mind when interacting with the project: we're all doing our best to build something great together, but this is not a paid, full-time job for any of us.

## Disclaimer

> [!WARNING]
> **HSYNC manipulates files and directories** — it creates, overwrites, moves, and deletes data.
> Misconfiguration, software defects, or other unforeseen conditions may lead to **data loss or
> corruption**. **Use at your own risk and always keep verified, independent backups.**

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NONINFRINGEMENT. Although the author has implemented reasonable safety measures, IN NO EVENT SHALL THE AUTHOR OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY — including, without limitation, any direct, indirect, incidental, special, exemplary, or consequential damages, loss of data, or business interruption — WHETHER IN AN ACTION OF CONTRACT, TORT, OR OTHERWISE, ARISING FROM, OUT OF, OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

This disclaimer supplements, and does not replace, the warranty disclaimer and limitation of liability provisions of the [BSD 3-Clause License](LICENSE), which govern this software.

## License

Distributed under the [BSD 3-Clause License](LICENSE).
