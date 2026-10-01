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

| # | Method | Best for | Guide |
| - | ------ | -------- | ----- |
| 1 | **Installer script** (`install.sh` via `curl`) | Least setup: one command, installs under your home, no `sudo` | [Install with the script](getting-started-script.md) |
| 2 | **Standalone binary** | You prefer to download and extract the archive yourself | [Standalone binary](getting-started-binary.md) |
| 3 | **Debian/Ubuntu package** (`.deb`) | A Debian/Ubuntu host with a desktop-menu entry and a system package | [Debian package](getting-started-deb.md) |
| 4 | **RPM package** (`.rpm`) | A RHEL/Rocky/Alma/Fedora host with a desktop-menu entry and a system package | [RPM package](getting-started-rpm.md) |
| 5 | **From source** (clone and run) | Development, or a host where you control the toolchain | [Run from source](getting-started-source.md) |

## Requirements

- Linux **x86_64** or **aarch64**, macOS (Intel or Apple silicon), or Windows
  **x86_64**
- The `hsync` engine: the installer script and the standalone binary **embed**
  it; the `.deb` installs it as the `hsync-client` package dependency
- Raspberry Pi OS: **64-bit (arm64) only** — PySide6 publishes no 32-bit (armhf)
  Linux wheels

## After installing

1. **Configure a connection** — Server Mode or p2p Mode. Every setting is
   documented in the [Configuration Reference](configuration.md).
2. **Run and watch a sync** — [Using HSYNC Desktop](usage.md).
3. **Read the log** — the action labels are in [Log Labels](log-labels.md).
