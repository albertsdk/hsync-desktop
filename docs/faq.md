# FAQ — HSYNC Desktop

## How do I reset a folder's sync state?

When a folder keeps re-syncing, reports conflicts on files nobody edited, or the
log shows a database error, its local sync history is inconsistent. Reset it so
the next sync reconciles the folder from scratch:

1. Stop the sync (the button is disabled while it runs).
2. Enable **Show advanced options** in General.
3. Open **Settings → Sync → Advanced options → Reset sync state…** and confirm.

The reset clears only that folder's merge bases and deletion markers. It never
touches the synced files, `.hsyncignore`, the settings, the saved keys, the
device identity or the trusted fingerprints. On the next sync every file is
scanned and hashed again (a slower first cycle); files that are identical on
both sides are not transferred; differences are resolved normally with a
conflict copy when both sides changed; and deletions made shortly before the
reset can come back, because the deletion markers were forgotten.

The full procedure and caveats are in
[Using HSYNC Desktop → Reset the sync state](usage.md#reset-the-sync-state).

For a headless or service installation, the same operation is available from the
client CLI: stop the sync, then run `hsync state reset --folder <dir>` (add
`--quarantine` to move an unreadable database aside). See the
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
folder/index rows. If the database is unreadable, the Desktop already moves it
aside instead of failing (the CLI does the same with `--quarantine`).
