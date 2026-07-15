# Using HSYNC Desktop

This guide walks through everyday use of the desktop GUI: configuring a
connection, running and watching a sync, handling secrets, and the convenience
features (tray, themes, notifications, bandwidth limits).

## Starting the app

```bash
poetry run hsync-desktop
```

The main window shows the file/transfer panel and a log area; an icon also
appears in the system tray. Closing the window keeps the app running in the
tray — use the tray menu to show the window again or quit.

## Configuring a connection

Open **Settings**. The dialog is organised into three tabs.

### Server tab
For **Server Mode** (sync against a central HSYNC server):

- **Server URL** — e.g. `https://my-nas:9753`.
- **Bucket** — the remote bucket name to sync into.
- **API key** — click to enter or replace it (see *Secrets* below).
- **Insecure** — accept self-signed TLS certificates (use only on trusted networks).

### Sync tab
- **Local folder** — the directory to keep in sync.
- **Watch / auto-sync** — keep syncing automatically as files change.
- **Ignore deletions** — never propagate deletes (safe default for the NAS role).
- **Ignore patterns** — extra gitignore-style exclusion patterns.
- **Compression** — toggle transfer compression.
- **Delta transfer** — enabled by default for large files; see the
  [Delta Transfer Guide](https://github.com/albertsdk/hsync-server/blob/main/docs/delta-transfer.md)
  for details.
- **`.hsyncignore` editor** — edit ignore patterns for the selected folder.

### LAN tab
For **LAN Mode** (peer-to-peer on the same network, no server):

- **LAN mode** — enable peer discovery via mDNS.
- **Force master / Never master** — control master election for this device.
- **Require pairing** — only sync with explicitly paired peers.
- **LAN key** — shared secret for the LAN group (see *Secrets*).
- **NTP servers** — comma-separated list of SNTP servers used by the client in
  LAN mode to measure the clock offset used for chronological conflict
  resolution. Leave empty to use the built-in defaults
  (`pool.ntp.org`, `time.cloudflare.com`, `time.google.com`). Entries may
  carry a port override, e.g. `ntp.local:123`.

> Controls for features your installed `hsync` binary does not support are
> automatically disabled, with a tooltip explaining why.

## Running and watching a sync

1. Confirm your settings, then start the sync from the main window.
2. The file panel lists each file and its transfer status (queued, in
   progress, done, error); overall progress and throughput are shown live.
3. The log panel streams structured messages from the engine. You can hide or
   show it from the view options.
4. With watch / auto-sync enabled, the app keeps running and re-syncs on
   changes until you stop it.

## Secrets

API keys and LAN keys are entered through dedicated dialogs, never typed on a
command line. They are stored encrypted on disk (machine-derived key) and are
handed to the engine over a private channel, so they never appear in process
listings or logs. Use the key dialogs to replace a key at any time.

## Preferences

- **Theme** — switch between available light/dark themes.
- **Notifications** — enable desktop notifications for sync events.
- **Bandwidth limits** — cap upload/download throughput.
- **Language** — the UI is available in English, Italian, German, Spanish and
  French.

## Troubleshooting

- **A control is greyed out** — your `hsync` binary lacks that capability;
  rebuild/update the client to enable it.
- **TLS errors in Server Mode** — verify the URL and certificate; enable
  *Insecure* only on a trusted network for self-signed certificates.
- **Peers not found in LAN Mode** — ensure all devices are on the same subnet
  with mDNS allowed through the firewall, and share the same LAN key.

See the [client documentation](https://github.com/albertsdk/hsync-client/blob/main/docs/README.md) for the
underlying sync behaviour and modes.
