# FAQ — HSYNC Desktop

## How do I reset a folder's sync state?

A folder that keeps re-syncing, reports conflicts on files nobody edited, or
logs a database error has an inconsistent local sync history; resetting it makes
the next sync reconcile the folder from scratch. It clears only that folder's
merge bases and deletion markers — never the files, `.hsyncignore`, the settings,
the saved keys, the device identity or the trusted fingerprints.

The procedure and what to expect on the next cycle are in
[Using HSYNC Desktop → Reset the sync state](usage.md#reset-the-sync-state).

For a headless or service installation, the same operation is available from the
client CLI — see the
[client troubleshooting guide](https://github.com/albertsdk/hsync-client/blob/main/docs/troubleshooting.md#a-folder-keeps-re-syncing-or-reports-phantom-conflicts).

## Where is the sync state stored, and can I delete it manually?

The sync state lives outside the synced folder, in the device directory
(`<device dir>/syncstate/<uuid>.db`, one database per folder, plus a small
`index.db`). The folder itself only carries the `.hsyncfolder` identity marker.

**Do not delete those files by hand.** A running sync must be stopped first (the
client takes the folder's instance lock), `index.db` is shared between folders,
`HSYNC_STATE_DB` can make a single database hold every folder, and a file-level
delete can reset the wrong folder. Use the Desktop button, or `hsync state reset`
from the CLI: it deletes the folder's rows in one transaction and keeps the
folder/index rows. If the database is unreadable, the Desktop reports the error;
the CLI moves it aside with `hsync state reset --folder DIR --quarantine`.

## Why do my two devices not see each other?

In p2p Mode they must use the **same group name** and the **same share name**, and
be on the same network (or reach the same discovery server). A device with no
group only sees other no-group devices. The full checklist is in
[Troubleshooting → Devices are not found in p2p Mode](troubleshooting.md#devices-are-not-found-in-p2p-mode).

## Why does HSYNC warn that local files may be deleted?

The folder is not empty and the current settings allow deletions — p2p Mode with
**Prefer primary role** off, or a **Receive only** sync type. It is a warning
before anything happens, not an action. Choose **Keep deleted files**
(Settings → Sync → Deletions) and the warning disappears, because the app can
no longer delete anything; the status bar then shows a **Backup — deletions
kept** badge. See
[Warnings before and during a sync](usage.md#warnings-before-and-during-a-sync).

## How do I remove my settings and keys?

Quit the app and delete its settings entry (the path per OS is in
[Where settings are stored](configuration.md#where-settings-are-stored)): the next
launch starts from the setup wizard and asks for the keys again. Synced files and
the folder's sync state are left alone.
