# HSYNC Desktop — Engine (subprocess bridge)

The `engine/` package is the only code that talks to the `hsync` binary:
`engine/cli.py` holds the synchronous helpers (binary rendezvous, version /
capabilities probe + cache, trust-store subcommands) and `engine/process.py`
owns the `QProcess`, the secret/event pipes and the event→signal translation.
`engine/__init__.py` re-exports the former `engine.py` surface.

## Async probe runner (`engine/async_probe.py`)

| Symbol | Location | Role |
| ------ | -------- | ---- |
| `AsyncProbe` | `engine/async_probe.py::AsyncProbe` | run one blocking probe on a `QThread`; a new `start` supersedes, `cancel` drops the result |
| `ProbeOutcome` | `engine/async_probe.py::ProbeOutcome` | probe result (`ok`, `status`, `fingerprint`, `reason`) |
| `_PENDING` | `engine/async_probe.py::_PENDING` | registry keeping a cancelled probe's thread and worker alive until the blocking call returns |

Every blocking probe — the `engine/probes.py` HTTP calls and the
`engine/cli.py` fingerprint subprocesses — runs through `AsyncProbe`: on the UI
thread it freezes the window for the whole timeout (the desktop environment then
reports the app as unresponsive). Consumers: `settings/dialog.py` (both Test
Connection actions), `trusted_keys.py` (Read from server), `main_window/trust.py`
(start pre-flight) and the wizard connection page.

## Binary rendezvous & compatibility

| Symbol | Location | Role |
| ------ | -------- | ---- |
| `find_hsync_binary` | `engine/cli.py::find_hsync_binary` | locate bundled or sibling executable |
| `_parse_version` | `engine/cli.py::_parse_version` | extract `X.Y.Z` from `--version` output (shared by sync + async paths) |
| `get_binary_version` | `engine/cli.py::get_binary_version` | run `--version`, parse (pure, uncached) |
| `get_binary_capabilities` | `engine/cli.py::get_binary_capabilities` | run `--capabilities-json` → `parse_capabilities` (common SSOT); includes `delta` capability for rsync-style block sync |
| `is_binary_version_compatible` | `engine/cli.py::is_binary_version_compatible` | pure major-version comparison |
| `get_binary_version_cached` | `engine/cli.py::get_binary_version_cached` | `get_binary_version` + QSettings cache keyed by `(path, size, mtime_ns)` |
| `get_binary_capabilities_cached` | `engine/cli.py::get_binary_capabilities_cached` | `get_binary_capabilities` + QSettings cache (only parsed docs are stored) |
| `BinaryVersionProbe` | `engine/cli.py::BinaryVersionProbe` | async `QProcess` resolver for `--version` (cache hit emits synchronously; hung binary killed after 5 s) |
| `_probe_settings` | `engine/cli.py::_probe_settings` | QSettings accessor (patchable in tests) |
| `_platform_tag` | `engine/cli.py::_platform_tag` | OS/arch tag for bundled-binary lookup |

The version/capabilities probes are cached in `QSettings(SETTINGS_ORG,
SETTINGS_APP)` under `binary/version_cache` / `binary/capabilities_cache`. An
entry is fresh only while the on-disk binary's `(size, mtime_ns)` match the
values captured at probe time, so a replaced bundled binary invalidates the
cache. `main.py` resolves the version via `BinaryVersionProbe` (non-blocking);
the settings dialog uses the synchronous cached `get_binary_capabilities_cached`
to gate controls at first paint.

## HsyncEngine lifecycle

