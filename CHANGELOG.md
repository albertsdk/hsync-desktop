# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Trash…** marks a row whose stored copy is gone (*no stored copy*) and keeps
  Restore disabled for it, so the view never offers a command that can only
  refuse.

- **Trash…** in the Sync menu (ADR-0056): lists the files this device deleted,
  restores one into the folder, or empties the store after a confirmation. The
  listing and both actions go through `hsync trash`, so it works while a sync
  runs and a restored file returns to every device at the next cycle.

- A **Keep deleted files in the local trash** switch and a **Restore window
  (days)** spin in *Settings → Sync* replace the single overloaded spin: the
  switch is emitted as `--no-trash`, the window as `--trash-retention`, and both
  only once saved.

- Three settings for the peer-mesh capabilities (serve blocks, fetch from peers, publish
  inventory), translated in every locale.

### Changed

- **Move to trash** in the file list now uses the app's own trash instead of the
  operating system's: one confirmation for the selection, the bytes are kept for
  the restore window and come back through **Sync → Trash…**, and the same code
  runs on Linux, macOS and Windows (no `gio`, PowerShell or AppleScript helper).
- The confirmation of a plan with deletions states how long they stay restorable
  (`HSYNC_TRASH_RETENTION_DAYS`, 30 days by default) instead of "cannot be
  undone"; with the trash off the old warning is kept.
- **Keep deleted files for (days)** in *Settings → Sync* is now a switch plus a
  **Restore window (days)** spin (`1..3650`): the window stores
  `sync/trash_retention` and is emitted as `--trash-retention` only once saved, so
  an installation that never saved the tab keeps honouring
  `HSYNC_TRASH_RETENTION_DAYS`. `0` is no longer the dialog's "off" — that is the
  switch's job — because the client reads `--trash-retention 0` as "keep until
  the size limit evicts".
- The advanced tab groups them with the existing peer options as three independent
  switches.
- The three identity checks default to **Automatic** (a saved pin, then a CA
  chain, then the first sighting) and share one wording; a stored `chain` or
  `accept-new` is normalized to `auto`.
- Windows: the log panel uses a slightly larger font (one point below the system
  monospace, 9 pt floor) instead of the uniform two-point reduction, which read
  too small there.
- A plan that deletes nothing is applied without the confirmation dialog by
  default; the first plan of an installation is always shown, and any plan with
  a deletion still asks. The setting is renamed from *Sync without asking* to
  *Apply changes that delete nothing*, the scope it always had.

### Fixed

- The "Time left" column is populated on folder rows too: it derives the
  estimate from the remaining wire bytes and the summed rate of the children in
  flight (it stayed empty on the default folder view even while the folder read
  "Sending"/"Receiving").
- A transfer this device is **sending** shows its in-flight state and a progress
  bar again (first sync, p2p upload and delta): the bundled engine now reports
  the sender's own samples instead of relying on the receiver's delivery echo,
  which does not exist until the peer's control WebSocket is up.
- A comparison that overlaps a transfer no longer leaves the just-received file
  at "To Download" (100% progress) or an empty folder at "To Sync": a verdict
  from the comparison snapshot cannot downgrade a path a terminal event already
  settled, and the plan counters/summary no longer count it.
- Saving a preference that is not about the connection (the language, the theme,
  a sync interval) no longer contacts the server: an unverified share used to be
  probed on every OK press, so a revoked key or an unreachable host made every
  setting unsavable and each save waited up to the probe timeout. The share check
  now runs only when the connection itself was edited, and the
  `sync/bucket_verified` marker is gone with it.
- Creating or duplicating a share in server mode now confirms the new bucket
  before the share is written (offering to create it on the server when it is
  missing), instead of discovering it on the first sync.
- The share-check and confirmation boxes reserve room for their title, which a
  short message used to clip in the title bar.
- **Move to trash** failed with `exit status 127` on hosts whose GLib is newer
  than the bundled one; the helper now runs with the library overrides stripped.
- Windows: a configured P2P/API key now reaches the client and the structured
  events reach the GUI — secrets travel through the process environment and
  events through the child's stderr — instead of the keyless-P2P startup failure
  and dead event channel caused by Windows not inheriting the POSIX pipe FDs.
- Windows: the GUI no longer opens an extra console window (at launch or during
  a sync), and the app and its shortcuts show the app icon.
- The **Sync only a specific subfolder** setting now restricts the sync: the value
  was resolved to an absolute path before being passed as `--subdir` (which is
  bucket-relative), so the filter matched nothing. An invalid value is now rejected
  instead of silently widening the run to the whole folder.
- The whole-system-tree warning now also appears on Windows and macOS, not only on
  Linux (system trees, `Program Files`/`ProgramData`, `/System`, `/Library`,
  `/Applications`).
- macOS: the `.dmg` bundle is now signed after the `Info.plist` merge, so
  Gatekeeper no longer reports the app as **damaged** on first launch (the
  documented right-click → Open workaround could not clear that state).
- Windows: `hsync-desktop --version` and `--help` now show their output — in a
  terminal window, or in a dialog when the app is started without a console.
