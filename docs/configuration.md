# Configuration Reference

Every HSYNC Desktop setting lives in the GUI **Settings** dialog and is persisted
with Qt `QSettings`. This page is the single source of truth for the settings;
the [Usage Guide](usage.md) covers running a sync and the runtime prompts.

Open **Settings** from the main window (or the tray menu). The dialog is
organised into five tabs: **Sync**, **Server Mode**, **p2p**, **Log** and
**Appearance**. Controls for features your installed `hsync` binary does not
support are automatically disabled, with a tooltip explaining why.

## Server Mode

For syncing against a central HSYNC server.

| Setting | Description |
|---------|-------------|
| Server URL | HSYNC server address, e.g. `https://my-nas:9753` |
| Bucket | Remote bucket name to sync into |
| API key | Account token (`hs_<id>_<secret>`); entered through a dedicated dialog (see [Secrets](usage.md#secrets)) |
| Server trust policy | How the client authenticates the server certificate: standard CA validation (default), ask on first use, accept new, require a pin, or no verification. Passed as `HSYNC_SERVER_TRUST` |
| SSL verification | Skip or use a custom CA certificate for a self-signed server |
| HTTP timeout | Request timeout in seconds |

## Sync

For the local folder and the transfer behaviour.

| Setting | Description |
|---------|-------------|
| Local folder | Directory to keep in sync |
| Watch / auto-sync | Keep syncing automatically as files change |
| Re-sync interval | Force a full sync every N seconds |
| Ignore deletions | Never propagate deletes (backup mode) |
| Ignore patterns | Extra gitignore-style exclusion patterns |
| `.hsyncignore` editor | Edit ignore patterns for the selected folder |
| Compression | Toggle transfer compression |
| Delta transfer | Rsync-style block sync for large files (enabled by default) |

## p2p

For peer-to-peer sync with no server. See the
[client p2p guide](https://github.com/albertsdk/hsync-client/blob/main/docs/p2p-mode.md)
for the underlying behaviour.

| Setting | Description |
|---------|-------------|
| Enable p2p | Enable peer discovery |
| Force master / Never master | Control master election for this device |
| Require pairing | Only sync with explicitly paired peers |
| p2p key | Shared secret for the p2p group; with a bootnode it is also the bootnode credential |
| Bootnode | Endpoint of an optional `boot/1` node for cross-network discovery (`host`, `host:port`, `[IPv6]`, `[IPv6]:port`); empty uses mDNS on the local network only. Passed as `HSYNC_BOOTNODE` (no scheme/path) |
| Bootnode trust policy | How the client authenticates the bootnode: ask on first use (default), accept new, require a pin, or no verification. Passed as `HSYNC_BOOTNODE_TRUST` |
| Manage trusted keys | List, add and remove the bootnode, server and peer fingerprints the client actually uses |
| Map port with UPnP | Map the master port so peers reached through a bootnode can dial it (only takes effect with a bootnode set) |
| NTP servers | Comma-separated SNTP servers for p2p clock-offset measurement; empty uses the built-in defaults. Entries may carry a port override, e.g. `ntp.local:123` |

**Trust stores.** *Manage trusted keys…* edits the client's known-hosts
(bootnode and sync server) and known-peers stores directly — there is no separate
setting — so the GUI and the `hsync` CLI share the same source of truth.

## Log

| Setting | Description |
|---------|-------------|
| Verbose output | Enable verbose (debug-level) logging |
| Quiet mode | Suppress non-warning output |
| Log file | Path to the log file |
| Show log panel | Toggle the in-app log viewer |

The action labels the log panel can show are listed in
[Log Labels](log-labels.md).

## Appearance

| Setting | Description |
|---------|-------------|
| Theme | Light or Dark |
| Notifications | Enable or disable desktop push notifications |

The interface language follows the system locale (English, Italian, German,
Spanish, French).

## Where settings are stored

Settings are persisted by Qt `QSettings`; secrets (API and p2p keys) are stored
encrypted with a machine-derived key and handed to the engine over a private
channel, never on the command line. See [Secrets](usage.md#secrets).
