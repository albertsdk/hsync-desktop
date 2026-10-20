# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- p2p mode now calls the `boot/1` node a **discovery server** instead of a
  "relay server": the node only helps devices find each other and never carries
  file data. The setup wizard, the Settings p2p tab, the trusted-servers dialog
  and all locales use the same wording. Internal identifiers, wizard-draft
  fields and i18n keys follow the same terminology; a wizard draft saved by an
  older version is discarded (draft schema v3).

### Fixed

- The p2p invite shown after the setup wizard now includes the share name, so a
  second device can join the same share without guessing it.
