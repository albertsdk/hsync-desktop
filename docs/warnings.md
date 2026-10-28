# Warnings and notifications

HSYNC Desktop tells you what is happening in four places, from the least to the
most intrusive. Knowing which is which saves you from chasing problems that are
not there.

<img src="assets/screens/18-notifications.png" alt="A transient toast and a persistent warning banner in the main window" width="640">

## How the app tells you things

| Where | What it is | Stays until |
| ----- | ---------- | ----------- |
| **Toast** (bottom-right) | A transient message: searching for devices, connection result, "nothing to sync", a Send/Receive while a sync is running. | It auto-hides. |
| **Warning / error banner** | Something you should read: a warning the sync keeps running through, or an error. An icon and a title make the severity recognisable without relying on colour. | You close it; it survives a new sync. |
| **Desktop notification** | The same warning or error, shown by the operating system **only while the window is in the background**. | It follows your system notification settings. |
| **Log panel** | Every message, including the ones shown as toasts. | Until you clear it. |

Errors and warnings always appear **in the app window**, whatever your
notification preference; the preference only controls the operating-system
notifications.

## Is everything in sync?

The status bar answers the question the connection dot cannot: **are the files
the same everywhere?** It reads one of:

- `Checking…` — a comparison is running.
- `Waiting for inventory` — a device is connected but has not yet said what it
  holds.
- `No devices` — there is nothing to compare against yet.
- `All files in sync` — nothing is pending.
- `2 to download · 1 to send` (or `3 change(s) pending` for deletes and renames) —
  work is left.

A device that serves the share as **primary** answers for the whole group: with
more than one device connected, the counts are those of the device **furthest
behind**, so `All files in sync` means every device is aligned. Its tooltip lists
each device with what it still has to receive (`↓`) or send (`↑`), and its file
list shows `Synced · 2/3` for a file that only some devices have.

## Warnings during a sync

A **warning** is something the sync keeps running through, for example:

- the file watcher degraded to polling because the system ran out of inotify
  resources;
- a discovery server could not be reached while device discovery retried;
- free disk space fell below the configured reserve;
- the shared folder is no longer accessible (drive unplugged, network mount
  dropped).

A warning that heals itself — real-time changes queued faster than they could be
sent, a file that kept changing while it was being sent, files that could not be
read and are retried by the next scan — shows as a brief toast instead and never
as a notification. Each distinct warning is reported once per ten minutes, so a
condition that comes and goes does not fill the screen; the log keeps every
occurrence.

## Warnings before a sync

Four checks can stop a start or a deletion phase. This is what they mean and
what to do:

- **File Deletion Risk** — the folder is not empty and the current settings can
  delete local files. It appears in p2p Mode while **Prefer primary role** is off
  (local files missing on the primary device may be removed here) and with the
  **Receive only** sync type (deletions made elsewhere apply here). Check the
  folder and confirm to continue; enabling **Prefer primary role** or the one-way
  **Send only** type is what makes it stop asking. Simulation Mode and the
  **Keep deleted files** policy skip it: neither can remove a local file.
  See [Choose what happens to deleted files](choose-deletion-policy.md).
- **Deletions skipped (deletion protection)** — a cycle wanted to delete more
  local files than **Max deletions per cycle** or **Max deletions percent** allow.
  Those deletions were skipped and the sync kept running; a later cycle retries
  them. If the removal is expected, raise the limits in *Settings → Advanced*;
  otherwise check the primary device or the source first.
- **No shared password** — with an empty p2p password the app confirms before
  starting, because reads are open to anyone who can reach this device. Set the
  password in the p2p tab to stop the prompt; see [Secrets](secrets.md).
- **A sync plan awaits confirmation** — an automatic start (auto-sync on startup
  or launch at login) stops when the plan it computed would delete files:
  nothing is applied and the app says so (under **Synchronisation events** in
  *Settings → General → Notifications*). Open the window and use
  **Preview changes** or **Start** to review that plan and confirm it. See
  [Preview changes without starting a sync](sync-basics.md#preview-changes-without-starting-a-sync).

## Trust prompts while running

While a p2p sync runs, the app may prompt you when a device presents an
unrecognised or changed certificate fingerprint:

- **Pairing required** — strict pairing refuses a first-seen fingerprint. Trust it
  (after verifying it out of band) or ignore it.
- **Fingerprint changed** — a previously pinned device now presents a different
  fingerprint, possibly a man-in-the-middle. Trust the new fingerprint, forget the
  stored key, or ignore it.

Accepting a fingerprint pins it in the client's trust store, so the app and the
`hsync` command line see the same keys. The full explanation is in
[Trust, fingerprints and identity checks](choose-trust.md).

## Badges in the window

- **Simulation — no changes** — Simulation Mode is on; runs only preview.
- **Deletions kept** — the **Keep deleted files** policy is active.
- **— Simulation** in the title bar while Simulation Mode is on.

## Controlling notifications

In **Settings → General → Notifications** you can switch system notifications off
entirely, and choose which events raise one: **Errors**, **Warnings**,
**Connection problems**, **Synchronisation events**, **Devices and role changes**.
The switches are greyed out while system notifications are off. In-app toasts and
banners are not affected.

## Related

- [Log Labels](log-labels.md) — the messages the log panel can show.
- [Troubleshooting](troubleshooting.md) — the common symptoms and what to check.
