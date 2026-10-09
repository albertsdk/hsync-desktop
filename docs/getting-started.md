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
| 6 | **macOS `.dmg`** (Apple silicon or Intel) | <img src="assets/os/apple.svg" alt="macOS" width="16" height="16"> | A Mac where you want the standard drag-to-Applications app | [macOS](getting-started-macos.md) |
| 7 | **Windows installer** (`.exe`) | <img src="assets/os/windows.svg" alt="Windows" width="16" height="16"> | A Windows x64 host: per-user install, Start Menu shortcut | [Windows installer](getting-started-windows.md) |
| 8 | **From source** (clone and run) |  | Development, or a host where you control the toolchain | [Run from source](getting-started-source.md) |

## Requirements

- <img src="assets/os/linux.svg" alt="Linux" width="16" height="16"> Linux **x86_64** or **aarch64**, <img src="assets/os/apple.svg" alt="macOS" width="16" height="16"> macOS (Intel or Apple silicon), or <img src="assets/os/windows.svg" alt="Windows" width="16" height="16"> Windows
  **x86_64**
- The `hsync` engine: the installer script, the standalone binary and the
  **AppImage** **embed** it; the `.deb`/`.rpm` install it as the `hsync-client`
  package dependency
- Raspberry Pi OS: **64-bit (arm64) only** — PySide6 publishes no 32-bit (armhf)
  Linux wheels
- The **AppImage** is **Linux x86_64 only**
- The **macOS `.dmg`** is **unsigned**: macOS needs a one-time confirmation
  (right-click → Open, or `xattr -dr com.apple.quarantine`)

## After installing

1. **Configure a connection** — Server Mode or p2p Mode. Every setting is
   documented in the [Configuration Reference](configuration.md).
2. **Run and watch a sync** — [Using HSYNC Desktop](usage.md).
3. **Read the log** — the action labels are in [Log Labels](log-labels.md).
