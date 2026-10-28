# HSYNC Desktop — Decisions

Ecosystem ADRs are SSOT in `hsync-common`
([decisions index](../../hsync-common/llm-wiki/decisions.md) →
`hsync-common/docs/internal/adr/`). This page maps the ADRs that govern the GUI to the
**desktop code**, plus desktop-only rules.

## ADR → desktop code

| ADR | Desktop implementation |
| --- | ---------------------- |
| [0004 desktop-subprocess-contract](../../hsync-common/docs/internal/adr/0004-desktop-subprocess-contract.md) | the whole `engine/` package: CLI args (`cli_args.build_hsync_args`), `--events-json-fd` JSON-Lines stream → Qt signals (`engine/process.py::HsyncEngine._handle_event`), stdin commands (`engine/process.py::HsyncEngine._send_command`) |
| [0005 protocol-versioning](../../hsync-common/docs/internal/adr/0005-protocol-versioning.md) | `is_binary_version_compatible` (`engine/cli.py::is_binary_version_compatible`) + `BinaryVersionProbe` (`engine/cli.py::BinaryVersionProbe`) gate the UI on the binary's protocol/app version (resolved asynchronously, cached in QSettings) |
| [0001 server-vs-p2p-modes](../../hsync-common/docs/internal/adr/0001-server-vs-p2p-modes.md) | p2p block in the settings dialog + `p2p`/`server` subcommand selection and master flags in `cli_args.py` |
| [0041 serving-side-status-pass-events](../../hsync-common/docs/internal/adr/0041-serving-side-status-pass-events.md) | `status_pass_started`/`status_pass_ended` signals (`engine/process.py::HsyncEngine`) → `EventsMixin._on_status_pass_started`/`_on_status_pass_ended`, distinct from the preview pair that confirms a sync ([ui.md](modules/ui.md)) |
| [0042 per-device-serving-status](../../hsync-common/docs/internal/adr/0042-per-device-serving-status.md) | `device_status` → `EventsMixin._on_device_status` + `EventsMixin._serving_sync_state` (worst device, never a union), per-file `holders`/`devices` → `FileTransferModel._row_status` ([ui.md](modules/ui.md)) |
| [0043 preview-confirmation-contract](../../hsync-common/docs/internal/adr/0043-preview-confirmation-contract.md) | `preview_skipped`/`preview_warning` → `PreviewStats.skipped_deletes`/`guard_deletes`; the dialog renders the plan, the estimates come from `get_bandwidth_limits` ([ui.md](modules/ui.md)) |

§8 capabilities gating (`--capabilities-json` → `parse_capabilities` →
disable unsupported controls) is realized in
`engine.get_binary_capabilities` (`engine/cli.py::get_binary_capabilities`) + `SettingsDialog`
([settings.md](modules/settings.md)).

## Desktop-only rules

- **Sync-state reset is a client operation the GUI only requests**: the
  per-folder state DB is client-owned and guarded by the per-directory
  `InstanceLock`, so the Settings button
  (`settings/dialog.py::SettingsDialog._on_reset_state`) never touches it — it
  confirms, sets `reset_state_folder` and closes; `StartMixin._reset_sync_state`
  runs `hsync state reset --folder … --json`
  (`engine/cli.py::reset_sync_state`). Gated on
  `supports_subcommand(doc, "state")` and disabled while the sync runs. Rationale
  (and the rejected alternative of deleting the DB from the GUI): the GUI cannot
  see a CLI/service sync on the same folder, so a file-level delete would reset
  state a live process keeps writing.
- **Subprocess contract is the only API**: never import `hsync_client.*`. All
  coupling is through CLI flags + the event stream + stdin commands. New
  capabilities land in the client (and `hsync-common` vocabulary) first; the
  desktop only *consumes* them.
