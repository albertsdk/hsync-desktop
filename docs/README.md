# HSYNC Desktop — Documentation

HSYNC Desktop is a cross-platform graphical front-end for the HSYNC file
synchronization client. It does not implement sync itself: it drives the bundled
`hsync` client binary, builds its command line from a friendly settings dialog,
and shows live progress, transfers and logs in a native window with a
system-tray icon.

## Start here

This guide is organised as a linear journey; pick the step that matches where you
are.

### 1. Install

Pick a method in the [Getting Started](getting-started.md) chooser: it compares
the nine ways to install HSYNC Desktop (installer script, standalone binary,
`.deb`, `.rpm`, AppImage, Snap, macOS `.dmg`, Windows installer, from source) and
links the matching guide.

### 2. Take the tour

New to the app? [A tour of the window](tour.md) shows the menu bar, the toolbar,
the path bar, the file list and the status bar, so you know what each part is.

### 3. Do your first sync

Follow [Your first sync](first-sync.md): the guided path from opening the wizard to
the first completed sync. For the four common cases step by step, including the
fields and the "use these details" invite, see [Set up with the wizard](setup-wizard.md).
Still choosing between a server and peer-to-peer (p2p)? Read
[Choose how your devices connect](choose-connection.md) first.

### 4. Use it every day

[Start, watch and stop a sync](sync-basics.md) covers the everyday controls;
[The file list](file-list.md) explains the table and its right-click menu;
[Warnings and notifications](warnings.md) explains the prompts, badges and
notifications. When something does not work at all, go to
[Troubleshooting](troubleshooting.md).

### 5. Reference

| Document | What it covers |
| -------- | -------------- |
| [tour.md](tour.md) | A tour of the window, part by part. |
| [first-sync.md](first-sync.md) | The guided path to a first sync. |
| [setup-wizard.md](setup-wizard.md) | The guided four-step setup and its fields. |
| [concepts.md](concepts.md) | The words the app uses (share, group, primary, rendezvous server, conflict copy). |
| [choose-connection.md](choose-connection.md) | Server Mode vs p2p Mode, and which to pick. |
| [choose-sync-type.md](choose-sync-type.md) | Send-only, receive-only, or both. |
| [choose-deletion-policy.md](choose-deletion-policy.md) | Apply deletions (mirror) vs keep deleted files (backup). |
| [choose-trust.md](choose-trust.md) | Trust, fingerprints and identity checks. |
| [configuration.md](configuration.md) | Every setting in the Settings dialog (the single source of truth). |
| [sync-basics.md](sync-basics.md) | Starting, watching and stopping a sync; shortcuts. |
| [file-list.md](file-list.md) | The file table: columns, actions, hidden files. |
| [warnings.md](warnings.md) | Toasts, banners, notifications, badges and the "in sync?" states. |
| [secrets.md](secrets.md) | Account keys and shared passwords. |
| [reset-sync-state.md](reset-sync-state.md) | Reconciling a folder from scratch. |
| [troubleshooting.md](troubleshooting.md) | Symptoms, what to check, where the logs are, how to get help. |
| [faq.md](faq.md) | Common questions. |
| [log-labels.md](log-labels.md) | Action labels shown in the log panel (advanced). |

### 6. Get help

[Support](../SUPPORT.md) says where to ask and what to include;
[Troubleshooting](troubleshooting.md) collects the common symptoms first.

## Associated Ecosystem Components

> The other HSYNC ecosystem components are listed in the
> [project README](../README.md#associated-ecosystem-components).
