# Getting Started — RPM package (RHEL/Rocky/Alma/Fedora)

The `.rpm` installs HSYNC Desktop system-wide (`/usr/bin/hsync-desktop` plus an
application-menu entry and the app icon). Like the Debian package, it does
**not** embed the engine: it declares `hsync-client` as a dependency, which
provides `/usr/bin/hsync`.

> The RPM binaries are built on a Rocky Linux 9 baseline (glibc 2.34), so they
> run on RHEL/Rocky/Alma 9+, recent Fedora, and any distro with glibc ≥ 2.34.

## Prerequisites

- <img src="assets/os/redhat.svg" alt="Red Hat" width="16" height="16"> <img src="assets/os/fedora.svg" alt="Fedora" width="16" height="16"> RHEL, Rocky Linux, AlmaLinux (9+) or Fedora, on **x86_64** or **aarch64**
- A root shell or `sudo`

## Install

The package depends on `hsync-client`, so install the client RPM first (or pass
both to `dnf` in one command). Both URLs always point to the **latest stable**
release (use `aarch64` instead of `x86_64` on ARM):

```bash
# 1. The engine (from the hsync-client releases)
curl -fLO "https://github.com/albertsdk/hsync-client/releases/latest/download/hsync-client-x86_64.rpm"
# 2. The desktop GUI (from the hsync-desktop releases)
curl -fLO "https://github.com/albertsdk/hsync-desktop/releases/latest/download/hsync-desktop-x86_64.rpm"

sudo dnf install ./hsync-client-x86_64.rpm ./hsync-desktop-x86_64.rpm
```

`dnf` resolves the Qt/X runtime libraries (`libglvnd`, `libxkbcommon*`,
`xcb-util-*`, `fontconfig`, `dbus-libs`) from the distribution repositories.

### Build from the checkout (alternative)

From the `hsync-desktop` checkout, with the client already built as a sibling:

```bash
./compile.sh --target rpm
sudo dnf install ./dist/rpm/hsync-desktop-*.rpm
```

`./compile.sh --target rpm-all` cross-builds the `x86_64` and `aarch64`
packages inside Docker.

## Verify

Launch it from the application menu, or:

```bash
hsync-desktop
```

The main window opens with a system-tray icon. On first launch open **Settings**
and configure a connection — see the [Configuration Reference](configuration.md).

## Update and uninstall

Install the newer `.rpm` over the existing one; settings and secrets are kept.

```bash
sudo dnf remove hsync-desktop
```

Uninstalling `hsync-desktop` leaves the `hsync-client` package in place.

## Next

- Prefer a user-local install? [Installer script](getting-started-script.md) or
  [Standalone binary](getting-started-binary.md).
- Running from a clone? [From source](getting-started-source.md).