- **Secrets never on argv**: API/p2p keys travel through inherited pipe FDs
  (`--api-key-fd`/`--p2p-key-fd`, `engine/process.py::HsyncEngine.start`) and are Fernet-encrypted at
  rest (`crypto.py`). The settings file is permission-restricted
  (`cli_args.secure_config_file`, `settings/cli_args.py::secure_config_file`).
- **UI thread discipline**: only signals mutate widgets; long scans run in
  `QObject` workers (`file_panel/workers.py::DirectoryScanWorker`).
- **Setup wizard is a Settings subset**: the four-mode wizard
  (`wizard/`, [wizard.md](modules/wizard.md)) writes only the keys it owns and
  never redefines CLI/env contracts; advanced options stay in the Settings
  dialog. Its server/discovery-server reachability probes and endpoint grammar
  are shared with Settings (`engine/probes.py`, `engine/endpoints.py`), and its
  trust model is TOFU + pin (policy `ask`), never `strict`/`accept-new`.
- **Host fonts, not a bundled typeface**: the GUI follows the desktop's
  configured UI/monospace fonts and text scale
  (`fonts.py::apply_system_fonts`; GNOME `gsettings`, KDE `kdeglobals`,
  `QFontDatabase` fallback). No font is bundled: a package is built once and
  host fonts vary, and proprietary system fonts cannot be redistributed. The
  Linux `QT_QPA_PLATFORMTHEME=generic` harden stays (the GTK3 theme aborts
  against the bundled GLib); the host `gsettings` probe drops `LD_LIBRARY_PATH`
  and the other bundled-library overrides (`fonts.py::_host_env`) so it loads
  the host GLib. The global **Font size** preference (`appearance/font_scale`,
  `standard` default / `compact`) scales the resolved UI and monospace bases
  once, so every derived font follows; the file table has no separate size knob.
- **No placeholder role indicator**: the p2p role icon/text stay hidden until
  the election has decided the role (`_role_known`); a dashed "unknown" glyph
  read as an unfinished state. The primary icon is theme-aware
  (`currentColor` + the system accent).
- **i18n completeness**: every user string must exist in all locales
  (`hsync_desktop/locales/{en,it,de,es,fr,pt,zh,ru,nl,pl,ja}.py`); look up via `i18n.tr`.
- **Help → Documentation opens the docs index**: `docs_links.DOCS_INDEX` is the
  end-user documentation landing page (`docs/README.md`), while
  `docs_links.CONNECTION_MODES` (`docs/choose-connection.md`) is the mode chooser the
  wizard's mode step and its "Not sure?" dialog link to. Keeping the two
  constants distinct stops the Help entry from landing on a guide page; guarded
  by `tests/test_docs_links.py::test_docs_index_is_the_documentation_landing_page`.
- **User docs keep one role per page**: `docs/concepts.md` only defines the GUI
  vocabulary and links to the client docs for depth; `docs/troubleshooting.md`
  owns the symptoms (the run-time warnings stay in `docs/warnings.md`); `docs/faq.md`
  answers in two or three lines and links to the page owning the procedure.
  Settings and procedures are never restated in a second page.
- **Deletion protection is described as a skipped cycle**: the guard skips only
  the unconfirmed deletions of that cycle and the sync keeps running, so
  `notif.sync_paused_title`/`notif.sync_paused_msg` say "deletions skipped" (never
  "paused" or "guard"); guarded by
  `tests/test_locales.py::test_sync_paused_warning_describes_the_skipped_cycle`.
- **Capability-gated, not version-sniffing**: prefer the capabilities doc over
  parsing `--help`/version strings to decide which controls to show (§8).
- **Non-blocking startup probes**: the bundled binary's version is resolved
  asynchronously (`BinaryVersionProbe`, `engine/cli.py::BinaryVersionProbe`) and both probes are
  cached in `QSettings` keyed by the binary `(path, size, mtime_ns)`; a probe
  must never block the GUI startup path.
