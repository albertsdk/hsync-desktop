# HSYNC Desktop — Documentation

HSYNC Desktop is a cross-platform graphical front-end for the HSYNC file
synchronization client. It does not implement sync itself: it drives the
bundled `hsync` client binary, builds its command line from a friendly settings
dialog, and shows live progress, transfers and logs in a native window with a
system-tray icon.

Use it when you want HSYNC's Server Mode or peer-to-peer P2P Mode without
touching the command line.

## Where to start

- **End user?** → [Download a binary](#install--quickstart) and run it — no build required.
- **Building from source?** → Follow the [developer instructions](#install--quickstart) below.
- **Need help with settings?** → See the [Usage Guide](usage.md).

## Install & quickstart

### For end users

Download the prebuilt binary for your platform from the
[Releases page](https://github.com/albertsdk/hsync-desktop/releases) (when
available). Extract the archive and run the `hsync-desktop` executable — it
bundles the HSYNC Client binary, so no additional installation is required.

> Prebuilt binaries are a planned feature and not yet available in every
> release. In the meantime, use the developer instructions below.

On first launch, open **Settings**, fill in your sync folder, bucket and mode
(Server or p2p), then start a sync. See [usage.md](usage.md) for the full
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

To build the 64-bit Raspberry Pi (arm64) binary from an amd64/arm64 host with
Docker:

```bash
./compile.sh --target rpi
# Binary output: dist/rpi/arm64/hsync-desktop
```

The native build needs `poetry install` first; the Raspberry Pi target installs
its dependencies inside the build container and needs Docker with
`qemu-user-static` (binfmt) configured. The desktop GUI is available for 64-bit
Raspberry Pi OS only: PySide6 publishes no 32-bit (armhf) Linux wheels, so armhf
is not supported. Run `./compile.sh --help` for the full option list.

A Debian/Ubuntu package is produced with `./compile.sh --target deb` (host arch)
or `--target deb-all` (amd64 + arm64). The `.deb` installs
`/usr/bin/hsync-desktop`, a launcher entry and the app icon, and declares a
dependency on `hsync-client` (the engine it drives):

```bash
./compile.sh --target deb
sudo dpkg -i dist/deb/hsync-desktop_<ver>_<arch>.deb
sudo apt install -f
```

## Documentation map

| Document | What it covers |
| -------- | -------------- |
| [usage.md](usage.md) | Configure connection, run and watch syncs, manage secrets, tray & themes. |
| [log-labels.md](log-labels.md) | Action labels shown in the log panel and what they mean. |

## Associated Ecosystem Components

> The other HSYNC ecosystem components are listed in the
> [project README](../README.md#associated-ecosystem-components).
