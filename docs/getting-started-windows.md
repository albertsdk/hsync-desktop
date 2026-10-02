# Getting Started — Windows installer

The installer is **per-user** (no administrator rights). It installs HSYNC
Desktop and adds Start Menu (and optionally desktop) shortcuts. The app is
self-contained: it embeds the `hsync` client engine.

## Prerequisites

- Windows 10/11 (x64)

## Install

1. Download `hsync-desktop-VERSION-windows-amd64-setup.exe` from the release page
   (replace `VERSION` with the release you want).
2. Run it and follow the wizard. Tick "Create a desktop shortcut" if you want
   one.
3. Launch **HSYNC** from the Start Menu. On the last wizard page you can tick
   "Launch HSYNC Desktop".

On first launch open **Settings** and configure a connection — see the
[Configuration Reference](configuration.md).

## Update and remove

Download and run the newer installer; it upgrades in place. To remove it, go to
**Settings → Apps → HSYNC Desktop**.

## Next

- Prefer no installation? [Standalone binary](getting-started-binary.md).
- Running from a clone? [From source](getting-started-source.md).
