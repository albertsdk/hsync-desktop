# Managing multiple shares

A **share** is one sync configuration: a local folder, the way it connects
(Server Mode or p2p), and every sync setting. HSYNC Desktop keeps several named
shares and lets you switch between them from the window header; only one share
syncs at a time.

## What a share contains

- the **local folder** that is synced;
- the **connection mode**: Server Mode (a server URL) or p2p (a group);
- the sync parameters: direction, deletion policy, filters, bandwidth limits,
  advanced tuning, the log file and the secrets (API key, group password).

Appearance, language, notifications, the log panel visibility and the update
check are **not** per-share: they apply to the whole application.

## The share selector

The share name sits in the header, next to a small dropdown arrow:

- click the **name or the arrow** to open the list of shares;
- the list shows each share with its mode icon (p2p or server), the active one
  ticked; hover for its folder, bucket, direction and target;
- the **folder icon** opens the active share's folder in your file manager.

While nothing is configured yet, the header says so and there is no selector; the
first share is created the first time you save the wizard or the Settings dialog.

## Create a share

1. Open the selector and choose **New share…**.
2. Give it a **name** and pick a **folder**.
3. The new share starts as a copy of the current one, and the Settings dialog
   opens so you can adjust it.

The name is only a label: it can contain spaces and capital letters. The
**bucket** (the identifier the peers/servers use) is derived from the name when
the share is created and can be changed later in the Settings dialog.

## Switch share

Select another share in the list and the whole window follows it: header, badges,
file list and log.

If a sync is running, the app asks first; on confirmation it stops the running
sync, saves the current share's settings, loads the selected share and **stays
stopped**. Press **Start** to sync the new share.

## Manage shares

**Manage shares…** lists every share and lets you:

- **New** — as above;
- **Duplicate** — copy a share (with a new name and a new folder);
- **Rename** — change the label only; the bucket is untouched;
- **Delete** — remove the share's configuration.

The four buttons carry the app's own icons and no trailing ellipsis (the header
menu keeps its "…", the markup for an action that opens a dialog). **Rename**
and **New**/**Duplicate** open a prompt wide enough to show its title, with the
action's verb on the confirm button; **Close** closes the list.

Deleting a share **never touches your files**. It offers a checked box to also
*clear the local sync state* of its folder: this forgets the folder's merge bases
(no data is lost, but the next sync may re-download everything). Keeping the
state lets a later re-add of the same folder resume quickly; clearing it avoids
leaving unused state behind.

## One folder per share

Each share must use its **own folder**: a folder owns one sync database and one
lock, so two shares pointing at the same folder would interfere. To sync a
different folder, create a new share (or change the folder of the current one in
the Settings dialog). To keep using a folder you removed, re-add a share for it.

## See also

- [Choose how your devices connect](choose-connection.md)
- [Set up with the wizard](setup-wizard.md)
- [Configuration](configuration.md) — every setting in the Settings dialog.
- [Reset sync state](reset-sync-state.md) — reconciling a folder from scratch.
