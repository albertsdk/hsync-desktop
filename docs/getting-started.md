# HSYNC Desktop — Getting Started

HSYNC Desktop is the graphical application for Windows, macOS and Linux: it
drives the bundled `hsync` client engine and gives you a tray-resident interface
to start and stop sync, watch transfers and adjust settings — without touching
the command line.

HSYNC Desktop is a **desktop application only**: it has no Docker or server
deployment mode (those belong to
[HSYNC Server](https://github.com/albertsdk/hsync-server) and
[HSYNC Bootnode](https://github.com/albertsdk/hsync-bootnode)).

Pick **one** installation method below and follow it to a running app. The
methods are ordered from the simplest and most immediate to the most involved.

| # | Method | Platform | Best for | Guide |
| - | ------ | -------- | -------- | ----- |
| 1 | **Installer script** (`install.sh` via `curl`) | <img src="assets/os/linux.svg" alt="Linux" width="16" height="16"> <img src="assets/os/apple.svg" alt="macOS" width="16" height="16"> | Least setup: one command, installs under your home, no `sudo` | [Install with the script](getting-started-script.md) |
| 2 | **Standalone binary** | <img src="assets/os/linux.svg" alt="Linux" width="16" height="16"> <img src="assets/os/apple.svg" alt="macOS" width="16" height="16"> <img src="assets/os/windows.svg" alt="Windows" width="16" height="16"> | You prefer to download and extract the archive yourself | [Standalone binary](getting-started-binary.md) |
| 3 | **Debian/Ubuntu package** (`.deb`) | <img src="assets/os/debian.svg" alt="Debian" width="16" height="16"> <img src="assets/os/ubuntu.svg" alt="Ubuntu" width="16" height="16"> | A Debian/Ubuntu host with a desktop-menu entry and a system package | [Debian package](getting-started-deb.md) |
| 4 | **RPM package** (`.rpm`) | <img src="assets/os/redhat.svg" alt="Red Hat" width="16" height="16"> <img src="assets/os/fedora.svg" alt="Fedora" width="16" height="16"> | A RHEL/Rocky/Alma/Fedora host with a desktop-menu entry and a system package | [RPM package](getting-started-rpm.md) |
| 5 | **AppImage** (portable, Linux x86_64) | <img src="assets/os/linux.svg" alt="Linux" width="16" height="16"> | A Linux desktop where you want one self-contained file and no installation | [AppImage](getting-started-appimage.md) |
| 6 | **Snap package** | <img src="assets/os/ubuntu.svg" alt="Ubuntu" width="16" height="16"> | A Linux desktop with `snapd`: automatic updates, classic confinement | [Snap package](getting-started-snap.md) |
| 7 | **macOS `.dmg`** (Apple silicon or Intel) | <img src="assets/os/apple.svg" alt="macOS" width="16" height="16"> | A Mac where you want the standard drag-to-Applications app | [macOS](getting-started-macos.md) |
| 8 | **Windows installer** (`.exe`) | <img src="assets/os/windows.svg" alt="Windows" width="16" height="16"> | A Windows x64 host: per-user install, Start Menu shortcut | [Windows installer](getting-started-windows.md) |
| 9 | **From source** (clone and run) |  | Development, or a host where you control the toolchain | [Run from source](getting-started-source.md) |

## Requirements

- <img src="assets/os/linux.svg" alt="Linux" width="16" height="16"> Linux **x86_64** or **aarch64**, <img src="assets/os/apple.svg" alt="macOS" width="16" height="16"> macOS (Intel or Apple silicon), or <img src="assets/os/windows.svg" alt="Windows" width="16" height="16"> Windows
  **10 (version 1809 or later) or 11, x64**
- The `hsync` engine is bundled by every installation method on this page —
  installer script, standalone binary, AppImage, `.deb`, `.rpm`, Snap, macOS `.dmg`
  and Windows installer (no separate `hsync-client` install needed)
- **Server Mode** needs an HSYNC Server with an account token (the share itself is
  created on the first upload); **p2p Mode** needs no server — see the
  [server getting started](https://github.com/albertsdk/hsync-server/blob/main/docs/getting-started.md)
- One folder per installation: **Settings → Sync → Local folder** holds the folder
  this device keeps in sync
- Raspberry Pi OS: **64-bit (arm64) only** — PySide6 publishes no 32-bit (armhf)
  Linux wheels
- The **AppImage** is **Linux x86_64 only**
- The **Snap** needs `snapd` with `core24` support and is installed with
  `--classic`; it ships its own runtime (the host's glibc version does not matter)
  and updates automatically
- The **macOS `.dmg`** is **unsigned**: macOS needs a one-time confirmation
  (right-click → Open, or `xattr -dr com.apple.quarantine`)
- The **Windows** build is **x64 only** and requires Windows 10 (version 1809 or
  later) or Windows 11; it is **not** supported under Wine/CrossOver (the Qt
  runtime needs the ICU library that ships with Windows)

## Next steps

- [Your first sync](first-sync.md) — from opening the app to the first completed sync
- [A tour of the window](tour.md) — what each part of the app is
- [Setup wizard](setup-wizard.md) — configure a connection in four steps
- [Configuration Reference](configuration.md) — every setting
- [Start, watch and stop a sync](sync-basics.md) — running and watching a sync
- [Log Labels](log-labels.md) — the action labels in the log panel
