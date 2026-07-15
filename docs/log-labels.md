# Log Labels

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
for the full list and meanings — sync operations, preview (dry-run), LAN
client/master operations, and security/warning labels are all surfaced here and
colored by the same categories.

The security/warning labels in particular drive desktop notifications:

| Label | Desktop behavior |
|-------|------------------|
| `[NO MASTER]` | No master elected — shows a "no node will serve files" warning notification |
| `[FINGERPRINT CHANGED]` | Master cert changed — security warning notification |
| `[PAIRING NEEDED]` | Strict pairing required — notification |
| `[INSECURE MASTER]` | Insecure master refused — notification |
| `[MASTER CONFLICT]` / `[MASTER TAKEOVER]` | Master election conflict — notification |

## Desktop-only markers

These are emitted by the desktop itself (not part of the shared `ActionLabel`
set):

| Marker | Meaning |
|--------|---------|
| `[NO MASTER]` | Surfaced from the engine's `no_master` structured event (same meaning as the client label) |
| `[EVENT ERROR]` | The desktop's own prefix for an error event from the engine/UI layer |

## Related

- [Usage](usage.md)
- [Client label reference](https://github.com/albertsdk/hsync-client/blob/main/docs/log-labels.md)
- [Canonical label catalog](https://github.com/albertsdk/hsync-common/blob/main/docs/log-labels.md)
