# Getting Started — Method 2: Standalone binary

The self-contained bundle is the same artifact the installer script uses: a
single executable that embeds the `hsync` client engine. Download it manually
when you prefer not to run a `curl | bash` installer.

## Prerequisites

- Linux **x86_64**/**aarch64**, macOS (Intel or Apple silicon), or Windows
  **x86_64**

## Install

Download the archive for your platform from the
[Releases page](https://github.com/albertsdk/hsync-desktop/releases):

```
hsync-desktop-VERSION-linux-amd64.tar.gz
hsync-desktop-VERSION-linux-arm64.tar.gz
hsync-desktop-VERSION-darwin-amd64.tar.gz
hsync-desktop-VERSION-darwin-arm64.tar.gz
hsync-desktop-VERSION-windows-amd64.zip
```

The **latest stable** archive of each target is also available at a stable URL,
without knowing the version — replace `linux-amd64` with your target
(`linux-arm64`, `darwin-amd64`, `darwin-arm64`, `windows-amd64`):

```bash
curl -fLO "https://github.com/albertsdk/hsync-desktop/releases/latest/download/hsync-desktop-linux-amd64.tar.gz"
```

Verify it against the release `SHA256SUMS` if you wish, then extract and run it.

### Linux / macOS

```bash
tar -xzf hsync-desktop-linux-amd64.tar.gz
cd hsync-desktop-linux-amd64
./hsync-desktop
```

To get a `hsync-desktop` command on your `PATH`, move it into `~/.local/bin`:

```bash
mkdir -p "$HOME/.local/bin"
install -m 755 hsync-desktop "$HOME/.local/bin/hsync-desktop"
```

> On macOS the binary is unsigned, so Gatekeeper may block the first launch.
> Right-click the file and choose **Open**, or clear the quarantine attribute:
> `xattr -dr com.apple.quarantine hsync-desktop`.

### Windows

Extract the `.zip` and run `hsync-desktop.exe`. The bundle is self-contained, so
no Python or separate client install is required.

## Verify

Launch `hsync-desktop`: the main window opens with a system-tray icon. On first
launch open **Settings** and configure a connection — see the
[Configuration Reference](configuration.md).

## Update

Download the archive for the new version and repeat the install step; settings
and secrets are kept separately by Qt `QSettings`.

## Next

- Prefer the automated installer? [Installer script](getting-started-script.md).
- Prefer a system package on Debian/Ubuntu? [Debian package](getting-started-deb.md).