- The Settings window no longer truncates a localized action button: the content
  column widens past its reading width when a label needs it (a large system
  font, as on Windows), and the button pair unfolds whenever the screen allows.
- A folder row is described by its children: a pending verdict the engine stored
  on a folder that has content no longer makes the folder and every ancestor read
  "To sync" (`hsync_desktop/file_panel/transfer_table.py::FileTransferTable._aggregate_folder`).

## [1.1.2] - 2026-11-12

### Added

- **Multiple named shares**: a header selector switches the active share and a
  manage dialog creates, duplicates, renames and deletes them (with an optional
  client-state reset), each share keeping its own log buffer. Folder uniqueness
  and a duplicate-bucket warning guard the store, and the previous single-share
  configuration is migrated.
- A changed bucket is verified before the settings dialog saves it — including
  the one a share you just created carries — and the settings dialog and the
  wizard's connection test offer to create a share the server reports as missing
  instead of letting the sync fail on it.

### Changed

- Every dialog button is localized in all the supported locales, and the shares
  dialogs follow the rest of the UI style.

### Fixed

- Creating a share posts the name as a query parameter, and a `403` that names
  `max_buckets_per_account` is reported as a quota with the limit instead of a
  generic failure.
- Deleting a share removes the selected row instead of the first one, and the
  reset/confirm dialogs stay in front of the share manager.
- A missing share raises one notification per episode instead of two.
- A share created from the header selector is checked against the server when its
  settings are saved: the check was skipped because the new record already held
  its bucket name, so the first sync stopped on a `404` and the share was never
  created.
- A comparison that failed no longer reports "nothing to sync": the run ends with
  the engine's own error (a missing share, an unreachable server) instead of a
  green toast followed by a second, identical failure.
- The Properties title stays bold after a font reset, the detail pane can widen,
  the rename dialog keeps long names readable, and Server Mode no longer shows
  the placeholder dash of the bottom-bar group label.
- A stopped sync replaces the p2p/server mode icon with the grey badge instead
  of overlaying it, and the in-progress dot is smaller.

## [1.1.0] - 2026-11-11

### Added

- The tray menu names the connection state and offers **Open synced folder**
  (reach the files without restoring the window) and **About**, next to the
  run controls, Settings, the Setup wizard and Quit.
- Import files by **drag & drop** onto the file list: dropping files or folders
  from the OS file manager copies them into the shared folder (hold **Shift** to
  move). Name conflicts are resolved with a Replace / Keep both / Skip prompt
  (with an **Apply to all** option), the copy runs in the background, and the
  result is reported as a toast.
- The welcome splash — also the Help → About window — now shows the bundled sync
  engine's version next to the app version (`Engine 1.0.11`, localized), or an em
  dash when it cannot be determined.
- The p2p settings tab gained an **Exclude the local network** toggle: it
  disables mDNS discovery and finds devices only through the configured
  discovery server(s) (`--no-mdns`). It is enabled only while a discovery server
  is configured, since without one there would be no discovery channel at all.
- The p2p settings tab gained a **Reach the discovery server via** selector:
  the app now reaches the rendezvous server over **TLS/TCP** as well as
  QUIC/UDP — **Auto** (races both, QUIC/UDP preferred), **QUIC/UDP only** or
  **TLS/TCP only** — for networks that filter UDP.

### Changed

- p2p mode now calls the `rdv/1` node a **rendezvous server** instead of a
  "relay server": the node only helps devices find each other and never carries
  file data. The setup wizard, the Settings p2p tab, the trusted-servers dialog
  and all locales use the same wording. Internal identifiers, wizard-draft
  fields and i18n keys follow the same terminology; a wizard draft saved by an
  older version is discarded (draft schema v3).
- The file list breadcrumb now renders every folder as a clickable link: a
  parent folder navigates to it, and the current folder refreshes its listing
  on click instead of doing nothing.

### Fixed

- The connection label and the per-file states settle after a sync: the label
  reads "Connected" and synced rows read "Synced" (not "Synced (not
  verified)") once the cycle ends, with the run's activity shown separately in
  the file-set bar.
- A newly created empty folder no longer stays "To sync" on the device that
  created it (and "Local" on the replica): the bundled engine now keeps the
  empty-directory sentinel on the serving side and reports the folder's verdict
  from both creation paths.
- The transfer rate display re-anchors after a pause/resume: a progress sample
  arriving after a gap longer than the rate window restarts the measurement,
  so a resumed upload no longer shows a bogus burst speed for the bytes already
  transferred.
- The p2p invite shown after the setup wizard now includes the share name, so a
  second device can join the same share without guessing it.
- Sync could not start in p2p mode with exit code 2: the engine now receives the
  client's current `--peer-rendezvous-timeout` flag instead of the renamed
  `--rendezvous-timeout` (hsync-client 1.0.11).
- A finished transfer no longer reopens or stays frozen: a trailing progress
  sample cannot restart a row that already reached `Synced`, and a status
  refresh now resolves a row whose terminal event was lost.
- Stopping a sync now ends the whole engine process tree: a bundled one-file
  engine left its payload running (and the folder instance-locked), so the
  next Start was refused with "Another hsync process is already syncing".
