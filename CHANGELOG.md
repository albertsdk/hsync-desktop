# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Import files by **drag & drop** onto the file list: dropping files or folders
  from the OS file manager copies them into the shared folder (hold **Shift** to
  move). Name conflicts are resolved with a Replace / Keep both / Skip prompt
  (with an **Apply to all** option), the copy runs in the background, and the
  result is reported as a toast.

### Changed

- p2p mode now calls the `rdv/1` node a **rendezvous server** instead of a
  "relay server": the node only helps devices find each other and never carries
  file data. The setup wizard, the Settings p2p tab, the trusted-servers dialog
  and all locales use the same wording. Internal identifiers, wizard-draft
  fields and i18n keys follow the same terminology; a wizard draft saved by an
  older version is discarded (draft schema v3).

### Fixed

- The p2p invite shown after the setup wizard now includes the share name, so a
  second device can join the same share without guessing it.
- Sync could not start in p2p mode with exit code 2: the engine now receives the
  client's current `--peer-rendezvous-timeout` flag instead of the renamed
  `--rendezvous-timeout` (hsync-client 1.0.11).