- **Every blocking probe runs off the UI thread**: the client fingerprint
  subprocesses and the server `/health` calls are slow by nature (seconds to the
  configured timeout), so they run on `engine/async_probe.py::AsyncProbe` and the
  UI shows a busy state (`common.checking`). Run on the UI thread they freeze the
  window until the timeout, and the desktop environment reports the app as
  unresponsive.
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
  `packaging/deb/deb-depends.sh::_inject_shlib_depends`). It installs the GUI
  under `/usr/lib/hsync-desktop`
  with a `.desktop` launcher and hicolor icons, and **bundles the `hsync`
  client** (`_add_data_args`, `_require_bundled_client`), so it declares no
  `hsync-client` dependency. `deb-all` cross-builds amd64 + arm64 in Docker
  (armhf unsupported, as for `rpi`) and compiles the per-arch client inside the
  same container (same glibc).
- **Container builds install the `build` group explicitly** (`rpi`/`deb-all`):
  `poetry install --only main,build`. Under Poetry 2.x (2.3.2, pinned in the
  builder image) a co-present `--with` is ignored inside `--only`, so the
  previous `--only main --with build` silently installed no PyInstaller (exit
  code 0, `pyinstaller` absent on PATH) and the cross-build targets aborted;
  guarded by `tests/test_compile_script.py`.
- **The Windows build needs the ICU library shipped with Windows**: the PySide6
  6.12 win_amd64 wheel ships no ICU DLL, and its `Qt6Core.dll` imports the
  unversioned `icuuc.dll` (the Windows SDK ICU), while PyInstaller 6.22's
  `PyInstaller/utils/hooks/qt/__init__.py` (`QtLibraryInfo.collect_extra_binaries`
  hook) only globs the versioned `icu??.dll` names — so nothing is bundled either way.
  The artifact runs on Windows 10 (1809 or later) / 11 on x64 only, and the
  installer enforces that floor and the absence of an Arm64 build
  (`packaging/windows/hsync-desktop.iss`: `MinVersion`, `ArchitecturesAllowed`);
  Wine/CrossOver fails at load time
  (`Library icuuc.dll … not found`) and is documented as unsupported. Bundling
  `icu*.dll` from `C:\Windows\System32` was rejected: no license to redistribute
  Microsoft binaries, and the ABI must stay the Windows SDK ICU Qt links against.

