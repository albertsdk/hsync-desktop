# HSYNC Desktop — Engine (subprocess bridge)

`engine.py` is the only module that talks to the `hsync` binary. It owns the
`QProcess`, the secret/event pipes, and the event→signal translation.

## Binary discovery & compatibility

| Symbol | Line | Role |
| ------ | ---- | ---- |
| `find_hsync_binary` | `engine.py:99` | locate bundled (`:106`) or sibling (`:118`) executable |
| `get_binary_version` | `:124` | run `--version`, parse |
| `get_binary_capabilities` | `:143` | run `--capabilities-json` → `parse_capabilities` (common SSOT); includes `delta` capability for rsync-style block sync |
| `check_binary_compatibility` | `:166` | gate UI on protocol/app compatibility |
| `_platform_tag` | `:74` | OS/arch tag for bundled-binary lookup |

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

`start` (`engine.py:282`) builds inheritable pipes so secrets never hit the
command line (`:315`):

- `--api-key-fd` (`:345`) and `--lan-key-fd` (`:358`): secret written to the
  write end, read end inherited by the child (`FD_CLOEXEC` on parent ends).
- `--events-json-fd` (`:366`): child writes JSON-Lines events to the inherited
  write end; the parent keeps the read end (`_events_read_fd`, `:242`) watched by
  a `QSocketNotifier` (`_events_notifier`, `:243`). On start failure all FDs are
  closed (`:374`).

## Event → Signal bridge

`_on_events_available` (`engine.py:549`) reads ready lines, `parse_event_line`
(`:568`, common) yields a `UiEventDict`, and `_handle_event` (`:572`) maps each
`UiEventName` to a typed Qt `Signal`:

| `UiEventName` | Signal | Line |
| ------------- | ------ | ---- |
| `status` / `peers` / `role` | `status_changed` / `peers_changed(connected, total)` / `master_changed` | `:581`/`:583`/`:588` |
| `bucket` / `group` / `session` / `server` | `bucket_detected` / `group_detected` / … / `server` ip | `:593`–`:599` |
| `transfer` / `rename` / `dir_created` / `progress` | `file_transferred` / `file_renamed` / `directory_created` / `file_progress` | `:603`–`:611` |
| `sync_complete` / `transfer_failed` / `sync_paused` | `sync_completed` / `transfer_failed` / `sync_paused` | `:617`/`:619`/`:625` |
| `error` / `auth_error` / `path_not_found` | `error_occurred` / `auth_error_occurred` / `path_not_found` | `:631`/`:633`/`:637` |
| `master_conflict` / `no_master` | `master_conflict` / `no_master_warning` | `:640`/`:646` |
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
