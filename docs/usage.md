# Using HSYNC Desktop

This guide walks through everyday use of the desktop GUI: starting the app,
configuring a connection, running and watching a sync, handling secrets, and the
convenience features (tray, themes, notifications, bandwidth limits). The
settings themselves are documented once in the
[Configuration Reference](configuration.md).

## Starting the app

Launch it the way you installed it:

```bash
hsync-desktop
```

- Installer script, `.deb` or `.rpm`: run `hsync-desktop`.
- Standalone bundle or AppImage: run the extracted file.
- macOS `.dmg`: open **HSYNC** from Launchpad or Applications.
- Windows installer: open **HSYNC** from the Start Menu.
- From source: `./run.sh`.

The main window shows the file/transfer panel and a log area; an icon also
appears in the system tray. Closing the window hides it to the tray and a running
sync keeps going — use the tray menu to show the window again. **Quit** stops the
sync and asks for confirmation while one is running; without a system tray the
window really closes (it asks the same confirmation) and the app exits. Launching
the app again never opens a second window: it brings the existing one forward.

Run `hsync-desktop --minimized` to start straight into the tray without showing
the window (no tray available falls back to showing the window). Enable
**Launch at login** in *Settings → General* to do this automatically at login.
The welcome splash appears only on the first launch and never delays the window.

## Configuring a connection

The quickest path is the [Setup wizard](setup-wizard.md) (**Setup wizard** in the
menu bar), which covers the four common cases in four steps and pre-fills your
current configuration on re-run. For full control, open **Settings** and fill in
the connection for your mode — **p2p Mode** (peer-to-peer, no server) or **Server
Mode** (against a central HSYNC server).
Every setting is documented in the
[Configuration Reference](configuration.md), including the Sync, p2p Mode,
Server Mode, General and Advanced tabs and the trusted-key stores. Use
**General** for app preferences (language, theme, notifications, the log panel
and launch at login) and **Advanced** for engine tuning (performance, delta
transfer, deletion protection, bandwidth).

