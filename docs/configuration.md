# Configuration Reference

Every HSYNC Desktop setting lives in the GUI **Settings** dialog and is persisted
with Qt `QSettings`. This page is the single source of truth for the settings;
the [Usage Guide](usage.md) covers running a sync and the runtime prompts.

Open **Settings** from the main window (or the tray menu). The dialog is
organised into five tabs: **Sync**, **p2p**, **Server Mode**, **Log** and
**Appearance**. Controls for features your installed sync engine does not
support are automatically disabled, with a tooltip explaining why. On a fresh
install (no saved settings yet) the app starts in **p2p Mode**.

## Server Mode

For syncing against a central HSYNC server.

| Setting | Description |
|---------|-------------|
| Server URL | HSYNC server address, e.g. `https://my-nas:9753` |
| Bucket | Remote bucket name to sync into |
| API key | Account token (`hs_<id>_<secret>`); entered through a dedicated dialog (see [Secrets](usage.md#secrets)) |
| Server identity check | How the app checks the server identity: standard verification (default), ask on first use, accept automatically, require the saved identity, or don't verify. Passed as `HSYNC_SERVER_TRUST` |
| Certificate check | Skip verification or use a custom certificate file for a self-signed server |
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
| Enable p2p | Enable device discovery |
| Group name | Partition key for p2p discovery: devices only sync with peers using the exact same group name. Leave it empty to put this device in the "no group" partition — it then syncs only with other devices that also left it empty |
| Force primary role / Never become primary | Control which device takes the primary role |
| Require pairing | Only sync with explicitly paired devices |
| Shared password | Password shared by the devices in the p2p group; with a relay server it is also the relay credential |
| Relay server | Endpoint of an optional `boot/1` node for cross-network discovery (`host`, `host:port`, `[IPv6]`, `[IPv6]:port`); empty uses mDNS on the local network only. Passed as `HSYNC_BOOTNODE` (no scheme/path) |
| Relay identity check | How the app checks the relay server identity: ask on first use (default), accept automatically, require the saved identity, or don't verify. Passed as `HSYNC_BOOTNODE_TRUST` |
| Manage trusted servers & devices | List, add and remove the relay server, server and device fingerprints the client actually uses |
| Open the port on my router automatically | Open the primary port so devices reached through a relay server can connect (only takes effect with a relay server set) |
| Time servers | Comma-separated time servers (SNTP) for p2p clock-offset measurement; empty uses the built-in defaults. Entries may carry a port override, e.g. `ntp.local:123` |

**Force primary role and sync type.** *Force primary role* only applies to the
**Keep aligned (Send & Receive)** sync type, so the conflict is caught as soon as
it appears. Picking a one-way type (send-only or receive-only, Sync tab) while
p2p mode and *Force primary role* are both on offers to turn it off because it is
incompatible (accept jumps to the p2p tab); switching *Force primary role* on
while a one-way type is active offers to go back to the **Keep aligned (Send &
Receive)** type because they are incompatible (accept jumps to the Sync tab).
Declining either prompt keeps your choice and repeats the generic warning when
saving.

**Trust stores.** *Manage trusted servers & devices…* edits the client's
known-hosts (relay server and sync server) and known-devices stores directly —
there is no separate setting — so the GUI and the `hsync` CLI share the same
source of truth.

**Keyless runs.** Without a shared password the app confirms before starting:
devices are not authenticated and reads are open to anyone who can reach this
device. Set a shared password in the p2p tab to avoid the prompt; the
confirmation is requested on every start and is not a stored setting.

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
| Tooltips | Show or hide option tooltips |
| Launch at system startup | Start HSYNC minimized to the tray when you log in |

The interface language follows the system locale (English, Italian, German,
Spanish, French, Portuguese (Brazil), Chinese (Simplified), Russian, Dutch,
Polish, Japanese).

**Launch at system startup.** When enabled, the app registers a per-user
autostart entry for the platform — an XDG autostart file on Linux/BSD, a
LaunchAgent on macOS, a `Run` registry value on Windows — that launches
`hsync-desktop --minimized`, so the window stays in the tray at login. Disabling
the option removes the entry. The setting is a desktop preference only; it does
not start a sync (use **Auto-sync on startup** on the Sync tab for that).

## Where settings are stored

Settings are persisted by Qt `QSettings`; secrets (API and p2p keys) are stored
encrypted with a machine-derived key and handed to the engine over a private
channel, never on the command line. See [Secrets](usage.md#secrets).
