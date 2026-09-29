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

Open **Settings**. The dialog is organised into tabs (Sync, Server Mode, p2p,
Log and Appearance); the connection settings are described below.

### Server tab
For **Server Mode** (sync against a central HSYNC server):

- **Server URL** — e.g. `https://my-nas:9753`.
- **Bucket** — the remote bucket name to sync into.
- **API key** — click to enter or replace it (see *Secrets* below).
- **CA certificate** — path to a custom CA for a self-signed server (optional).
- **Server trust policy** — how the client authenticates the server certificate:
  *Standard CA validation* (the default, for a public-CA or reverse-proxy
  server), *Ask on first use*, *Accept new*, *Require a pin* or *No
  verification*. Passed as `HSYNC_SERVER_TRUST`. For a self-signed server pin
  the certificate through *Manage trusted keys… → Servers*, or choose *Ask* /
  *Accept new*.
- **Insecure** — accept any certificate (use only on trusted networks;
  equivalent to *No verification*).

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

### p2p tab
For **p2p Mode** (peer-to-peer, no server):

- **p2p mode** — enable peer discovery.
- **Force master / Never master** — control master election for this device.
- **Require pairing** — only sync with explicitly paired peers.
- **p2p key** — shared secret for the p2p group (see *Secrets*). With a bootnode it
  is also the bootnode credential: set it to the same key the bootnode operator
  configured, so the client can authenticate to a protected bucket or a private
  node.
- **Bootnode (optional)** — hostname of a `boot/1` bootstrap node, for syncing
  with devices that are **not** on the same local network. Leave it empty to use
  mDNS discovery on the local network only; the hostname is passed to the client
  as `HSYNC_BOOTNODE` (a bare host: no scheme and no port).
- **Bootnode trust policy** — how the client authenticates the bootnode:
  *Ask on first use* (the default), *Accept new*, *Require a pin* or *No
  verification*. Passed as `HSYNC_BOOTNODE_TRUST`.
- **Manage trusted keys…** — open a dialog that lists and edits the trust stores
  the client actually uses: the bootnode and sync-server known-hosts stores and
  the p2p known-peers store. You can add, remove or refresh pins there; the
  accepted fingerprints live in the client's stores (not in a separate setting),
  so the GUI and the `hsync` CLI share the same source of truth.
- **Map port with UPnP** — let the client map its master TCP port on the router
  so peers reached through a bootnode can dial it. It only takes effect when a
  bootnode is set; without a mapping the device stays slave-only.
- **NTP servers** — comma-separated list of SNTP servers used by the client in
  p2p mode to measure the clock offset used for chronological conflict
  resolution. Leave empty to use the built-in defaults
  (`pool.ntp.org`, `time.cloudflare.com`, `time.google.com`). Entries may
  carry a port override, e.g. `ntp.local:123`.

> Controls for features your installed `hsync` binary does not support are
> automatically disabled, with a tooltip explaining why.

While a p2p sync is running, the app may prompt you when a device presents an
unrecognised or changed certificate fingerprint (the terminal-free equivalent
of the client's trust checks):

- **Pairing required** — strict pairing refuses a first-seen fingerprint. Trust
  it (after verifying it out of band) or ignore it.
- **Fingerprint changed** — a previously pinned device now presents a different
  fingerprint, possibly a man-in-the-middle. Trust the new fingerprint, forget
  the stored key, or ignore it.

Accepting a fingerprint pins it in the client's trust store, so both the app
and the `hsync` CLI see the same keys.

## Running and watching a sync

1. Confirm your settings, then start the sync from the main window.
2. The file panel lists each file and its transfer status (queued, in
   progress, done, error); overall progress and throughput are shown live.
3. The log panel streams structured messages from the engine. You can hide or
   show it from the view options.
4. With watch / auto-sync enabled, the app keeps running and re-syncs on
   changes until you stop it.

## Secrets

API keys and p2p keys are entered through dedicated dialogs, never typed on a
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
- **Peers not found in P2P Mode** — ensure all devices are on the same subnet
  with mDNS allowed through the firewall, and share the same p2p key. For
  devices on different networks, set a **Bootnode** in the p2p tab.

See the [client documentation](https://github.com/albertsdk/hsync-client/blob/main/docs/README.md) for the
underlying sync behaviour and modes.
