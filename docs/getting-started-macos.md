# Getting Started — macOS (.app / .dmg)

The `.dmg` contains a standard **HSYNC.app** bundle: open it and drag the app to
**Applications**. The app embeds the `hsync` client engine, so there is nothing
else to install.

> Provided for **Apple silicon (arm64)** and **Intel (amd64)** separately — pick
> the `.dmg` matching your Mac. The app is **unsigned**, so macOS asks for
> confirmation on the first launch (see below).

## Prerequisites

- macOS 11 (Big Sur) or later
- The matching `.dmg`: `hsync-desktop-darwin-arm64.dmg` (Apple silicon)
  or `hsync-desktop-darwin-amd64.dmg` (Intel)

## Install

```bash
curl -fLO "https://github.com/albertsdk/hsync-desktop/releases/latest/download/hsync-desktop-darwin-arm64.dmg"
open hsync-desktop-darwin-arm64.dmg
```

Use `darwin-amd64` instead of `darwin-arm64` on an Intel Mac. The URL always
points to the **latest stable** release; to pin a version, use
`https://github.com/albertsdk/hsync-desktop/releases/download/vX.Y.Z/hsync-desktop-<version>-darwin-<arch>.dmg`.
Then drag **HSYNC** into the **Applications** folder shown in the window.

### Build from the checkout (alternative)

On a Mac, with the `hsync-client` engine already built as a sibling directory
(install the build dependencies first — see [Contributing](../CONTRIBUTING.md)):

```bash
./compile.sh --target dmg
```

The `.app` is assembled under `build/macos/` and the `.dmg` is written to
`dist/macos/`.

## First launch (Gatekeeper)

The app is **not notarized**, so macOS blocks the first launch:

- Open **Applications**, **right-click HSYNC → Open**, then click **Open** in the
  dialog; or
- Remove the quarantine flag:

  ```bash
  xattr -dr com.apple.quarantine /Applications/HSYNC.app
  ```

After that it opens normally.

## Run

Open **HSYNC** from Launchpad or Applications — it runs in the menu bar with a
tray icon. On first launch open **Settings** and configure a connection; see the
[Configuration Reference](configuration.md).

## Update and remove

Download the newer `.dmg` and replace the app in **Applications**. To remove it,
drag **HSYNC.app** to the Trash.

## Next

- Prefer no Gatekeeper prompt? There is no signed build yet; use the
  [standalone binary](getting-started-binary.md) (same unsigned caveat) or run
  [from source](getting-started-source.md).
