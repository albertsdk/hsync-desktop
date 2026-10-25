# Getting Started — Method 3: Debian/Ubuntu package

The `.deb` installs HSYNC Desktop system-wide (`/usr/bin/hsync-desktop` plus an
application-menu entry and the app icon). It is **self-contained**: the matching
`hsync` engine is bundled, so no separate `hsync-client` package is required.

## Prerequisites

- <img src="assets/os/debian.svg" alt="Debian" width="16" height="16"> <img src="assets/os/ubuntu.svg" alt="Ubuntu" width="16" height="16"> Debian or Ubuntu, **amd64** or **arm64** (armhf is not supported: PySide6
  publishes no 32-bit Linux wheels)
- A root shell or `sudo`

> The `.deb` is built per architecture: **amd64** on Debian 12 (glibc 2.36), so
> it runs on Debian 12+ / Ubuntu 22.04+; **arm64** on Debian 13 "trixie" (glibc
> 2.41, required by PySide6's aarch64 wheel), so it needs Debian 13+ /
> Ubuntu 25.04+.

## Install

```bash
curl -fLO "https://github.com/albertsdk/hsync-desktop/releases/latest/download/hsync-desktop-amd64.deb"
sudo apt install ./hsync-desktop-amd64.deb
```

Use `arm64` instead of `amd64` on ARM. The URL always points to the **latest
stable** release. `apt` resolves the Qt/X runtime libraries (`libgl1`,
`libegl1`, `libxkbcommon*`, `libxcb1`, `libwayland-*`) from the distribution
repositories.

### Build from the checkout (alternative)

From the `hsync-desktop` checkout, with the client built as a sibling (the
engine is read from `../hsync-client` and embedded in the package, so the build
fails without it):

```bash
./compile.sh --target deb
sudo apt install ./dist/deb/hsync-desktop_*.deb
```

`./compile.sh --target deb-all` cross-builds the `amd64` and `arm64` packages
inside Docker.

## Verify

Launch it from the application menu, or:

```bash
hsync-desktop
```

The main window opens with a system-tray icon. On first launch open **Settings**
and configure a connection — see the [Configuration Reference](configuration.md).

## Update and uninstall

Install the newer `.deb` over the existing one; settings and secrets are kept.

```bash
sudo apt remove hsync-desktop
```

Removal deletes the application files only: the `hsync` engine belongs to this
package, so there is no separate client package to clean up.

## Next

- Prefer a user-local install? [Installer script](getting-started-script.md) or
  [Standalone binary](getting-started-binary.md).
- Running from a clone? [From source](getting-started-source.md).
