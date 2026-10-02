# Getting Started — Method 3: Debian/Ubuntu package

The `.deb` installs HSYNC Desktop system-wide (`/usr/bin/hsync-desktop` plus an
application-menu entry and the app icon). Unlike the standalone bundle, it does
**not** embed the engine: it declares `hsync-client` as a dependency, which
provides `/usr/bin/hsync`.

## Prerequisites

- Debian or Ubuntu, **amd64** or **arm64** (armhf is not supported: PySide6
  publishes no 32-bit Linux wheels)
- A root shell or `sudo`

## Install

The package depends on `hsync-client`, so install the client package first (or
pass both to `apt` in one command). Both URLs always point to the **latest
stable** release (use `arm64` instead of `amd64` on ARM):

```bash
# 1. The engine (from the hsync-client releases)
curl -fLO "https://github.com/albertsdk/hsync-client/releases/latest/download/hsync-client-amd64.deb"
# 2. The desktop GUI (from the hsync-desktop releases)
curl -fLO "https://github.com/albertsdk/hsync-desktop/releases/latest/download/hsync-desktop-amd64.deb"

sudo apt install ./hsync-client-amd64.deb ./hsync-desktop-amd64.deb
```

`apt` resolves both the `hsync-client` dependency and the Qt runtime libraries
(`libgl1`, `libegl1`, `libxkbcommon*`, …) from the distribution repositories.

### Build from the checkout (alternative)

From the `hsync-desktop` checkout, with the client already built as a sibling:

```bash
./compile.sh --target deb
sudo apt install ./dist/deb/hsync-desktop_<ver>_<arch>.deb
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

Uninstalling `hsync-desktop` leaves the `hsync-client` package in place.

## Next

- Prefer a user-local install? [Installer script](getting-started-script.md) or
  [Standalone binary](getting-started-binary.md).
- Running from a clone? [From source](getting-started-source.md).
