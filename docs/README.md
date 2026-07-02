# HSYNC Desktop — Documentation

HSYNC Desktop is a cross-platform graphical front-end for the HSYNC file
synchronization client. It does not implement sync itself: it drives the
bundled `hsync` client binary, builds its command line from a friendly settings
dialog, and shows live progress, transfers and logs in a native window with a
system-tray icon.

Use it when you want HSYNC's Server Mode or peer-to-peer LAN Mode without
touching the command line.

## Where to start

- **End user?** → [Download a binary](#install--quickstart) and run it — no build required.
- **Building from source?** → Follow the [developer instructions](#install--quickstart) below.
- **Need help with settings?** → See the [Usage Guide](usage.md).

## Install & quickstart

### For end users

Download the prebuilt binary for your platform from the
[Releases page](https://github.com/albertobasso/hsync-desktop/releases) (when
available). Extract the archive and run the `hsync-desktop` executable — it
bundles the HSYNC Client binary, so no additional installation is required.

> Prebuilt binaries are a planned feature and not yet available in every
> release. In the meantime, use the developer instructions below.

On first launch, open **Settings**, fill in your sync folder, bucket and mode
(Server or LAN), then start a sync. See [usage.md](usage.md) for the full
walkthrough.

### For developers (build from source)

```bash
cd hsync-desktop
poetry install          # first time only
poetry run hsync-desktop
```

Build a standalone binary with:

```bash
./compile.sh
# Binary output: dist/<os>-<arch>/hsync-desktop
```

## Documentation map

| Document | What it covers |
| -------- | -------------- |
| [usage.md](usage.md) | Configure connection, run and watch syncs, manage secrets, tray & themes. |

## Related projects

- [hsync-client](../../hsync-client/docs/README.md) — the sync engine this GUI drives.
- [hsync-server](../../hsync-server/docs/README.md) — the central server for Server Mode.
- [hsync-android](../../hsync-android/docs/README.md) — the Android app.
- [hsync-common](../../hsync-common/docs/README.md) — shared models and protocol.
