# Getting Started — Windows installer

The installer is **per-user** (no administrator rights). It installs HSYNC
Desktop and adds Start Menu (and optionally desktop) shortcuts. The app is
self-contained: it embeds the `hsync` client engine.

## Prerequisites

- <img src="assets/os/windows.svg" alt="Windows" width="16" height="16"> Windows 10/11 (x64)

## Install

Download the latest installer:

[Download hsync-desktop-windows-amd64-setup.exe](https://github.com/albertsdk/hsync-desktop/releases/latest/download/hsync-desktop-windows-amd64-setup.exe)

Run it and follow the wizard (tick "Create a desktop shortcut" if you want one).
The link always points to the **latest stable** release; to pin a version, use
the [Releases page](https://github.com/albertsdk/hsync-desktop/releases). Then
launch **HSYNC** from the Start Menu (the last wizard page can launch it too).

> The installer is **unsigned**, so Windows SmartScreen warns on the first run:
> choose **More info → Run anyway**. The portable `.zip` shows the same prompt.

> **Wine/CrossOver is not supported.** The app runs on the Qt runtime bundled in
> the PySide6 wheel, which links against the ICU library that ships with Windows
> (`icuuc.dll`). Compatibility layers do not provide it, so the app stops at
> startup with `Library icuuc.dll … not found`. On Linux use the native package
> instead — see [Getting Started](getting-started.md).

On first launch open **Settings** and configure a connection — see the
[Configuration Reference](configuration.md).

## Update and remove

Download and run the newer installer; it upgrades in place. To remove it, go to
**Settings → Apps → HSYNC Desktop**.

## Next

- Prefer no installation? [Standalone binary](getting-started-binary.md).
- Running from a clone? [From source](getting-started-source.md).
