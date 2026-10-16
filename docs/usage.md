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

- Installed with the installer script or a `.deb`: run `hsync-desktop`.
- Standalone bundle: run the extracted `hsync-desktop` executable.
- From source: `./run.sh`.

The main window shows the file/transfer panel and a log area; an icon also
appears in the system tray. Closing the window keeps the app running in the
tray — use the tray menu to show the window again or quit.

Run `hsync-desktop --minimized` to start straight into the tray without showing
the window (no tray available falls back to showing the window). Enable
**Launch at login** in *Settings → General* to do this automatically at login.

## Configuring a connection

Open **Settings** and fill in the connection for your mode — **p2p Mode**
(peer-to-peer, no server) or **Server Mode** (against a central HSYNC server).
Every setting is documented in the
[Configuration Reference](configuration.md), including the Sync, p2p Mode,
Server Mode, General and Advanced tabs and the trusted-key stores. Use
**General** for app preferences (language, theme, notifications, the log panel
and launch at login) and **Advanced** for engine tuning (performance, delta
transfer, deletion protection, bandwidth).

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
*Settings → p2p → Manage trusted servers & devices…*.

## Running and watching a sync

1. Confirm your settings, then start the sync from the main window. The action
   bar shows the **share name** next to the folder icon; click it to open the
   shared folder in your file manager, and hover it to see the local path.
2. The file panel lists each file and its transfer status (queued, in progress,
   done, error); overall progress and throughput are shown live.
   The bottom-right sent/received numbers are the **distinct files** moved this
   session (a file transferred or renamed more than once still counts once); the
   size in parentheses is the total bytes moved, repeats included.
3. The log panel streams structured messages from the engine. You can hide or
   show it from the view options; the label catalogue is in
   [Log Labels](log-labels.md).
4. With **Real-time sync** enabled, the app keeps running and re-syncs on changes
   until you stop it.

To sync a single folder on demand, right-click it (or use the **File** menu) and
choose **Send now** (push it to the other devices) or **Receive now** (pull it
from them). Both run a one-shot scoped to that folder — or, for a file, to its
containing folder — and are available only while no sync is running. A preview
summary is shown first, so you confirm exactly what will be transferred before it
runs.

## Secrets

API keys and shared passwords are entered through dedicated dialogs, never typed
on a command line. They are stored encrypted on disk (machine-derived key) and
handed to the engine over a private channel, so they never appear in process
listings or logs. Use the credential dialogs to replace a password at any time.

## Preferences

- **Theme** — switch between available light/dark themes.
- **Notifications** — enable desktop notifications for sync events.
- **Bandwidth limits** — cap upload/download throughput.
- **Language** — the UI is available in English, Italian, German, Spanish,
  French, Portuguese (Brazil), Chinese (Simplified), Russian, Dutch, Polish and
  Japanese.

## Troubleshooting

- **Synchronization does not start** — when the engine cannot start (for
  example the bundled `hsync` client is missing or incompatible), the app shows
  an error dialog with the reason the engine reported and writes the same
  message to the log panel, instead of failing silently.
- **A control is greyed out** — your sync engine lacks that capability;
  rebuild/update the client to enable it.
- **Sync engine not found** — the GUI looks for it bundled in the build, on
  `PATH`, or in `../hsync-client/dist/<os>-<arch>/`. Install the client or build
  it from the sibling checkout.
- **TLS errors in Server Mode** — verify the URL and certificate; enable
  *No verification* only on a trusted network for self-signed certificates.
- **Devices not found in p2p Mode** — ensure all devices are on the same subnet
  with mDNS allowed through the firewall, and that they use the same **group
  name** (a device with no group only sees other no-group devices). A shared
  password is only needed to authorize writes; devices on different networks
  need a **relay server** set in the p2p tab.
- **p2p authentication failed** — a device you are syncing with requires a shared
  password that this device is missing or has differently. The app stops and
  opens the password prompt so you can enter the correct one (it is saved and the
  sync retries); the password must be identical on every device in the group.

See the [client documentation](https://github.com/albertsdk/hsync-client/blob/main/docs/README.md) for the
underlying sync behaviour and modes.
