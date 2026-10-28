# Choose what happens to deleted files

Sync can either **delete files on the other devices** when you delete them here,
or **never delete anything**. This single choice is what most people care about,
so it is worth a moment.

<img src="assets/screens/05-settings-sync.png" alt="Settings, Sync tab, with the Deletions choice highlighted" width="640">

Open it from **Settings → Sync → Deletions**.

## The two choices

| Choice | What happens | Choose it when |
| ------ | ------------ | -------------- |
| **Apply deletions (propagate)** | Deleting a file on one device deletes it on the others, so every device stays identical. | You trust your devices and want a true mirror. |
| **Keep deleted files (backup)** | Nothing is ever deleted here: local deletions are not sent, and deletions coming from elsewhere are not applied. The folder only grows. | You want safety above all — an accidental delete never spreads. |

While **Keep deleted files** is active, the main window shows a **Deletions
kept** badge next to the status, so a device that never removes files says so.
Clicking the badge (or opening Settings) switches back; the app confirms first.

## Deletion protection (a separate safety net)

Independently of the choice above, the app can **pause a cycle that would delete
too many local files at once** — a guard against a stray delete wiping a folder.
You set the thresholds in **Settings → Advanced** (a maximum count and a maximum
percentage; `0` disables a rule). When the guard trips, the deletions are skipped,
a warning appears, and the sync keeps running; a later cycle retries them. See
[Warnings and notifications](warnings.md).

## Why you may be asked before starting

If the folder is not empty and the current settings **can** delete local files,
the app asks once before starting the first sync. That prompt is a heads-up, not
a change: enabling **Keep deleted files** — or choosing a one-way **Send only**
type — is what makes it stop asking. See
[Warnings and notifications → Warnings before a sync](warnings.md#warnings-before-a-sync).

## Related

- [Choose your sync type](choose-sync-type.md) — who sends and who receives.
- [Reset the sync state](reset-sync-state.md) if a folder keeps re-syncing.
