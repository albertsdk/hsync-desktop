# Key concepts

The words the app uses, in the order you meet them, explained in plain language.
Each entry points to the page that goes deeper.

## Share

A **share** is one folder kept in sync, under a name — the folder name on an HSYNC
server, or the name devices use in p2p Mode. Devices that must see the same
content use the **same share name**. The folder on *this* computer can be
somewhere else: that location is the **Local folder** (*Settings → Sync*).

## Connection mode

**Server Mode** syncs through a central **HSYNC server**; **p2p Mode** syncs your
devices directly, with no server. See
[Choose how your devices connect](choose-connection.md).

## Group (p2p Mode)

The **p2p group name** is a way to keep separate sets of devices apart: devices
see and sync only with other devices using the **exact same group name**. Leaving
it empty puts the device in the "no group" set, which sees only other no-group
devices. It is not a secret — the shared password is.

## Primary and secondary role (p2p Mode)

In p2p Mode one device serves the files to the others: the **primary**. The others
are **secondary**. **Prefer primary role** asks for that role and **Never become
primary** removes the device from the election; the status bar shows the role once
it is decided. (The engine's own log lines still say "master" for this role.)

## Discovery server

An optional helper (an **HSYNC Bootnode**) that only lets devices on different
networks find each other. It never carries or stores your files. With no discovery
server, the app uses mDNS on the local network.

## Trust and fingerprints

Every server and device proves its identity with a certificate. The first time,
the app asks whether to trust its **fingerprint** — a short code that names that
identity — and remembers it; a later change is reported as a possible
man-in-the-middle and asks again. See
[Trust, fingerprints and identity checks](choose-trust.md).

## Conflict copy

When two devices really change the same file at the same time, one version wins
and the other is kept next to it as `_conflicted_copy_`, so nothing is lost. See
[conflict resolution](https://github.com/albertsdk/hsync-client/blob/main/docs/conflict-resolution.md).

## Sync state

For each folder, outside the synced directory, the app keeps a small database of
merge bases and deletion markers. When it becomes inconsistent the folder keeps
re-syncing or reports phantom conflicts; see
[Reset the sync state](reset-sync-state.md).

## Simulation Mode

A preview-only run: the app compares the two sides and shows the summary without
transferring or deleting anything. See
[Start, watch and stop a sync](sync-basics.md#start-a-sync).
