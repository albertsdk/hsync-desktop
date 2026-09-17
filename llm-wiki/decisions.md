# HSYNC Desktop — Decisions

Ecosystem ADRs are SSOT in `hsync-common`
([decisions index](../../hsync-common/llm-wiki/decisions.md) →
`hsync-common/docs/internal/adr/`). This page maps the ADRs that govern the GUI to the
**desktop code**, plus desktop-only rules.

## ADR → desktop code

| ADR | Desktop implementation |
| --- | ---------------------- |
| [0004 desktop-subprocess-contract](../../hsync-common/docs/internal/adr/0004-desktop-subprocess-contract.md) | the whole `engine.py`: CLI args (`cli_args.build_hsync_args`), `--events-json-fd` JSON-Lines stream → Qt signals (`engine.py:572`), stdin commands (`engine.py:459`) |
| [0005 protocol-versioning](../../hsync-common/docs/internal/adr/0005-protocol-versioning.md) | `is_binary_version_compatible` (`engine.py:225`) + `BinaryVersionProbe` (`:324`) gate the UI on the binary's protocol/app version (resolved asynchronously, cached in QSettings) |
| [0001 server-vs-lan-modes](../../hsync-common/docs/internal/adr/0001-server-vs-lan-modes.md) | LAN block in the settings dialog + `lan`/`server` subcommand selection and master flags in `cli_args.py` |

§8 capabilities gating (`--capabilities-json` → `parse_capabilities` →
disable unsupported controls) is realized in
`engine.get_binary_capabilities` (`engine.py:188`) + `SettingsDialog`
([settings.md](modules/settings.md)).

## Desktop-only rules

- **Subprocess contract is the only API**: never import `hsync_client.*`. All
  coupling is through CLI flags + the event stream + stdin commands. New
  capabilities land in the client (and `hsync-common` vocabulary) first; the
  desktop only *consumes* them.
- **Secrets never on argv**: API/LAN keys travel through inherited pipe FDs
  (`--api-key-fd`/`--lan-key-fd`, `engine.py:315`+) and are Fernet-encrypted at
  rest (`crypto.py`). The settings file is permission-restricted
  (`cli_args.secure_config_file`, `:31`).
- **UI thread discipline**: only signals mutate widgets; long scans run in
  `QObject` workers (`file_panel/workers.py:27`).
- **i18n completeness**: every user string must exist in all 5 locales
  (`locales/{en,it,de,es,fr}.py`); look up via `i18n.tr`.
- **Capability-gated, not version-sniffing**: prefer the capabilities doc over
  parsing `--help`/version strings to decide which controls to show (§8).
- **Non-blocking startup probes**: the bundled binary's version is resolved
  asynchronously (`BinaryVersionProbe`, `engine.py:340`) and both probes are
  cached in `QSettings` keyed by the binary `(path, size, mtime_ns)`; a probe
  must never block the GUI startup path.

> New cross-repo decisions: add the ADR in `hsync-common` first, then map it here.
