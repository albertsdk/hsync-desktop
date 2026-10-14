# HSYNC Desktop — Decisions

Ecosystem ADRs are SSOT in `hsync-common`
([decisions index](../../hsync-common/llm-wiki/decisions.md) →
`hsync-common/docs/internal/adr/`). This page maps the ADRs that govern the GUI to the
**desktop code**, plus desktop-only rules.

## ADR → desktop code

| ADR | Desktop implementation |
| --- | ---------------------- |
| [0004 desktop-subprocess-contract](../../hsync-common/docs/internal/adr/0004-desktop-subprocess-contract.md) | the whole `engine.py`: CLI args (`cli_args.build_hsync_args`), `--events-json-fd` JSON-Lines stream → Qt signals (`engine.py::HsyncEngine._handle_event`), stdin commands (`engine.py::HsyncEngine._send_command`) |
| [0005 protocol-versioning](../../hsync-common/docs/internal/adr/0005-protocol-versioning.md) | `is_binary_version_compatible` (`engine.py::is_binary_version_compatible`) + `BinaryVersionProbe` (`engine.py::BinaryVersionProbe`) gate the UI on the binary's protocol/app version (resolved asynchronously, cached in QSettings) |
| [0001 server-vs-p2p-modes](../../hsync-common/docs/internal/adr/0001-server-vs-p2p-modes.md) | p2p block in the settings dialog + `p2p`/`server` subcommand selection and master flags in `cli_args.py` |

§8 capabilities gating (`--capabilities-json` → `parse_capabilities` →
disable unsupported controls) is realized in
`engine.get_binary_capabilities` (`engine.py::get_binary_capabilities`) + `SettingsDialog`
([settings.md](modules/settings.md)).

## Desktop-only rules

- **Subprocess contract is the only API**: never import `hsync_client.*`. All
  coupling is through CLI flags + the event stream + stdin commands. New
  capabilities land in the client (and `hsync-common` vocabulary) first; the
  desktop only *consumes* them.
- **Secrets never on argv**: API/p2p keys travel through inherited pipe FDs
  (`--api-key-fd`/`--p2p-key-fd`, `engine.py::HsyncEngine.start`) and are Fernet-encrypted at
  rest (`crypto.py`). The settings file is permission-restricted
  (`cli_args.secure_config_file`, `settings/cli_args.py::secure_config_file`).
- **UI thread discipline**: only signals mutate widgets; long scans run in
  `QObject` workers (`file_panel/workers.py::DirectoryScanWorker`).
- **i18n completeness**: every user string must exist in all 5 locales
  (`locales/{en,it,de,es,fr}.py`); look up via `i18n.tr`.
- **Capability-gated, not version-sniffing**: prefer the capabilities doc over
  parsing `--help`/version strings to decide which controls to show (§8).
- **Non-blocking startup probes**: the bundled binary's version is resolved
  asynchronously (`BinaryVersionProbe`, `engine.py::BinaryVersionProbe`) and both probes are
  cached in `QSettings` keyed by the binary `(path, size, mtime_ns)`; a probe
  must never block the GUI startup path.
- **Raspberry Pi GUI is arm64-only**: the `rpi` build target ships the
  arm64 (64-bit) binary only. PySide6 publishes no armv7 Linux wheels, so the Qt
  desktop cannot be built for 32-bit armhf; the target documents this instead of
  failing. Cross-builds run in an emulated arm64 container from
  `packaging/rpi/Dockerfile.builder` via `compile.sh --target rpi`. The builder
  pins its build inputs: the privileged `qemu-user-static` binfmt image is
  pulled by digest and Rust is installed from a SHA256-verified,
  version-pinned `rustup-init`. Its base is the official multi-arch
  `python:3.12-bookworm` image (prebuilt CPython), so the arm64 build does not
  compile CPython under qemu-user.
- **Debian packaging** (`compile.sh`, targets `deb`/`deb-all`): a `--onedir`
  freeze staged as a `.deb` reusing the shared packaging machinery
  (`packaging/deb/`, `_semver_to_debian`, `_finalize_deb_stage`,
  `_inject_shlib_depends`). It installs the GUI under `/usr/lib/hsync-desktop`
  with a `.desktop` launcher and hicolor icons, and declares
  `Depends: hsync-client` instead of bundling the client (the app falls back to
  `/usr/bin/hsync` on PATH). `deb-all` cross-builds amd64 + arm64 in Docker
  (armhf unsupported, as for `rpi`). Not yet wired into a release workflow.
- **Container builds install the `build` group explicitly** (`rpi`/`deb-all`):
  `poetry install --only main,build`. Under Poetry 2.x (2.3.2, pinned in the
  builder image) a co-present `--with` is ignored inside `--only`, so the
  previous `--only main --with build` silently installed no PyInstaller (exit
  code 0, `pyinstaller` absent on PATH) and the cross-build targets aborted;
  guarded by `tests/test_compile_script.py`.

> New cross-repo decisions: add the ADR in `hsync-common` first, then map it here.

- **Bootnode trust is selected as a policy (ADR-0035)**: the "Trust bootnode on
  first use" toggle is replaced by a `p2p_bootnode_trust` combo
  (`ask`/`accept-new`/`strict`/`none`), forwarded as `HSYNC_BOOTNODE_TRUST`
  (default `ask`). The pin lives in the client's known-hosts store, not a GUI
  env var: the GUI resolves policy `ask` in its start pre-flight
  (`_ensure_bootnode_trust`) by writing `hsync trust bootnode add`, and both
  trust stores are editable through the "Manage trusted keys" dialog
  (`trusted_keys.py`). The GUI cannot answer the client's terminal prompt, so it
  always sends an explicit policy; the client's SSH-style prompt is terminal-only
  and fails closed without a tty.

- **The client/desktop version pairing is gated at build time**: `compile.sh`
  `_add_data_args` runs the bundled `hsync-client` binary with `--version` and
  refuses the build when its major version differs from
  `hsync_common.constants.HSYNC_VERSION` — the same rule the app re-checks at
  runtime (`engine.py::is_binary_version_compatible`, which only warns). A binary
  that cannot run on the host (cross-arch `rpi`) is reported as unverifiable and
  skipped. Guarded by `tests/test_compile_script.py`.