| Symbol | Location | Role |
| ------ | -------- | ---- |
| `HsyncEngine` | `engine/process.py::HsyncEngine` | `QObject` wrapper around the process |
| `start` | `engine/process.py::HsyncEngine.start` | open pipes, write secrets, launch `QProcess`, attach notifier |
| `request_stop` | `engine/process.py::HsyncEngine.request_stop` | user-facing, **non-blocking** stop: `SIGTERM` at once, `kill()` after the grace, `stop_timeout` if the child still never reports `finished`. The GUI never freezes on it |
| `stop_and_wait` | `engine/process.py::HsyncEngine.stop_and_wait` | blocking stop for the callers that need the child gone first (quit, restart after an auth error, setup wizard): `SIGTERM`, `kill()` after 5 s, bounded wait |
| `sync` / `preview` | `engine/process.py::HsyncEngine.sync` / `engine/process.py::HsyncEngine.preview` | trigger a cycle / dry-run via stdin command |
| `set_sync_direction` / `set_bandwidth` | `engine/process.py::HsyncEngine.set_sync_direction` / `engine/process.py::HsyncEngine.set_bandwidth` | live runtime commands |
| `_send_command` | `engine/process.py::HsyncEngine._send_command` | write a JSON command to the process stdin |
| `_on_stdout` | `engine/process.py::HsyncEngine._on_stdout` | forward raw log lines (`log_received`) and harvest the run's last `ERROR`/`CRITICAL` messages with the shared grammar (`hsync_common.logger.LOG_LINE_RE`) into `_recent_errors` |
| `_on_finished` / `_on_error` | `engine/process.py::HsyncEngine._on_finished` / `engine/process.py::HsyncEngine._on_error` | exit + QProcess error mapping; also clears the stop escalation timers. The `desc` passed to `process_finished` follows **operator intent** first: a run ended by `request_stop`/`stop_and_wait` reports `stopped` even when it exits `0` normally, and only an exit nobody asked for reports `normal`/`crashed` |
| `_set_status` | `engine/process.py::HsyncEngine._set_status` | debounced `status_changed` emit |

State accessors: `is_running` (`engine/process.py::HsyncEngine.is_running`), `is_master` (`engine/process.py::HsyncEngine.is_master`),
`status` (`engine/process.py::HsyncEngine.status`), `cid` (`engine/process.py::HsyncEngine.cid`), `server_ip` (`engine/process.py::HsyncEngine.server_ip`),
`binary_path` get/set (`engine/process.py::HsyncEngine.binary_path`).

Stop escalation: `request_stop` (`engine/process.py::HsyncEngine.request_stop`) sends
`SIGTERM` and returns immediately, so the window stays responsive; the client unwinds
on `SIGTERM` like `Ctrl+C` (stops its servers, flushes and closes the log sinks), so a
stop normally ends with a normal exit. `_stop_grace_timer` escalates to `kill()` and
`_stop_safety_timer` (`engine/process.py::HsyncEngine._on_stop_safety_elapsed`)
declares the run stopped and emits `stop_timeout`
(`engine/process.py::HsyncEngine.stop_timeout`) when the child never reports
`finished` — the only path that ends a run without it. `_on_finished` clears both
timers; `stop_and_wait` is the blocking variant (same escalation, bounded wait).

## Secrets & event channel (pipe FDs, never argv)

`start` (`engine/process.py::HsyncEngine.start`) builds inheritable pipes so secrets never hit the
command line:

- `write_secret_pipe` (`engine/process.py::write_secret_pipe`): write secret, close write end, mark the
  read fd inheritable (`os.set_inheritable`). Python 3.4+ fds are CLOEXEC by
  default; without this the QProcess child would see a closed `--api-key-fd` /
  `--p2p-key-fd`.
- `--api-key-fd` / `--p2p-key-fd`: values from `decrypt_value` on
  `connection/api_key` and `p2p/key` (both Fernet at rest).
- `p2p_secret_option` (`engine/process.py::p2p_secret_option`) turns the mode
  resolved by `p2p_secret_mode` (`engine/process.py::p2p_secret_mode`) into
  `--p2p-key-fd` or `--p2p-passphrase-fd`. A secret below
  `hsync_common.protocol.rdv_tokens::MIN_GROUP_KEY_CHARS` cannot be a raw group
  key (the client rejects it), so it always travels as a passphrase and the
  client derives the key. That keeps a legacy `p2p/key_mode=raw` install with a
  short secret working instead of aborting at startup.
- `--events-json-fd`: child writes JSON-Lines; parent watches the read end.
  Same inheritable requirement as the secret read fds. On start failure all
  FDs are closed.

## Event → Signal bridge

`_on_events_available` (`engine/process.py::HsyncEngine._on_events_available`) reads ready lines, `parse_event_line`
(common) yields a `UiEventDict`, and `_handle_event` (`engine/process.py::HsyncEngine._handle_event`) maps each
`UiEventName` to a typed Qt `Signal`:

