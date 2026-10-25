# Getting Started — AppImage (portable Linux, x86_64)

The AppImage is a **single self-contained executable** for Linux x86_64. It
bundles the GUI, the Qt runtime and the `hsync` client engine, so there is
nothing to install, no root and no package manager involved.

> Only **x86_64** is provided. On Linux arm64 use the
> [Debian package](getting-started-deb.md)/[RPM package](getting-started-rpm.md)
> or the Raspberry Pi binary; on other systems use the
> [standalone binary](getting-started-binary.md).

## Prerequisites

- <img src="assets/os/linux.svg" alt="Linux" width="16" height="16"> A 64-bit Linux desktop (`x86_64`)
- FUSE 2, which most distributions ship. Without it, run the AppImage with
  `--appimage-extract-and-run` (see [Run](#run))
- The usual X11/Wayland desktop libraries (present on any graphical session)

## Install

```bash
curl -fLO "https://github.com/albertsdk/hsync-desktop/releases/latest/download/hsync-desktop-x86_64.AppImage"
chmod +x hsync-desktop-x86_64.AppImage
```

The URL always points to the **latest stable** release; to pin a version, use
`https://github.com/albertsdk/hsync-desktop/releases/download/vX.Y.Z/hsync-desktop-<version>-x86_64.AppImage`.

### Build from the checkout (alternative)

With the `hsync-client` engine already built as a sibling directory (install the
build dependencies first — see [Contributing](../CONTRIBUTING.md); the package
embeds the engine, so the build fails without it):

```bash
./compile.sh --target appimage
```

The AppImage is written to `dist/appimage/`.

## Run

```bash
./hsync-desktop-x86_64.AppImage
```

If FUSE is unavailable (some containers or minimal systems):

```bash
./hsync-desktop-x86_64.AppImage --appimage-extract-and-run
```

## Optional: desktop-menu integration

The AppImage already contains the icon and the `.desktop` entry. To add it to
your application menu, use a tool such as AppImageLauncher, or copy the AppImage
to a stable path and create your own `.desktop` entry pointing at it.

## Update and remove

Download the newer AppImage and replace the file. To remove it, delete the file
(and any `.desktop` entry you created).

## Next

- Prefer a system package? [Debian package](getting-started-deb.md) or
  [RPM package](getting-started-rpm.md).
- Running from a clone? [From source](getting-started-source.md).
