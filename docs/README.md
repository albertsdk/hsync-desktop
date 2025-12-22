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

- [HSYNC Common](https://github.com/albertobasso/hsync-common/blob/main/README.md) - Shared models, constants, and utilities used by the client
- [HSYNC Client](https://github.com/albertobasso/hsync-client/blob/main/README.md) - Sync client (Server Mode and LAN/P2P Mode)
- [HSYNC Server](https://github.com/albertobasso/hsync-server/blob/main/README.md) - Central synchronization server (Server Mode)
- [HSYNC Android](https://github.com/albertobasso/hsync-android/blob/main/docs/README.md) — the Android app *(in development)*.

> **Note:** The desktop GUI (`HSYNC Desktop`) and the Android app (`HSYNC Android`)
> are still under active development and are not yet ready for production use.
