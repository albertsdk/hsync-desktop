# Key concepts

The words the app uses, in the order you meet them. Each entry links to the
client documentation for the full explanation; nothing here redefines the
protocol itself.

## Share name

A **share** is one folder kept in sync under a name — the folder name on an HSYNC
server, or the name peers use in p2p mode. Devices that must see the same content
use the **same share name**; the local directory behind it is **Local folder**
(*Settings → Sync*) and may differ between devices.

## Group (p2p)

The **p2p group name** is a partition key: devices discover and sync only with
devices that use the exact same group name. Leaving it empty puts the device in
the "no group" partition, which sees only other no-group devices. It is not a
secret — the shared password is.

## Primary and secondary role (p2p)

In p2p mode one device serves the files to the others: the **primary** device.
The others are **secondary**. *Prefer primary role* asks for that role and *Never
become primary* removes the device from the election; the status bar shows the
role once the election has decided it. The engine's own labels and log lines
still say "master" for this role. See
[p2p Mode](https://github.com/albertsdk/hsync-client/blob/main/docs/p2p-mode.md).

## Discovery server

An optional **HSYNC Bootnode** that only helps devices on different networks find
each other; it never carries or stores your files. With no discovery server the
app uses mDNS on the local network. See
[hsync-bootnode](https://github.com/albertsdk/hsync-bootnode/blob/main/docs/getting-started.md).

## Trust and fingerprints

Every server and device presents a certificate. The first time, the app asks
whether to trust its fingerprint and then pins it: a later change is reported as a
possible man-in-the-middle and asks again. The stores are shared with the `hsync`
CLI and editable from *Settings → p2p → Manage trusted servers & devices…*.

## Conflict copy

When two devices really change the same file at the same time, one version wins
and the other is kept next to it as `_conflicted_copy_`, so nothing is lost. See
[Conflict resolution](https://github.com/albertsdk/hsync-client/blob/main/docs/conflict-resolution.md).

## Sync state

Per folder, outside the synced directory, the app keeps a small database with the
merge bases and deletion markers. When it becomes inconsistent the folder keeps
re-syncing or reports phantom conflicts; resetting it is described in
[Using HSYNC Desktop → Reset the sync state](usage.md#reset-the-sync-state).

## Simulation Mode

A preview-only run: the app compares the two sides and shows the summary without
transferring or deleting anything. See
[Configuration → Sync](configuration.md#sync).
