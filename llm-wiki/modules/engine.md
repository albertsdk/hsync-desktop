# HSYNC Desktop — Engine (subprocess bridge)

`engine.py` is the only module that talks to the `hsync` binary. It owns the
`QProcess`, the secret/event pipes, and the event→signal translation.

## Binary discovery & compatibility

| Symbol | Line | Role |
| ------ | ---- | ---- |
| `find_hsync_binary` | `engine.py:145` | locate bundled or sibling executable |
| `_parse_version` | `:170` | extract `X.Y.Z` from `--version` output (shared by sync + async paths) |
| `get_binary_version` | `:176` | run `--version`, parse (pure, uncached) |
| `get_binary_capabilities` | `:194` | run `--capabilities-json` → `parse_capabilities` (common SSOT); includes `delta` capability for rsync-style block sync |
| `is_binary_version_compatible` | `:225` | pure major-version comparison |
| `get_binary_version_cached` | `:290` | `get_binary_version` + QSettings cache keyed by `(path, size, mtime_ns)` |
| `get_binary_capabilities_cached` | `:301` | `get_binary_capabilities` + QSettings cache (only parsed docs are stored) |
| `BinaryVersionProbe` | `:324` | async `QProcess` resolver for `--version` (cache hit emits synchronously; hung binary killed after 5 s) |
| `_probe_settings` | `:236` | QSettings accessor (patchable in tests) |
| `_platform_tag` | `:96` | OS/arch tag for bundled-binary lookup |

The version/capabilities probes are cached in `QSettings(SETTINGS_ORG,
SETTINGS_APP)` under `binary/version_cache` / `binary/capabilities_cache`. An
entry is fresh only while the on-disk binary's `(size, mtime_ns)` match the
values captured at probe time, so a replaced bundled binary invalidates the
cache. `main.py` resolves the version via `BinaryVersionProbe` (non-blocking);
the settings dialog uses the synchronous cached `get_binary_capabilities_cached`
to gate controls at first paint.

## HsyncEngine lifecycle

| Symbol | Line | Role |
| ------ | ---- | ---- |
| `HsyncEngine` | `engine.py:188` | `QObject` wrapper around the process |
| `start` | `:282` | open pipes, write secrets, launch `QProcess`, attach notifier |
| `stop` | `:404` | terminate the process |
| `sync` / `preview` | `:422` / `:431` | trigger a cycle / dry-run via stdin command |
| `set_sync_direction` / `set_bandwidth` | `:435` / `:443` | live runtime commands |
| `_send_command` | `:459` | write a JSON command to the process stdin |
| `_on_stdout` | `:473` | forward raw log lines (`log_received`) |
| `_on_finished` / `_on_error` | `:486` / `:500` | exit + QProcess error mapping |
| `_set_status` | `:518` | debounced `status_changed` emit |

State accessors: `is_running` (`:249`), `is_master` (`:253`), `peer_count`
(`:257`), `status` (`:261`), `cid` (`:265`), `server_ip` (`:269`),
`binary_path` get/set (`:273`/`:277`).

## Secrets & event channel (pipe FDs, never argv)

`start` (`engine.py:302`) builds inheritable pipes so secrets never hit the
command line:

- `write_secret_pipe` (`engine.py`): write secret, close write end, mark the
  read fd inheritable (`os.set_inheritable`). Python 3.4+ fds are CLOEXEC by
  default; without this the QProcess child would see a closed `--api-key-fd` /
  `--p2p-key-fd`.
- `--api-key-fd` / `--p2p-key-fd`: values from `decrypt_value` on
  `connection/api_key` and `p2p/key` (both Fernet at rest).
- `--events-json-fd`: child writes JSON-Lines; parent watches the read end.
  Same inheritable requirement as the secret read fds. On start failure all
  FDs are closed.

## Event → Signal bridge

`_on_events_available` (`engine.py:549`) reads ready lines, `parse_event_line`
(`:568`, common) yields a `UiEventDict`, and `_handle_event` (`:572`) maps each
`UiEventName` to a typed Qt `Signal`:

| `UiEventName` | Signal | Line |
| ------------- | ------ | ---- |
| `status` / `peers` / `role` | `status_changed` / `peers_changed(connected, total)` / `master_changed` | `:581`/`:583`/`:588` |
| `bucket` / `group` / `session` / `server` | `bucket_detected` / `group_detected` / … / `server` ip | `:593`–`:599` |
| `discovery` | `discovery_changed(plan, bootnode)` — the active plan (mdns/bootnode) at startup | `:798` |
| `transfer` / `rename` / `dir_created` / `progress` | `file_transferred` / `file_renamed` / `directory_created` / `file_progress` | `:612`–`:617` |
| `sync_complete` / `transfer_failed` / `sync_paused` | `sync_completed` / `transfer_failed` / `sync_paused` | `:620`/`:613`/`:614` |
| `error` / `auth_error` / `path_not_found` | `error_occurred` / `auth_error_occurred` / `path_not_found` | `:621`/`:623`/`:622` |
| `master_conflict` / `no_master` | `master_conflict` / `no_master_warning` | `:624`/`:625` |
| `duplicate_identity` | `duplicate_identity(peer_cid, peer_address)` | `:656` |
| `preview_start` / `preview_end` / `file_status` / `rename_status` | preview/file-status signals | `:648`–`:660` |

Full signal list: `engine.py:197`–`:222`. Event names + payload shape are SSOT in
`hsync_common.protocol.events`
([common data-models](../../../hsync-common/llm-wiki/data-models.md)).

`TransferStats` (`engine.py:45`) accumulates per-session counters (`reset:53`).

## Delta transfer compatibility

The desktop GUI is **compatible with delta transfer** (rsync-style block sync)
without requiring UI changes. Delta transfer is transparent to the user: when both
the client and server/master support the `delta` capability, large files with small
changes are transferred more efficiently by sending only changed blocks. The
capability is negotiated automatically via `--capabilities-json`; no desktop-side
configuration is needed. Falls back to full transfer if delta is not supported or
fails.

> Contract rule (ADR 0004): never bypass this bridge by importing client code —
> see [decisions.md](../decisions.md).
