# The file list

The file list is the table in the middle of the main window. It shows exactly what
the sync works on, one row per file or folder, and it doubles as the way to open,
move and act on your files.

<img src="assets/screens/19-file-context-menu.png" alt="The right-click menu on a file row, grouped by action" width="200">

## Columns

Each row shows the file's icon next to its name, then:

| Column | Meaning |
| ------ | ------- |
| **Name** | The file or folder, with its type icon. Always shown, always first. |
| **Direction** | `↑` upload, `↓` download, `✕` a deleted row, `⇄` a rename. Blank when there is no operation. |
| **Size** | The size on disk. |
| **Type** | The kind of file (hidden until you enable it). |
| **Modified** | The last modification date. |
| **Progress** | A bar with the percentage while a transfer runs. |
| **Status** | The planned action ("To upload" / "To download" / …) or the result ("Syncing", "Synced"). |
| **Estimated Time** | The estimated time left for a running transfer. |
| **Speed** | The live transfer rate (hidden until you enable it). |

**Type** and **Speed** are hidden by default; turn them on from the header menu.
You can drag a divider to resize a column, drag a header to reorder the columns,
and double-click a divider to fit a column to its content. Widths, order and
visible columns are remembered across runs; **Reset columns** in the header menu
restores the default layout.

Files show their precise planned action, while a folder shows a neutral aggregate
("To sync") whose tooltip breaks down the mixed operations.

## Hidden files

Files and folders whose name starts with a dot are hidden from the list. Enable
**Show hidden files** from the header menu to see them — this changes only the
list, not what is synchronised.

## The shared-folder size

The status bar's **Shared: X / Y** indicator shows the shared folder's size on
this device (**X**) and the size of the whole share (**Y**, a dash while it is not
yet known). The whole-share value is approximate when the two sides disagree on a
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

Folders created by a remote peer appear in the list as **Synced** (green), like
the files inside them.

## Related

- [Start, watch and stop a sync](sync-basics.md) — Send now / Receive now in
  context.
- [Warnings and notifications](warnings.md) — what the statuses tell you.
