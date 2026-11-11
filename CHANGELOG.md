# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
