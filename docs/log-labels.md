# Log Labels

> **For advanced users.** You do not need this page for normal use: the log panel
> is optional and most messages are shown to you as toasts and banners. Come here
> when you are reading the log to diagnose something — see
> [Troubleshooting](troubleshooting.md).

HSYNC Desktop runs the `hsync-client` engine as a subprocess and surfaces its
output in the in-app **Log** panel, so every client label can appear there.
The desktop also emits a couple of own markers for UI-level events. This page
lists what you can see.

> The complete, cross-project catalog (descriptions, color categories, and which
> project emits each label) lives in
> [`hsync-common/docs/log-labels.md`](https://github.com/albertsdk/hsync-common/blob/main/docs/log-labels.md).
> The full set of client labels is documented in
> [`hsync-client/docs/log-labels.md`](https://github.com/albertsdk/hsync-client/blob/main/docs/log-labels.md).

## Client labels (engine subprocess)

The desktop log panel shows whatever the underlying `hsync-client` engine
emits. See [the client label reference](https://github.com/albertsdk/hsync-client/blob/main/docs/log-labels.md)
for the full list and meanings — sync operations, preview (dry-run), p2p
client/master operations, and security/warning labels are all surfaced here.
These are the client's own strings: what the app calls the **primary** role
appears in them as `MASTER`, so `[NO MASTER]` means no primary device.

**Colors.** The panel renders the client's own palette, re-mapped to a light/dark-
friendly tone so nothing vanishes on either background; it is re-rendered when you
switch theme.

The security/warning labels in particular drive an in-app warning toast and a
desktop notification (the latter only while the window is in the background):

| Label | Desktop behavior |
|-------|------------------|
| `[NO MASTER]` | No master elected — shows a "no node will serve files" warning notification |
| `[FINGERPRINT CHANGED]` | Master cert changed — security warning notification |
| `[PAIRING NEEDED]` | Strict pairing required — notification |
| `[INSECURE MASTER]` | Insecure master refused — notification |
| `[MASTER CONFLICT]` | Two devices both prefer the primary role — warning notification |
| `[MASTER TAKEOVER]` | A peer that prefers the primary role took over — expected handover, logged only (no notification) |

## Desktop-only markers

These are emitted by the desktop itself (not part of the shared `ActionLabel`
set):

| Marker | Meaning |
|--------|---------|
| `[EVENT ERROR]` | The desktop's own prefix for an error event from the engine/UI layer |

## Related

- [Start, watch and stop a sync](sync-basics.md)
- [Warnings and notifications](warnings.md)
- [Client label reference](https://github.com/albertsdk/hsync-client/blob/main/docs/log-labels.md)
- [Canonical label catalog](https://github.com/albertsdk/hsync-common/blob/main/docs/log-labels.md)