The Server and p2p tabs include a **Learn more** link to the matching external
guide — the [hsync-server setup guide](https://github.com/albertsdk/hsync-server/blob/main/docs/getting-started.md)
and the [hsync-bootnode guide](https://github.com/albertsdk/hsync-bootnode/blob/main/docs/getting-started.md)
— and the Setup wizard's mode step links to this guide's connection-mode
sections. **Help → Documentation** (or `F1`) opens this documentation index, and
the same menu holds **Project on GitHub** plus the in-app **About** and
**License** dialogs.

The primary/secondary role shown in the status bar exists only in p2p mode and its
text appears once the device is connected and the role is known (before that the
bar shows a neutral icon only); Server Mode has no such role.

Next to the shared-folder size, the status bar also answers the question the
connection indicator cannot: **are the files in sync?** It reads `Checking…` while
a comparison runs, `No devices` when there is nothing to compare against (no other
device connected yet), `All files in sync` when nothing is pending, and
`2 to download · 1 to send` (or `3 change(s) pending` for deletes and renames)
when work is left. A device that serves the share as **primary** reports the same
states: it compares its folder with what the connected devices published, so its
table shows the pending transfers instead of staying on `Local`. Hover the text
for a reminder of what the current state means.

In the trusted-key
dialog (*Manage trusted servers & devices…*) the tabs follow the active mode: p2p
shows the discovery-server and device stores, Server Mode shows the **Server HSYNC**
store. Enabling **Detailed log output** while the log panel is hidden offers to
show the panel.

## Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl+O`, `Enter` | Open the selected file or folder |
| `F2` | Rename |
| `Delete` | Move to trash |
| `Alt+Enter` | Properties |
| `Ctrl+Shift+C` | Copy path |
| `Ctrl+Alt+C` | Copy to a folder |
| `F5` | Refresh the file list |
| `Ctrl+Shift+S` | Start |
| `Ctrl+,` | Settings |
| `F1` | Documentation |
| `Ctrl+Q` | Quit |

On macOS `Cmd` replaces `Ctrl` (`Cmd+,` for Settings, `Cmd+Q` to quit). The log
panel uses the standard `Ctrl+C` / `Ctrl+A` for copying and selecting its text.
The file-list actions work on the selected row, so the keys do nothing without a
selection.

## Trust prompts while running

While a p2p sync is running, the app may prompt you when a device presents an
unrecognised or changed certificate fingerprint (the terminal-free equivalent of
the client's trust checks):

- **Pairing required** — strict pairing refuses a first-seen fingerprint. Trust
  it (after verifying it out of band) or ignore it.
- **Fingerprint changed** — a previously pinned device now presents a different
  fingerprint, possibly a man-in-the-middle. Trust the new fingerprint, forget
  the stored key, or ignore it.

Accepting a fingerprint pins it in the client's trust store, so both the app and
the `hsync` CLI see the same keys. The stores can also be edited from
*Settings → p2p → Manage trusted servers & devices…* (in Server Mode the dialog
opens on the **Server HSYNC** store).

## Running and watching a sync

1. Confirm your settings, then start the sync from the main window. The action
   bar shows the **share name** next to the folder icon; click it to open the
   shared folder in your file manager, and hover it to see the local path.
2. The file panel lists each file and its transfer status (queued, in progress,
   done, error); overall progress and throughput are shown live. A file you are
   receiving appears in the list while it is still being written, with its
   percentage and rate, and shows its real size once complete.
   The bottom-right sent/received numbers are the **distinct files** moved this
   session (a file transferred or renamed more than once still counts once); the
   size in parentheses is the total bytes moved, repeats included.
3. The log panel streams structured messages from the engine, colored with the
   engine's own palette (levels and label categories, adapted to the light or
   dark theme). You can hide or show it from the view options; the label
   catalogue is in [Log Labels](log-labels.md).
4. With **Real-time sync** enabled, the app keeps running and re-syncs on changes
   until you stop it.

When two devices really change the same file at once, the merge keeps one version
and preserves the other next to it as a conflict copy (`_conflicted_copy_`), so
nothing is lost; the log names the file. The rules behind it are the client's
[conflict resolution](https://github.com/albertsdk/hsync-client/blob/main/docs/conflict-resolution.md).

The first time you start a sync, the app shows a liability disclaimer: choose
**I understand** to continue, or **Not now** to close it without starting the
sync. Check **Don't show this message again** to stop asking; the app prompts
again only when the disclaimer text changes.

To sync a single folder on demand, right-click it (or use the **File** menu) and
choose **Send now** (push it to the other devices) or **Receive now** (pull it
from them). Both run a one-shot scoped to that folder — or, for a file, to its
containing folder — and are available only while no sync is running. A preview
summary is shown first, so you confirm exactly what will be transferred before it
runs.

With **Simulation Mode** enabled (Settings → Sync) the run stops at that summary:
nothing is transferred or deleted, and the app tells you so. While the mode is
on, the main window shows a **Simulation — no changes** badge next to the
connection status, the title bar ends with **— Simulation**, the Start button
tooltip says the run only previews, and every run starts with a
`--- Simulation: no changes will be applied ---` line in the log. The summary
dialog's only action is **Close**.

Transient messages (searching for devices, connection results, "nothing to
sync", a Send/Receive while a sync is running) appear as a small overlay toast in
the bottom-right corner, so nothing shifts and you do not need the log panel open
to see the outcome.

Toast colours follow the severity: blue for information, green for a completed
result, amber for a warning, red for an error (an icon and a title make the
severity recognisable without colour). Errors and warnings stay in the window
until you close them, whatever the notifications preference, and survive a new
sync; they are the in-app counterpart of the desktop notification, which is sent
only while the window is in the background.

While the one-shot runs, a toast shows what it is doing — searching for devices
(in p2p mode) or connecting to the server, then how many other devices were
found. When it ends, the result is reported once: the window shows a summary
dialog when it is in the foreground, or a desktop notification when it is not. In
both cases you are told whether the transfer completed and how many items moved,
if nothing was pending ("already up to date"), if no other device was found, or
if the server could not be reached. A one-shot only reports a lost connection if
it had actually connected first. The file list stays in the folder you were
browsing, with the entry you acted on still selected. Folders created on a remote
peer appear in the list as **Synced** (green), like the files inside them.

## Warnings before and during a sync

Three checks can stop a start or a deletion phase. Each one explains itself in
the dialog or toast; this is what they mean and what to do:

- **File Deletion Risk** — the folder is not empty and the current settings can
  delete local files. It appears in p2p Mode while **Prefer primary role** is off
  (local files missing on the primary device may be removed here) and with the
  **Receive only** sync type (deletions made elsewhere apply here). Check the
  folder and confirm to continue; enabling **Prefer primary role** or the one-way
  **Send only** type is what makes it stop asking. Simulation Mode skips it.
- **Deletions skipped (deletion protection)** — a cycle wanted to delete more
  local files than **Max deletions per cycle** or **Max deletions percent** allow.
  Those deletions were skipped and the sync kept running; a later cycle retries
  them. If the removal is expected, raise the limits in *Settings → Advanced*;
  otherwise check the primary device or the source first.
- **No shared password** — with an empty p2p password the app confirms before
  starting, because reads are open to anyone who can reach this device. Set the
  password in the p2p tab to stop the prompt (see
  [Keyless runs](configuration.md#p2p-mode)).

## Secrets

API keys and shared passwords are entered through dedicated dialogs, never typed
on a command line. They are stored encrypted on disk (machine-derived key) and
handed to the engine over a private channel, so they never appear in process
listings or logs. Use the credential dialogs to replace a password at any time.

## Preferences

- **Theme** — **System default** follows your desktop and updates live; **Light**
  and **Dark** pin an appearance.
- **Notifications** — show desktop/system notifications for sync events. Errors
  and warnings are always shown in the app window, so turning this off only
  silences the operating-system notifications.
- **Bandwidth limits** — cap upload/download throughput.
- **Advanced options** — off by default: the Advanced tab and the *Advanced
  Options* sections stay hidden until you enable **Show advanced options** in
  General, so the standard view stays simple.
- **Language** — the UI is available in English, Italian, German, Spanish,
  French, Portuguese (Brazil), Chinese (Simplified), Russian, Dutch, Polish and
  Japanese.
- **Fonts** — the interface follows your desktop's UI and monospace fonts and the
  system text scaling (GNOME/Ubuntu and KDE). **Font size** on the General tab
  selects **Standard** (desktop size, including the file list) or **Slightly
  reduced** (one point smaller across the app, never below 8 pt); the file list
  keeps a comfortable row height either way.

The file list shows the standard columns plus **Direction** (↑/↓, ✕ on a deleted
row, ⇄ on a rename), visible by default; the direction is blank when there is no
operation and its glyphs are bold for emphasis. **Speed** (live transfer rate) is
available from the header menu and hidden until you enable it. Files show the
planned action ("To upload" / "To download" / …), while a folder shows a neutral
aggregate ("To sync") whose tooltip breaks down the mixed operations. You can
**drag the column edges** to resize any data column; the widths are remembered,
and **Reset columns** in the header menu restores the default layout. On the very
first launch the window opens wide enough to give the file names room, and the
file list keeps that shape until you resize a column. **Reset columns** in the
header menu drops the saved layout, so the following launch gets that roomy
default again. The status
bar's **Shared: X / Y** indicator shows the shared
folder's size on this device (**X**) and the size of the whole share (**Y**, a
dash while it is not yet known): the whole-share value is the sync set (remote
files plus local files not yet uploaded) and is approximate when the two sides
disagree on a file's size. Files and folders whose name starts with a dot are
hidden from the list; enable **Show hidden files** from the table header menu to
see them (this changes only the list, not what is synchronised). Right-click a
row for the actions on that file or folder — open, open the containing folder,
open with another app, send/receive now, copy to a folder, copy the path, rename,
move to trash, properties. **Copy path** puts the absolute path (in your system's
form, e.g. backslashes on Windows) on the clipboard, while **Copy relative path**
copies the path inside the shared folder; both are also in the **File** menu.
In Server Mode, the address field accepts a bare hostname or `host:port` —
`https://` and the default port are implied.

## Reset the sync state

When a folder keeps re-syncing, reports conflicts on files nobody edited, or the
log shows a database error, the folder's local sync history is inconsistent.
**Settings → Sync → Advanced options → Reset sync state…** makes the next sync
reconcile the folder from scratch.

Before you confirm, stop the sync (the reset control is disabled while a sync
runs) and know what to expect on the next cycle:

- every file is read and hashed again, so the first sync is slower;
- files that are identical on both devices are **not** transferred;
- differences are resolved normally, and a conflict copy is kept when both
  sides changed;
- files deleted shortly before the reset can come back, because the deletion
  history is forgotten.

It never touches your files, `.hsyncignore`, the settings, the saved keys, the
device identity or the trusted fingerprints — only the folder's internal
version/deletion state. If the state file is unreadable, the app reports the
error instead of guessing; `hsync state reset --folder DIR --quarantine` from the
client moves it aside and the folder starts from scratch.

## Troubleshooting

Start with the [Troubleshooting guide](troubleshooting.md): it covers a sync that
does not start, greyed-out controls, p2p discovery and TLS problems, the deletion
warnings, and where the logs are. For the underlying sync behaviour and modes,
see the [client documentation](https://github.com/albertsdk/hsync-client/blob/main/docs/README.md).