| `UiEventName` | Signal |
| ------------- | ------ |
| `status` / `peers` / `role` | `status_changed` / `peers_changed(connected, total)` / `master_changed` |
| `bucket` / `group` / `session` / `server` | `bucket_detected` / `group_detected` / … / `server` ip |
| `rendezvous` | `rendezvous_changed(plan, rendezvous)` — the active plan (mdns/rendezvous) at startup |
| `transfer` / `rename` / `dir_created` | `file_transferred(direction, file, size)` / `file_renamed(old, new)` / `directory_created(path)` |
| `progress` | `file_progress(file, transferred, total, op)` — `op` gives the direction of a file that has no local row yet |
| `sync_complete` / `transfer_failed` / `sync_paused` | `sync_completed(dict)` (the cycle counters) / `transfer_failed` / `sync_paused` |
| `security_rejected` | `security_rejected(op, path, message)` — unsafe remote path refused by the inbound guards |
| `error` / `auth_error` / `auth_required` / `path_not_found` | `error_occurred` / `auth_error_occurred` / `auth_required_occurred` / `path_not_found` |
| `warning` | `warning_occurred(message, source, transient, details)` — a non-fatal condition the run continues through (degraded watcher, unreachable rendezvous, low disk space, a vanished shared folder); `source` is the client's stable subsystem id, `transient` (from `reason="transient"`) means it heals itself and gets an auto-hiding toast instead of a persistent banner, and `details` carries `reason` plus `needed`/`limit` when the client measured a bounded resource (the UI turns them into a localized remedy) |
| `ready` | *(no signal)* — ends the startup phase; see the startup-failure note below |
| `master_conflict` / `no_master` / `no_peers` | `master_conflict` / `no_master_warning` / `no_peers_warning` |
| `sync_pending` | `sync_pending(reason, devices, expected)` — `no_device`, or `awaiting_inventory` with the published/expected inventory counts |
| `duplicate_identity` | `duplicate_identity(peer_cid, peer_address)` |
| `pairing_needed` / `fingerprint_changed` | `pairing_needed(scope, peer_cid, peer_address, fingerprint)` / `fingerprint_changed(scope, peer_cid, peer_address, fingerprint)` |
| `preview_start` / `preview_end` | `preview_started` / `preview_ended` — the comparison this window requested |
| `status_pass_start` / `status_pass_end` | `status_pass_started` / `status_pass_ended` — the classification pass of a serving device |
| `device_status` | `device_status(cid, pending_here, pending_there, held)` — one row per live device inside a serving pass |
| `preview_skipped` / `preview_warning` | `preview_skipped(reason, count, size)` — deletions the policy dropped — / `preview_warning(reason, deletes, local)` — a plan the mass-deletion guard will pause |
| `file_status` / `rename_status` | `file_status(status, filepath, size, holders, devices)` / `file_rename_status(old, new, size)` |

Mappings live in `_handle_event` (`engine/process.py::HsyncEngine._handle_event`). Full signal list: `HsyncEngine`
Signal declarations (`engine/process.py::HsyncEngine`). Event names + payload shape are SSOT in
`hsync_common.protocol.events`
([common data-models](../../../hsync-common/llm-wiki/data-models.md)).

`error_occurred` carries a second `reason` argument so the UI can name the cause:
`""` (generic, from the client's `error` event), `"connection"` (a
`NetworkError` that is not a `ServerError`, tagged by the client's preview/sync),
`"process"` (a `QProcess` read/write/crash error), `"start"` (the engine could
not be launched) and `"startup"` (a fatal startup error the client reported just
before exiting).

**Startup failures** (`engine/process.py::HsyncEngine.startup_failed`): a config
error exits *normally* with a non-zero code, which `process_finished` alone cannot
tell apart from a clean stop. The engine therefore tracks a startup phase —
`_ready` is set by the client's `ready` event (or by any `status` event, the
fallback for older clients) and the merged stdout/stderr tail is buffered until
then. If the process exits while still in that phase (and not because of an
operator stop), it emits `startup_failed(exit_code, tail)`. A received
`error(reason="startup")` suppresses that safety net so the failure is reported
exactly once. The window presents a **manual** start with a modal dialog and an
**automatic** start (`_on_auto_start`, OS autostart in the tray) with the
persistent error banner + tray notification
(`main_window/events.py::EventsMixin._present_startup_failure`).

**Fatal exits after readiness** (`engine/process.py::HsyncEngine.fatal_exit`): the
client can still refuse once the startup phase is over — the per-directory
instance lock is taken just before the run loop, and a trust/connectivity gate or
an unexpected exception can also end the process — always with exit code `1`
(`ExitCode.FATAL`; `2..5` are verdicts of a completed cycle, never a failure).
Since the startup tail is discarded at readiness, `_on_stdout` keeps the run's
last `ERROR`/`CRITICAL` messages (SGR stripped, level parsed from the documented
log format) and `_on_finished` emits `fatal_exit(exit_code, last_error)` for that
code when no `error(reason="startup")` was reported. The window presents it once
(`main_window/events.py::EventsMixin._on_fatal_exit` → `_report_engine_stop_failure`)
unless the run was a user stop, a scoped Send/Receive, or the client already
explained itself through `error_occurred`. `no_peers_warning` is emitted when a p2p one-shot aborts because
no peer was discovered.

