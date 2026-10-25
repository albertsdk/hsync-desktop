# HSYNC Desktop — Documentation

HSYNC Desktop is a cross-platform graphical front-end for the HSYNC file
synchronization client. It does not implement sync itself: it drives the bundled
`hsync` client binary, builds its command line from a friendly settings dialog,
and shows live progress, transfers and logs in a native window with a
system-tray icon.

## Start here

This guide is organised as a linear journey; pick the step that matches where
you are.

### 1. Install

Pick one method and follow it end to end:

- [Method 1 — Installer script](getting-started-script.md): one `curl` command,
  installs under your home (Linux/macOS). **Least setup.**
- [Method 2 — Standalone binary](getting-started-binary.md): download and
  extract the self-contained bundle.
- [Method 3 — Debian package](getting-started-deb.md): system package for
  Debian/Ubuntu.
- [Method 4 — RPM package](getting-started-rpm.md): system package for
  RHEL/Rocky/Alma/Fedora.
- [Method 5 — AppImage](getting-started-appimage.md): one self-contained file
  for Linux x86_64, no installation.
- [Method 6 — macOS .dmg](getting-started-macos.md): drag-to-Applications app
  for Apple silicon or Intel.
- [Method 7 — Windows installer](getting-started-windows.md): per-user `.exe`
  installer with Start Menu shortcuts.
- [Method 8 — From source](getting-started-source.md): clone and run.

Start from the [Getting Started](getting-started.md) chooser for a comparison
table that helps you pick. HSYNC Desktop ships as desktop packages only (there is
no Docker image): it is a desktop application that drives the bundled client.

### 2. Configure a connection

**New here?** Use the [Setup wizard](setup-wizard.md): four steps that cover the
common cases (back up, sync on the same network, sync from anywhere, share with a
team).

For full control, open **Settings** (p2p Mode or Server Mode). Every setting is
documented in the [Configuration Reference](configuration.md). The words the app
uses — share, group, primary, discovery server — are defined in
[Key concepts](concepts.md).

### 3. Run and watch a sync

[Using HSYNC Desktop](usage.md) covers running a sync, watching transfers, the
runtime warnings and trust prompts, secrets and preferences. If a folder keeps
re-syncing or reports phantom conflicts, the [FAQ](faq.md) explains how to start
it from a clean sync state; when something does not work at all, go to
[Troubleshooting](troubleshooting.md).

### 4. Reference

| Document | What it covers |
| -------- | -------------- |
| [setup-wizard.md](setup-wizard.md) | Guided four-step setup for the common cases. |
| [concepts.md](concepts.md) | The words the app uses (share, group, primary, discovery server, conflict copy). |
| [configuration.md](configuration.md) | Every setting in the Settings dialog (the single source of truth). |
| [usage.md](usage.md) | Running and watching syncs, runtime warnings, trust prompts, secrets, tray, themes. |
| [troubleshooting.md](troubleshooting.md) | Symptoms, what to check, where the logs are, how to get help. |
| [faq.md](faq.md) | Common questions, including how to reset a folder's sync state. |
| [log-labels.md](log-labels.md) | Action labels shown in the log panel and what they mean. |

### 5. Get help

[Support](../SUPPORT.md) says where to ask and what to include;
[Troubleshooting](troubleshooting.md) collects the common symptoms first.

## Associated Ecosystem Components

> The other HSYNC ecosystem components are listed in the
> [project README](../README.md#associated-ecosystem-components).
