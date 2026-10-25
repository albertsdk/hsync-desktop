# Getting Started — RPM package (RHEL/Rocky/Alma/Fedora)

The `.rpm` installs HSYNC Desktop system-wide (`/usr/bin/hsync-desktop` plus an
application-menu entry and the app icon). It is **self-contained**: the matching
`hsync` engine is bundled, so no separate `hsync-client` package is required.

> The RPM is built per architecture on a RHEL-family baseline: **x86_64** on
> Rocky Linux 9 (glibc 2.34), so it runs on RHEL/Rocky/Alma 9+, recent Fedora,
> and any distro with glibc ≥ 2.34; **aarch64** on AlmaLinux 10 (glibc 2.39,
> required by PySide6's aarch64 wheel), so it needs RHEL/Rocky/Alma 10+.

## Prerequisites

- <img src="assets/os/redhat.svg" alt="Red Hat" width="16" height="16"> <img src="assets/os/fedora.svg" alt="Fedora" width="16" height="16"> RHEL, Rocky Linux, AlmaLinux (9+) or Fedora, on **x86_64** or **aarch64**
- A root shell or `sudo`

## Install

```bash
curl -fLO "https://github.com/albertsdk/hsync-desktop/releases/latest/download/hsync-desktop-x86_64.rpm"
sudo dnf install ./hsync-desktop-x86_64.rpm
```

Use `aarch64` instead of `x86_64` on ARM. The URL always points to the **latest
stable** release. `dnf` resolves the Qt/X runtime libraries (`libglvnd`,
`libxkbcommon*`, `xcb-util-*`, `fontconfig`, `dbus-libs`) from the distribution
repositories.

### Build from the checkout (alternative)

From the `hsync-desktop` checkout, with the client built as a sibling (the
engine is read from `../hsync-client` and embedded in the package, so the build
fails without it):

```bash
./compile.sh --target rpm
sudo dnf install ./dist/rpm/hsync-desktop-*.rpm
```

`./compile.sh --target rpm-all` cross-builds the `x86_64` and `aarch64`
packages inside Docker, building the matching-arch client there.

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

## Next

- Prefer a user-local install? [Installer script](getting-started-script.md) or
  [Standalone binary](getting-started-binary.md).
- Running from a clone? [From source](getting-started-source.md).
