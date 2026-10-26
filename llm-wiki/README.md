# HSYNC Desktop — Agent Wiki (index)

PySide6/Qt desktop GUI. It does **not** reimplement sync: it launches the
`hsync` **client binary** as a subprocess, feeds it CLI args built from the
settings UI, and renders the structured event stream the binary emits. This wiki
is the agent map; start here, then drill into the linked files.

> **Docs-first**: read this index and the relevant module file before touching
> code; follow the `path/to/file.ext::symbol` anchors instead of blind search.
> End-user docs live in [`../docs/`](../docs/README.md) — keep them in sync with
> any user-facing change (Dual-Docs rule).

## Map

| Doc | Scope |
| --- | ----- |
| [architecture.md](architecture.md) | component map: binary discovery → QProcess → event→signal → Qt UI; build/packaging targets |
| [modules/engine.md](modules/engine.md) | `engine/` package (`cli.py`, `process.py`, `async_probe.py`): subprocess lifecycle, pipe-FD secrets, event→signal bridge, capability probe, off-thread probe runner |
| [modules/ui.md](modules/ui.md) | `main_window/` package, `trusted_keys.py` (trust dialogs), `file_panel/`, tray, themes, icons, i18n |
| [modules/settings.md](modules/settings.md) | `config.py`, `settings/` (dialog, cli_args, validators), `crypto.py` |
| [modules/wizard.md](modules/wizard.md) | `wizard/` setup wizard (modes, pages, probes, draft/apply); `engine/endpoints.py`, `engine/probes.py` |
| [data-models.md](data-models.md) | `TransferStats`, `FileTransfer`/`TransferStatus`, reused common types, wizard models |
| [decisions.md](decisions.md) | ADR→desktop-code map; GUI-only rules |

## Cross-repo SSOT

The desktop is a **consumer**: the event names, capabilities doc and protocol
versions it parses are defined in `hsync-common`
([wiki](../../hsync-common/llm-wiki/README.md)); the CLI flags it emits and the
events it reads are the **contract** owned by the `hsync` client
([wiki](../../hsync-client/llm-wiki/README.md)). Never redefine those here.

## Golden rules (see [decisions.md](decisions.md))

- **Subprocess contract only**: talk to the binary via CLI args + the
  `--events-json-fd` JSON-Lines stream + stdin commands. No imports of client
  internals (ADR 0004).
- **Capability-gated UI**: probe `--capabilities-json` and disable controls the
  binary does not support (§8).
- **Secrets via pipe FDs**: API/p2p keys are written to inherited pipes
  (`--api-key-fd` / `--p2p-key-fd`), never argv; at rest they are Fernet-encrypted
  in `QSettings` (`crypto.py`).
- **i18n lock-step**: every user string exists in all locales
  (`hsync_desktop/locales/{en,it,de,es,fr,pt,zh,ru,nl,pl,ja}.py`); look up via `i18n.tr`.
