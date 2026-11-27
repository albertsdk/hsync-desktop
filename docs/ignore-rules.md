# Ignore files you do not want to sync

Some files should stay on this computer: build output, caches, a `.DS_Store`, a
local log. You exclude them with a pattern file, and HSYNC treats an excluded file
as if it were not there — it is never uploaded, downloaded or deleted.

Patterns come from two places, applied together:

- the folder's **`.hsyncignore`** file, edited from **Settings → Sync →
  What to sync → Ignore rules…** (or with any text editor, at the root of the
  shared folder);
- the **Extra ignore patterns** field in the same group, for a few one-off
  patterns you do not want in the file.

## The patterns

The syntax is the one `.gitignore` uses:

| Pattern | Matches |
| ------- | ------- |
| `*.log` | every file ending in `.log`, in any folder |
| `/build/` | the `build` folder at the root of the shared folder only |
| `cache/` | a `cache` folder at any depth |
| `secret.txt` | that name, at any depth |
| `**/*.tmp` | every `.tmp` file, at any depth |
| `!important.log` | re-include a file an earlier pattern excluded |

Rules of thumb:

- a pattern without `/` matches a **name** anywhere in the tree;
- a leading `/` anchors it to the root of the shared folder;
- a trailing `/` matches **folders** only, so `cache/` never matches a file called
  `cache`;
- `#` starts a comment and a blank line is ignored;
- once a file is excluded, `!` can bring it back — the last matching pattern wins.

A minimal file looks like this:

```text
# Build output and local caches
/build/
*.log
!keep.log
```

## What it does not do

- It never **deletes** anything: an excluded file stays where it is, on this
  computer and on the others.
- It does not hide files from the file list. To hide dot-files there, use the
  list's own **Show hidden** toggle (see [The file list](file-list.md)).
- It does not stop a file from being **restored** where the other devices already
  have it — an exclusion is not a deletion.

## When to re-check it

A pattern takes effect at the next sync start. If a file you expected to stay
local was transferred, the pattern did not match: run
**Sync → Compare** after the change to see what the engine still plans to do, and
remember that a folder is matched by its name, not by its contents.

## Related

- [The Sync settings](settings-sync.md) — the group the editor is opened from.
- [The file list](file-list.md) — what the window shows, and hidden files.
- [Reset the sync state](reset-sync-state.md) — when the history, not the rules,
  is what needs rebuilding.
