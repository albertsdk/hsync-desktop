# Getting Started — Snap package

The Snap installs HSYNC Desktop on any distribution with `snapd` and updates it
automatically. It is **self-contained**: the matching `hsync` engine is bundled,
so no separate `hsync-client` install is required.

The Snap uses **classic confinement** because a file-sync application needs the
same filesystem access as the `.deb`/`.rpm`: it reads and writes the sync folder
you choose anywhere on disk, keeps settings and secrets under your home
directory, manages a login autostart entry, and runs its bundled engine, which
binds local TCP ports. Strict interfaces cannot express that.

## Prerequisites

- <img src="assets/os/ubuntu.svg" alt="Ubuntu" width="16" height="16"> Ubuntu
  **24.04 or later**, or another distribution with a current `snapd` that
  supports the `core24` base
- **amd64** or **arm64**
- `sudo` (installing or removing the snap)

The Snap ships its own runtime and glibc (`core24`), so the host's glibc version
does not matter.

## Install

The store publication is currently on the **`edge`** channel only, while the
store runs its one-time classic-confinement review; there is no `stable` install
yet. Install from `edge`:

```bash
sudo snap install hsync-desktop --classic --channel=edge
```

`--classic` is required: without it `snapd` refuses a classic-confined snap. Until
the review is approved the store has no published revision at all — use the
alternative offline path below, which always works.

## Verify

```bash
hsync-desktop --version
snap connections hsync-desktop
```

The application-menu entry starts "HSYNC"; the tray icon appears while it runs.

## Alternative: install a release asset offline

The GitHub Release publishes the `.snap` files for both architectures. Install
one without the store:

```bash
sudo snap install --dangerous --classic ./hsync-desktop-amd64.snap
```

Use `hsync-desktop-arm64.snap` on ARM. `--dangerous` skips store signature
verification, which is expected for a locally downloaded file checked against
`SHA256SUMS`.

## Update and uninstall

Snaps update automatically from the store, including the `edge`/`beta`/`candidate`
channels when you opt into them; a snap installed from `edge` keeps that channel
on refresh. To check or force an update:

```bash
snap refresh --time
sudo snap refresh hsync-desktop
```

Remove it with:

```bash
sudo snap remove hsync-desktop
```

Your settings, saved secrets and sync folder live in your home directory and are
kept.

> Install **either** the Snap **or** the `.deb`/`.rpm`, not both: the packages
> share the same settings directory and single-instance socket.
