# Reset the sync state

When a folder keeps re-syncing, reports conflicts on files nobody edited, or the
log shows a database error, the folder's local **sync state** is inconsistent.
Resetting it makes the next sync reconcile the folder from scratch.

Open **Settings → Sync → Advanced options → Reset sync state…**. The control is
disabled while a sync runs, so stop the sync first.

## What to expect on the next cycle

- every file is read and hashed again, so the first sync is slower;
- files that are identical on both devices are **not** transferred;
- differences are resolved normally, and a conflict copy is kept when both sides
  changed;
- files deleted shortly before the reset can come back, because the deletion
  history is forgotten.

## What it never touches

The reset clears only the folder's internal version and deletion state. It never
touches your files, `.hsyncignore`, the settings, the saved keys, the device
identity or the trusted fingerprints.

If the state file is unreadable, the app reports the error instead of guessing.

> **Advanced / command line.** From a headless installation the same operation is
> available with `hsync state reset --folder DIR --quarantine`, which moves the
> unreadable state aside so the folder starts from scratch.

## Related

- [FAQ — Where is the sync state stored?](faq.md#where-is-the-sync-state-stored-and-can-i-delete-it-manually)
- [Troubleshooting](troubleshooting.md)
