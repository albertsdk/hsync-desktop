# HSYNC Desktop — Data models & state

The desktop holds only **view-state**: it has no wire/sync models. Protocol types
it reads are imported from `hsync-common`; the rest are local UI dataclasses/enums.

## Reused common types (parsed, not redefined)

| Type | Source | Used by |
| ---- | ------ | ------- |
| `UiEventName` / `UiEventDict` / `parse_event_line` | `hsync_common.protocol.events` | `engine._handle_event` (`engine.py:572`) |
| `CapabilitiesDoc` / `parse_capabilities` | `hsync_common.protocol.capabilities` | `engine.get_binary_capabilities` (`engine.py:143`); UI gating |

Event payload shape + capability schema are SSOT in
[common data-models](../../hsync-common/llm-wiki/data-models.md). The desktop
must not assume fields beyond that schema.

## Local view-state

### FileTransfer (`file_panel/models.py:71`)

Dataclass for one row in the transfer table.

| Field | Notes |
| ----- | ----- |
| `filepath` / `direction` | path + `"↓"`/`"↑"` |
| `size` / `bytes_transferred` | progress inputs |
| `start_time` | for ETA |
| `status` | a `TransferStatus` |
| `mtime` / `client_cid` / `client_ip` | metadata for detail pane |

Derived: `filename` (`:84`), `path` (`:88`), `remaining` (`:93`), `eta_seconds`
(`:97`).

### TransferStatus (`file_panel/models.py:23`)

Enum of row states: `LOCAL`, `SYNCED`, `TO_DOWNLOAD`/`TO_UPLOAD`/`TO_DELETE`/
`TO_RENAME`, `DOWNLOADING`/`UPLOADING`, `DELETED`, `COMPLETED`, `ERROR` (plus
legacy `QUEUED`/`TRANSFERRING`). Render maps: `STATUS_COLORS` (`:42`),
`_NO_PROGRESS_STATUSES` (`:60`).

### TransferStats (`engine.py:45`)

Per-session counters accumulated by the engine; `reset` (`engine.py:53`).

## Persisted configuration

Not a model — `QSettings` keyed by `config.py` `DEFAULT_*` constants. Secrets are
stored Fernet-encrypted (`crypto.py`, `_ENC_PREFIX` marker). See
[settings.md](modules/settings.md) for keys, encryption, and the
config→CLI-args mapping.
