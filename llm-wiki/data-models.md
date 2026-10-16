# HSYNC Desktop — Data models & state

The desktop holds only **view-state**: it has no wire/sync models. Protocol types
it reads are imported from `hsync-common`; the rest are local UI dataclasses/enums.

## Reused common types (parsed, not redefined)

| Type | Source | Used by |
| ---- | ------ | ------- |
| `UiEventName` / `UiEventDict` / `parse_event_line` | `hsync_common.protocol.events` | `engine._handle_event` (`engine/process.py::HsyncEngine._handle_event`) |
| `CapabilitiesDoc` / `parse_capabilities` | `hsync_common.protocol.capabilities` | `engine.get_binary_capabilities` (`engine/cli.py::get_binary_capabilities`); UI gating |

Event payload shape + capability schema are SSOT in
[common data-models](../../hsync-common/llm-wiki/data-models.md). The desktop
must not assume fields beyond that schema.

## Local view-state

### FileTransfer (`file_panel/models.py::FileTransfer`)

Dataclass for one row in the transfer table.

| Field | Notes |
| ----- | ----- |
| `filepath` / `direction` | path + `"↓"`/`"↑"` |
| `size` / `bytes_transferred` | progress inputs |
| `start_time` | for ETA |
| `status` | a `TransferStatus` |
| `mtime` / `client_cid` / `client_ip` | metadata for detail pane |

Derived: `filename` (`file_panel/models.py::FileTransfer.filename`), `path` (`file_panel/models.py::FileTransfer.path`),
`remaining` (`file_panel/models.py::FileTransfer.remaining`), `eta_seconds`
(`file_panel/models.py::FileTransfer.eta_seconds`, computed from the elapsed rate only while `DOWNLOADING`/`UPLOADING`).

### TransferStatus (`file_panel/models.py::TransferStatus`)

Enum of row states: `LOCAL`, `SYNCED`, `TO_DOWNLOAD`/`TO_UPLOAD`/`TO_DELETE`/
`TO_RENAME`, `DOWNLOADING`/`UPLOADING`, `DELETED`, `COMPLETED`, `ERROR` (plus
legacy `QUEUED`/`TRANSFERRING`). Render maps: `STATUS_COLORS` (`file_panel/models.py::STATUS_COLORS`),
`_NO_PROGRESS_STATUSES` (`file_panel/models.py::_NO_PROGRESS_STATUSES`).

### TransferStats (`engine/process.py::TransferStats`)

Per-session counters accumulated by the engine; `reset` (`engine/process.py::TransferStats.reset`)
clears them and the path sets. `files_sent` / `files_received` are the size of
`sent_paths` / `received_paths`, the distinct bucket-relative paths moved this
session (a repeated transfer stays one; `record_content` adds a path,
`follow_rename` moves identity on a rename — including `src/` descendants for a
directory — and a rename of an untracked path is a no-op). `bytes_sent` /
`bytes_received` sum every content transfer, repeats included. Keys come from
`engine/process.py::HsyncEngine._relative_key` against `HsyncEngine.local_root`.

## Persisted configuration

Not a model — `QSettings` keyed by `config.py` `DEFAULT_*` constants. Secrets are
stored Fernet-encrypted (`crypto.py`, `_ENC_PREFIX` marker). See
[settings.md](modules/settings.md) for keys, encryption, and the
config→CLI-args mapping.