Both `auth_error` (invalid/missing key) and `auth_required` (a shared key is
required but missing) drive the same credential re-prompt
(`main_window/trust.py::TrustMixin._on_auth_error`): the engine is stopped, the p2p-password
or API-key dialog opens (pre-filled with the current value) and a retry follows
on accept; events arriving while the prompt is open are ignored.

`TransferStats` (`engine/process.py::TransferStats`) accumulates per-session counters (`engine/process.py::TransferStats.reset`).
`files_sent` / `files_received` are the size of the distinct-path sets
(`TransferStats.record_content` adds a path on a completed content upload/download,
`TransferStats.follow_rename` moves identity on a rename so a moved file is not
counted twice — an untracked source is a no-op); `bytes_sent` / `bytes_received`
sum every content transfer, repeats included. The identity key is bucket-relative
via `HsyncEngine._relative_key`, using `HsyncEngine.local_root` fed from the
selected path.

## Trust (known-hosts / known-peers) helpers

The GUI edits the client's three SSH-style trust stores through subprocess helpers
(one `hsync trust …` namespace) so it never touches the store files directly:

| Symbol | Location | Role |
| ------ | -------- | ---- |
| `_run_hsync_success` / `_run_hsync_json` / `_run_hsync_line` | `engine/cli.py::_run_hsync_success` / `engine/cli.py::_run_hsync_json` / `engine/cli.py::_run_hsync_line` | run `<binary> <args>`; return exit-0 flag / parsed JSON / last stdout line (None on any failure) |
| `fetch_rendezvous_fingerprint` / `fetch_server_fingerprint` | `engine/cli.py::fetch_rendezvous_fingerprint` / `engine/cli.py::fetch_server_fingerprint` | `hsync trust {rendezvous,server} fingerprint` (raw probe) |
| `list_rendezvous_trust` / `add_rendezvous_trust` / `remove_rendezvous_trust` | `engine/cli.py::list_rendezvous_trust` / `engine/cli.py::add_rendezvous_trust` / `engine/cli.py::remove_rendezvous_trust` | `hsync trust rendezvous-server {list --json,add,remove}` |
| `list_server_trust` / `add_server_trust` / `remove_server_trust` | `engine/cli.py::list_server_trust` / `engine/cli.py::add_server_trust` / `engine/cli.py::remove_server_trust` | `hsync trust server {list --json,add,remove}` |
| `list_peer_pins` / `add_peer_pin` / `remove_peer_pin` | `engine/cli.py::list_peer_pins` / `engine/cli.py::add_peer_pin` / `engine/cli.py::remove_peer_pin` | `hsync trust peer {list --json,add,remove}` |
| `supports_peer_trust` | `engine/cli.py::supports_peer_trust` | True when the binary advertises the `trust` subcommand; permissive (True) on an unknown `CapabilitiesDoc` |
| `_run_hsync_capture` | `engine/cli.py::_run_hsync_capture` | the single `subprocess.run` entry point; returns the `CompletedProcess` (stdout/stderr/exit code) or None when the binary cannot run. The three helpers above are thin wrappers |
| `reset_sync_state` | `engine/cli.py::reset_sync_state` | `hsync state reset --folder DIR --quarantine --json` → `ResetStateResult` (`ok`, `found`, `versions`, `tombstones`, `quarantined`, `message`), parsed from the client's `versions_deleted`/`tombstones_deleted`; an unreadable DB is moved aside (`--quarantine`) so `quarantined` carries the new path; a non-zero exit carries the client's own text (e.g. the instance-lock holder). 60 s timeout: the command takes the folder lock and rewrites a SQLite file |

## Delta transfer compatibility

The desktop GUI is **compatible with delta transfer** (rsync-style block sync).
Delta transfer is transparent by default: when both
the client and server/master support the `delta` capability, large files with small
changes are transferred more efficiently by sending only changed blocks. The
capability is negotiated automatically via `--capabilities-json`. The Advanced tab
adds optional overrides (enable/disable and the per-mode minimum sizes), emitted by
`settings/cli_args.py::build_hsync_args` as `--no-delta`, `--delta-min-file-size`
and `--delta-min-file-size-p2p`; defaults keep the engine behaviour. Falls back to
full transfer if delta is not supported or fails.

> Contract rule (ADR 0004): never bypass this bridge by importing client code —
> see [decisions.md](../decisions.md).
