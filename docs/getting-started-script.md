# Getting Started — Method 1: Installer script

The `install.sh` installer is the simplest way to get HSYNC Desktop running on
Linux or macOS: it downloads the self-contained bundle for your platform and
installs it under your home, exposing a `hsync-desktop` command. The bundle
already embeds the `hsync` client engine.

There is no Docker mode (this is a desktop GUI); the installer never uses
`sudo` and never touches system directories.

## Prerequisites

- Linux or macOS, x86_64 or arm64
- `curl` and `tar`
- `~/.local/bin` on your `PATH` (the installer links the command there)

## Install

### Quick install (one command, latest stable release)

```bash
curl -fsSL https://github.com/albertsdk/hsync-desktop/releases/latest/download/install.sh | bash
```

### Verified install (checksum)

To verify the download before running it:

```bash
curl -fLO "https://github.com/albertsdk/hsync-desktop/releases/latest/download/install.sh"
curl -fLO "https://github.com/albertsdk/hsync-desktop/releases/latest/download/SHA256SUMS"
sha256sum --ignore-missing -c SHA256SUMS
chmod 700 install.sh
./install.sh
```

On macOS, use `shasum -a 256 install.sh` and compare the result with the
matching line in `SHA256SUMS`.

The installer unpacks the app into `~/.local/share/hsync-desktop` and links the
`hsync-desktop` command into `~/.local/bin`. Run `./install.sh --help` for
`--version`, `--install-dir`, `--bin-dir` and `--dry-run` options. On Windows,
download the release `.zip` instead — see
[Standalone binary](getting-started-binary.md).

## Verify

```bash
hsync-desktop
```

The main window opens with a system-tray icon. On first launch open **Settings**
and configure a connection — see the [Configuration Reference](configuration.md).

## Update and uninstall

Re-running the installer with the same directories replaces the app with the
new version (settings and secrets are kept separately by Qt `QSettings`):

```bash
./install.sh
```

To uninstall, remove the app directory and the command link:

```bash
rm -rf "$HOME/.local/share/hsync-desktop" "$HOME/.local/bin/hsync-desktop"
```

## Next

- Configure Server Mode or p2p Mode: [Configuration Reference](configuration.md).
- Prefer a system package? [Debian package](getting-started-deb.md).
