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

## Configuring a connection

Open **Settings** and fill in the connection for your mode — **Server Mode**
(against a central HSYNC server) or **p2p Mode** (peer-to-peer, no server). Every
setting is documented in the
[Configuration Reference](configuration.md), including the Server, Sync, p2p,
Log and Appearance tabs and the trusted-key stores.

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
*Settings → p2p → Manage trusted keys…*.

## Running and watching a sync

1. Confirm your settings, then start the sync from the main window.
2. The file panel lists each file and its transfer status (queued, in progress,
   done, error); overall progress and throughput are shown live.
3. The log panel streams structured messages from the engine. You can hide or
   show it from the view options; the label catalogue is in
   [Log Labels](log-labels.md).
4. With watch / auto-sync enabled, the app keeps running and re-syncs on changes
   until you stop it.

## Secrets

API keys and p2p keys are entered through dedicated dialogs, never typed on a
command line. They are stored encrypted on disk (machine-derived key) and handed
to the engine over a private channel, so they never appear in process listings
or logs. Use the key dialogs to replace a key at any time.

## Preferences

- **Theme** — switch between available light/dark themes.
- **Notifications** — enable desktop notifications for sync events.
- **Bandwidth limits** — cap upload/download throughput.
- **Language** — the UI is available in English, Italian, German, Spanish and
  French.

## Troubleshooting

- **A control is greyed out** — your `hsync` binary lacks that capability;
  rebuild/update the client to enable it.
- **`hsync` binary not found** — the GUI looks for it bundled in the build, on
  `PATH`, or in `../hsync-client/dist/<os>-<arch>/`. Install the client or build
  it from the sibling checkout.
- **TLS errors in Server Mode** — verify the URL and certificate; enable
  *No verification* only on a trusted network for self-signed certificates.
- **Peers not found in p2p Mode** — ensure all devices are on the same subnet
  with mDNS allowed through the firewall, and share the same p2p key. For
  devices on different networks, set a **Bootnode** in the p2p tab.

See the [client documentation](https://github.com/albertsdk/hsync-client/blob/main/docs/README.md) for the
underlying sync behaviour and modes.
