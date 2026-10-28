# Choose your sync type

The **Sync Type** decides which direction changes travel between this computer and
the others. It is the first setting to get right: everything else builds on it.

<img src="assets/screens/05-settings-sync.png" alt="Settings, Sync tab, with the Sync Type selector and the Deletions choice" width="640">

Open it from **Settings → Sync → Sync Type**.

## The three choices

| Sync Type | What happens | Choose it when |
| --------- | ------------ | -------------- |
| **Keep aligned (Send & Receive)** | Files move both ways so every device ends up with the same content. | Your everyday case: you edit files on any of your devices. |
| **Send only (to other devices)** | This computer only sends; changes made elsewhere never come back here. | This device is the source (a laptop you publish from, a camera folder). |
| **Receive only (from other devices)** | This computer only receives; local changes are not sent. | A kiosk, a display, or a machine where you never edit the files. |

## Keep aligned is the default, and usually the right answer

A two-way sync is what most people want: it is what makes two computers feel like
the same set of files. The two one-way types are for a deliberate one-way flow
and they reduce what the sync can do, so pick one only when you really mean it.

If you are in **p2p Mode** and **Prefer primary role** is on, a one-way type
conflicts with it: the app catches this and offers to turn it off (accepting jumps
to the p2p tab). The reverse also holds — turning **Prefer primary role** on while
a one-way type is active offers to go back to **Keep aligned**.

## A one-way type and deletions

With **Send only** or **Receive only**, deletions travel in one direction only.
If you have ever worried about losing files, pair a one-way type with the
**Keep deleted files** policy — see
[Choose what happens to deleted files](choose-deletion-policy.md).

## Related

- [Deletions](configuration.md#sync) — the other half of "what happens to my files".
- [Choose how your devices connect](choose-connection.md) — server or p2p.
