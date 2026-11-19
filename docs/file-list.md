# The file list

The file list is the table in the middle of the main window. It shows exactly what
the sync works on, one row per file or folder, and it doubles as the way to open,
move and act on your files.

<img src="assets/screens/19-file-context-menu.png" alt="The right-click menu on a file row, grouped by action" width="200">

## Columns

Each row starts with an icon that carries the file type and, when the row has an
operation, its glyph: `↑` upload, `↓` download, `✕` a deleted row, `⇄` a rename.
The columns are:

| Column | Meaning |
| ------ | ------- |
| **Name** | The file or folder, with the icon above. Always shown, always first. |
| **Size** | The size on disk. For a folder, the sum of the files it contains; its item count is shown in the tooltip and in the properties pane. |
| **Type** | The kind of file (hidden until you enable it). |
| **Modified** | The last modification date. |
| **Progress** | A bar with the percentage while a transfer runs. A file you are sending reaches 100% only once the other device has received it. |
| **Status** | The planned action ("To upload" / "To download" / …) or the result ("Syncing", "Synced"). |
| **Time left** | The estimated time left for a running transfer, once the rate is known (hidden until you enable it; blank until the first samples arrive). |
| **Speed** | The live transfer rate (hidden until you enable it). |

**Type**, **Time left** and **Speed** are hidden by default: the icon conveys the
type and the operation, and the two live metrics only say something while a
transfer runs. Turn them on from the header menu, which lists the columns in the
order you arranged them (**Name** stays first).
You can drag a divider to resize a column, drag a header to reorder the columns,
and double-click a divider to fit a column to its content. Widths, order and
visible columns are remembered across runs; **Reset columns** in the header menu
restores the default layout — order, visibility and fitted widths. An active sort
stays: it is a view choice, never persisted.

Files show their precise planned action, while a folder shows a neutral aggregate
("To sync") whose tooltip breaks down the mixed operations. A folder with no files
at all cannot aggregate anything, so it reports its own state instead: **Synced**
once every device holds it, **To upload** / **To download** while one side is
still missing it.

## Pending items

**Pending** in the list bar lists every file that still has work to do anywhere in
the share, one row per file with its path (for example `docs/report.pdf`). The
number on the button is the total; **Only changes** counts the same kind of work
per folder, so the two always agree.

The list is a view of the same table: the columns, the actions and the name filter
work as usual. **Only changes** is off while it is open (the list is already only
changes). Double-click a row to leave the list, open that file's folder and select
it — useful for a file that has not been downloaded yet. Leaving the list (the
button again, or opening a folder) restores the folder and the rows you had
selected.

## Search

The magnifier in the list bar (or `Ctrl+F`, `Cmd+F` on macOS) searches **this
folder and everything under it**: every file whose name or path contains what
you typed is listed with its path relative to the folder, so a match three
levels down needs no drilling. Capitalisation is ignored.

The results are the same table — columns, actions and **Only changes** apply —
and double-clicking a result takes you to its folder with the row selected.
Clearing the field, closing it (the magnifier again, or `Esc` while it has focus),
or opening a folder returns to the browser. The search is a view: it changes
nothing on disk and is not remembered after a restart.

## Hidden files

Files and folders whose name starts with a dot are hidden from the list. Enable
**Show hidden files** from the header menu to see them — this changes only the
list, not what is synchronised.

## Only changes

**Only changes** in the list bar (the magnifier next to the breadcrumb) hides the
rows with nothing pending: files already in sync, entries the engine has not
classified yet and finished transfers stay out of the way, while transfers,
renames, deletions and errors remain. The number next to the label is how many
rows at the current folder carry pending work, so the toggle doubles as a summary.

The choice is remembered across restarts and applies to the folder you are
browsing, like the rest of the list. When it hides everything, the list says
nothing is pending in that folder instead of showing an empty table — and it says
*not compared yet* instead, as long as the app has not classified the folder (the
first comparison runs on its own when the app connects), so an empty list never
claims the folder is up to date when its state is simply unknown. While a
comparison is running it says *comparing with the other devices*: that pass may
still find work, so it outranks both messages. It changes
only what you see: actions act on the visible rows, and the folder size and the
status bar keep counting every file.

## The shared-folder size

The **Shared: X / Y** row of the status bar's **Details ▾** popover shows the
shared folder's size on this device (**X**) and the size of the whole share
(**Y**, a dash while it is not yet known). The whole-share value is approximate when the two sides disagree on a
file's size.

## Right-click actions

Right-click a row for the actions on that file or folder, grouped by kind:

| Group | Actions |
| ----- | ------- |
| Open | **Open**, **Open containing folder**, **Open with…** |
| Send/Receive | **Send now**, **Receive now** (one-shot, while no sync is running) |
| Copy | **Copy to…**, **Copy path**, **Copy relative path** |
| Rename | **Rename** |
| Destructive | **Move to trash** |
| Properties | **Properties** |

**Copy path** puts the absolute path (in your system's form, e.g. backslashes on
Windows) on the clipboard; **Copy relative path** copies the path inside the
shared folder. The same two commands are in the **File** menu, where they are
reachable from the keyboard.

**Rename** and **Move to trash** are greyed out for a row the engine is still
working on (a file that is being transferred or is waiting to be, and folders
that contain any) — renaming or deleting such a file mid-transfer would race the
sync and could recreate it, so the action stays disabled until the row is
resting. **Copy to…** is disabled while a file is coming in (there is nothing to
copy yet) and for folders that are still transferring (the copy would catch them
mid-way); a file that is uploading can still be copied — the local copy is what
you asked for. **Rename** also refuses a new name that matches a file the sync
is still working on (or a folder containing one): the selected row may be
resting while the name you type is not. The same rules apply to the **File**
menu entries; **Open**, **Copy path** and **Properties** are always available.

Folders created by a remote peer appear in the list as **Synced** (green), like
the files inside them.

## Import by drag & drop

You can add files to the share by dragging them from your file manager into the
file list:

- drop onto a **folder row** to import into that folder, or onto the empty area
  to import into the folder you are currently browsing;
- a plain drop **copies** the files into the shared folder; hold **Shift** to
  **move** them instead (the originals are deleted, so the app asks first);
- if a file with the same name is already there, a prompt offers **Replace**,
  **Keep both** (the incoming file is saved as `name (1).ext`) or **Skip**, with
  an **Apply to all** checkbox when several files clash.

While the copy runs, an indicator covers the file list and says what the app is
doing: first *Analysing the dropped items…*, then *Copying into the shared
folder…* with the number of files and the size already written. When the size can
be measured the bar shows a real percentage; otherwise it stays a busy bar, so it
never promises progress it cannot know. **Cancel** stops the copy at the next
file — whatever was already written stays in the shared folder.

The files are written into the shared folder and the sync engine picks them up
automatically; a toast reports the outcome and the list refreshes, keeping the
status the other files already had. The shared folder's own engine files
(`.hsyncfolder`, `.hsyncignore`, …) cannot be dropped in, and the shared folder
cannot be dropped onto itself.

## Related

- [Start, watch and stop a sync](sync-basics.md) — Send now / Receive now in
  context.
- [Warnings and notifications](warnings.md) — what the statuses tell you.
