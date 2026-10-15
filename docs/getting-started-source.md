# Getting Started — Method 4: From source

Run HSYNC Desktop directly from a clone — for development, or a host where you
control the toolchain. This is the most involved method; for a managed host
prefer the [installer script](getting-started-script.md) or the
[Debian package](getting-started-deb.md).

## Prerequisites

- Python ≥3.12, <3.15
- Poetry
- The `hsync-common` repository checked out as a sibling of `hsync-desktop`
  (a path dependency of the project)
- The `hsync` client engine: build it from the sibling `hsync-client` checkout,
  or install it so it is on `PATH` (see
  [hsync binary discovery](#hsync-binary-discovery))

## Install and run

### Quick path (`run.sh`)

With both repositories cloned side by side:

```bash
git clone https://github.com/albertsdk/hsync-desktop.git hsync-desktop
git clone https://github.com/albertsdk/hsync-common.git hsync-common
cd hsync-desktop
./run.sh
```

`run.sh` creates the in-project virtualenv on first use, installs the main
dependencies, and launches the GUI (`./run.sh --help`). It stops with a clear
message if `../hsync-common` is missing.

### Native commands

The same steps, spelled out (the virtualenv is created by `run.sh`):

```bash
.venv/bin/hsync-desktop
```

### Build the engine first (self-contained bundle)

The native build bundles the `hsync` client when it finds it in the sibling
checkout (build the engine first — see [Contributing](../CONTRIBUTING.md)),
producing a standalone executable:

```bash
./compile.sh
# → dist/<os>-<arch>/hsync-desktop
```

The desktop build looks for the client at
`../hsync-client/dist/<os>-<arch>/hsync[.exe]`; when it is missing the build
warns and the app falls back to `hsync` on `PATH` at runtime.

### Build options

```bash
./compile.sh                    # Native host build (default)
./compile.sh --clean            # Clean artifacts and rebuild
./compile.sh --target deb       # Debian/Ubuntu .deb for the host arch
./compile.sh --target deb-all   # .deb for amd64 + arm64 (Docker + qemu)
./compile.sh --target rpi       # Raspberry Pi OS 64-bit (arm64)
./compile.sh --target windows   # Windows x64 installer + portable zip
./compile.sh --version 1.2.3    # Override the reported version
./compile.sh --help             # Show help
```

The version can also be set through the `HSYNC_VERSION` environment variable.

The `rpi` target cross-builds the arm64 onefile binary inside an emulated Debian
Bookworm container, so it needs Docker with `qemu-user-static` (binfmt) on the
build host; the GUI is available for **64-bit Raspberry Pi OS only** (PySide6
has no 32-bit Linux wheels). See [Debian package](getting-started-deb.md) to
produce `.deb` files.

The `windows` target (Windows x64 only) produces the per-user Inno Setup
installer and a portable `.zip`; it needs Inno Setup 6 (`ISCC`) and ImageMagick
on the build host.

## hsync binary discovery

At runtime the application searches for the `hsync` binary in this order:

1. **Bundled**: `hsync_desktop/bin/hsync[.exe]` (included in compiled builds)
2. **System PATH**: `which hsync`
3. **Sibling project** (development): `../hsync-client/dist/<os>-<arch>/hsync[.exe]`
   — the platform tag (e.g. `linux-amd64`, `darwin-arm64`) is detected at runtime

## Update

```bash
cd /path/to/hsync-desktop
git pull
./run.sh
```

Settings and secrets are kept separately by Qt `QSettings`.

## Next

- Configure Server Mode or p2p Mode: [Configuration Reference](configuration.md).
- Prefer a packaged install? [Debian package](getting-started-deb.md).