- **Snap packaging** (`snap/snapcraft.yaml`): classic confinement on `core24`,
  amd64 + arm64, wrapping the prebuilt PyInstaller onefile (the client is bundled
  by the existing build). Classic is required because the app syncs user-chosen
  paths, writes hidden config/autostart entries, reads desktop theming config and
  spawns an engine that binds ports; strict would need `personal-files` and would
  still be limited. The release workflow pins Linux builds to Ubuntu 24.04 and
  asserts the GLIBC floor is ≤ 2.39 (core24's glibc); the onefile must never be
  built on a newer runner. Snaps are published to the store `edge` only after the
  one-time classic review and attached to the GitHub release; `autostart.py`
  uses `snap run` inside a snap.

> New cross-repo decisions: add the ADR in `hsync-common` first, then map it here.

- **Bootnode trust is selected as a policy (ADR-0035)**: the "Trust bootnode on
  first use" toggle is replaced by a `p2p_bootnode_trust` combo
  (`ask`/`accept-new`/`strict`/`none`), forwarded as `HSYNC_BOOTNODE_TRUST`
  (default `ask`). The pin lives in the client's known-hosts store, not a GUI
  env var: the GUI resolves policy `ask` in its start pre-flight
  (`main_window/trust.py::TrustMixin._ensure_trust`) by writing `hsync trust bootnode add`, and both
  trust stores are editable through the "Manage trusted keys" dialog
  (`trusted_keys.py`). The GUI cannot answer the client's terminal prompt, so it
  always sends an explicit policy; the client's SSH-style prompt is terminal-only
  and fails closed without a tty.

- **The client/desktop version pairing is gated at build time**: `compile.sh`
  `_add_data_args` runs the bundled `hsync-client` binary with `--version` and
  refuses the build when its major version differs from
  `hsync_common.constants.HSYNC_VERSION` — the same rule the app re-checks at
  runtime (`engine/cli.py::is_binary_version_compatible`, which only warns). A binary
  that cannot run on the host (cross-arch `rpi`) is reported as unverifiable and
  skipped. Guarded by `tests/test_compile_script.py`.

- **Every package is self-contained (client bundled)**: the `deb`/`rpm` targets
  now bundle the `hsync` engine like `native`/`dmg`/`appimage`, so the packages
  no longer declare `Depends:`/`Requires: hsync-client` and need no extra
  package. Host `deb`/`rpm` bundle `CLIENT_BINARY` (verified against
  `HSYNC_VERSION`); `deb-all`/`rpm-all` compile the per-arch client **inside the
  same Docker container** as the GUI (same arch and distro → same glibc; the
  client's `rpi` arm64 binary would not run on Rocky's older glibc) and stage it
  at `hsync_desktop/bin/hsync` (keeping the platform suffix, i.e. `hsync.exe` on
  Windows, so `find_hsync_binary` finds it). Every client-bundling target
  (`native`, `rpi`, `deb`, `rpm`, `appimage`, `dmg`) calls
  `_require_bundled_client`, which fails the build if no client was staged.
  `find_hsync_binary` (`engine/cli.py::find_hsync_binary`) resolves the bundled
  binary against the **package root** (`hsync_desktop/bin`), so it stays correct
  from the `engine/` subpackage and in a frozen onefile/onedir bundle. The `.deb`
  `Depends:` is computed from the payload
  (`packaging/deb/deb-depends.sh::_compute_runtime_depends`: external DT_NEEDED
  → packages via `ldconfig`/`dpkg -S`) instead of a hand-maintained list, which
  had drifted (declared
  bundled libraries, missed `libxcb1`/`libdrm2`/`libwayland-*`); the `.rpm`
  `Requires` carries the RHEL names of that same external set. Guarded by
  `tests/test_compile_script.py`.
- **Per-arch Linux builder base**: PySide6 6.12 ships its aarch64 wheel as
  `manylinux_2_39` (x86_64 as `manylinux_2_34`), so the Debian 12 / RHEL 9 bases
  cannot host the arm64 build. `deb-all` builds amd64 on `python:3.12-bookworm`
  (glibc 2.36) and arm64 on `python:3.12-trixie` (glibc 2.41); `rpm-all` builds
  x86_64 on `rockylinux:9` (glibc 2.34, hence `el9`) and aarch64 on
  `almalinux:10` (glibc 2.39, hence `el10`). The aarch64 packages therefore
  require glibc ≥ 2.39 while the amd64 ones keep their older-distro reach.
- **Settings options are plain form rows; the page keeps one bounded column**:
  every option is a `QFormLayout` row (`widgets/forms.py::add_row`): caption in
  the label column, control in the field column, label alignment and field growth
  left to the Qt style hints, so the dialog follows the host OS instead of
  copying one desktop's chrome. The previous right-aligned `switch_row`
  container could leave a short caption hundreds of pixels from its switch, and
  the GNOME-style card ("switch on the row's trailing edge") was rejected as
  DE-specific for a Linux/Windows/macOS app. `settings/tab_layout.py::_CenteredColumn`
  caps and centres the content, so a wider window grows the margins, not the
  form. Captions carry no trailing colon (the label column separates them; only
  key/value rows such as the detail panel or the status bar keep one), matching
  the WD OS5 web UI and the modern desktop convention. Switches are kept although
  a checkbox matches a Save/Cancel dialog better (NN/g: a toggle switch should
  take immediate effect); revisit if the dialog ever applies settings instantly.
- **Stop is non-blocking and immediately visible**: the former `HsyncEngine.stop`
  blocked the Qt main thread in `waitForFinished(5000)` (plus `kill()` and 3 s),
  so clicking Stop gave no
  feedback until the child had already exited and the user could think nothing was
  happening. The engine now exposes `request_stop`
  (`engine/process.py::HsyncEngine.request_stop`: `SIGTERM` at once, `kill()` after
  a 5 s grace, `stop_timeout` if the child never reports `finished`) for the user
  action, and keeps the blocking `stop_and_wait`
  (`engine/process.py::HsyncEngine.stop_and_wait`) for the callers that need the
  process gone before continuing (app quit, retry after an auth error, setup
  wizard). The window shows a `Stopping…` badge, disables Start/Stop/Check-changes
  (tray too) and raises a progress toast at once
  (`main_window/start.py::StartMixin._on_stop`,
  `main_window/start.py::StartMixin._enter_stopping_ui`), settled by
  `process_finished` or, on the engine's `stop_timeout`, by
  `main_window/start.py::StartMixin._on_stop_timeout` with the `notif.stop_timeout`
  warning. Guarded by `tests/test_engine_process.py` and `tests/test_main_window.py`.
- **A warning with a host remedy deep-links to the page that carries the
  commands**: the persistent-warning banner used one link (`TROUBLESHOOTING` →
  `docs/troubleshooting.md`) for every engine warning, but the desktop symptom
  guide never documented the file-watcher/inotify limit, whose per-platform
  commands live in the client guide. `docs_links.py::WATCHER_LIMITS` now points at
  `hsync-client/docs/troubleshooting.md#the-file-watcher-degrades-to-polling-inotify-limits`
  and `main_window/ui.py::UiBuildMixin._on_engine_warning` selects it exactly when
  `warnings.py::remedy_text` produced a remedy (a watcher reason), keeping
  `TROUBLESHOOTING` otherwise; both share the `notif.open_guide` label, so no new
  locale key. The desktop `docs/troubleshooting.md` also gained a watcher section
  that links the client one. Rejected: one link for all warnings (leaves the
  actionable case on a page without commands) and a new label per target (locale
  churn for no extra clarity). Guarded by `tests/test_docs_links.py` and
  `tests/test_main_window.py`.
- **Preview and sync are one mechanism with two intents**: *Preview changes* is
  not an offline comparison — the client cannot plan against an inventory
  without a session — so the action runs the same `--dry-run` as Start and a
  confirmation applies with the same `SYNC` on the already-running process
  (`main_window/start.py::StartMixin._begin_start`,
  `main_window/actions.py::ActionsMixin._show_preview_summary`). Only
  `_preview_intent` differs: a `start` run keeps *Cancel*/*Synchronize* and the
  empty-plan `SYNC`, a `preview` run offers *Close*/*Sync now* (Close default),
  never applies an empty plan and never sends `SYNC` from that branch. The wait
  is a visible state (`StartMixin._enter_preparing_plan_ui`: progress toast +
  `notif.preparing_plan` marker) instead of a silent one. Restarting the engine
  on accept was rejected: it would re-handshake and could produce a plan
  different from the one the user confirmed. An unattended start never opens the
  dialog (`ActionsMixin._apply_automatic_plan`): it applies a plan that deletes
  nothing and otherwise stops with `notif.plan_needs_confirmation`. Whether a
  dry-run is unattended is `_dry_run_unattended`, recorded per dry-run, not the
  run's `_start_is_automatic`: `_retry_after_auth_fix` clears it after the
  credential prompt, so a retried plan is confirmed like a manual one. The apply
  is reported through `_report_result` (toast + OS notification once the window
  is out of focus) and the waiting-plan warning uses the `sync` notification
  category. The action lives in the Sync menu and the tray only — no action-bar
  button, no new icon. Guarded by `tests/test_preview_summary_dialog.py`,
  `tests/test_main_window.py` and `tests/test_system_tray.py`.
