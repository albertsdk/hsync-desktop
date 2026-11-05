# HSYNC Desktop — Data models & state

The desktop holds only **view-state**: it has no wire/sync models. Protocol types
it reads are imported from `hsync-common`; the rest are local UI dataclasses/enums.

## Reused common types (parsed, not redefined)

| Type | Source | Used by |
| ---- | ------ | ------- |
| `UiEventName` / `UiEventDict` / `parse_event_line` | `hsync_common.protocol.events` | `engine._handle_event` (`hsync_desktop/engine/process.py::HsyncEngine._handle_event`) |
| `CapabilitiesDoc` / `parse_capabilities` | `hsync_common.protocol.capabilities` | `engine.get_binary_capabilities` (`hsync_desktop/engine/cli.py::get_binary_capabilities`); UI gating |

Event payload shape + capability schema are SSOT in
[common data-models](../../hsync-common/llm-wiki/data-models.md). The desktop
must not assume fields beyond that schema.

## Local view-state

### FileTransfer (`hsync_desktop/file_panel/models.py::FileTransfer`)

Dataclass for one row in the transfer table.

It is a `slots=True` dataclass (the panel can hold one row per scanned file, so
no per-instance `__dict__`), and its rate-sampling deque (backing `speed_bps` /
`eta_seconds`) is allocated lazily on the first `note_progress` of a real
transfer — a resting or never-transferred row carries none. `note_progress`
re-anchors the measurement when a sample goes backwards (restart) or arrives
after a gap longer than four rate windows (pause/resume or a resumed upload
whose first sample jumps to the resumption offset): the fresh sample alone
yields no speed until a second one exists, so a resumed transfer never shows a
burst nor folds its idle time into the window.

| Field | Notes |
| ----- | ----- |
| `filepath` / `direction` | path + `"↓"`/`"↑"` |
| `size` / `bytes_transferred` | progress inputs |
| `holders` / `devices` | device coverage of the last serving pass: how many live devices hold the identity out of how many were compared (`-1` = unknown, e.g. a requester-side preview); drives the `Synced · 2/3` suffix and the detail-pane Devices row |
| `start_time` | for ETA |
| `status` | a `TransferStatus` |
| `mtime` | last-modified time for the detail pane |
| `last_synced_at` | wall clock of the last SYNCED verdict (0 = none this session); feeds the detail-pane Last synced row |

Derived: `filename` (`hsync_desktop/file_panel/models.py::FileTransfer.filename`), `path` (`hsync_desktop/file_panel/models.py::FileTransfer.path`),
`remaining` (`hsync_desktop/file_panel/models.py::FileTransfer.remaining`), `eta_seconds`
(`hsync_desktop/file_panel/models.py::FileTransfer.eta_seconds`, computed from the elapsed rate only while `DOWNLOADING`/`UPLOADING`).

### ImportPhase / CopyProgress (`hsync_desktop/file_panel/import_ops.py::ImportPhase` / `hsync_desktop/file_panel/import_ops.py::CopyProgress`)

What the drag & drop import is doing, reported by
`hsync_desktop/file_panel/workers.py::ImportWorker` and rendered by
`hsync_desktop/file_panel/overlay.py::LoadingOverlay`. `ImportPhase` is the state of the item in
flight (`scan`, `copy`, `move`); `CopyProgress` carries the batch position
(`items_done`/`items_total`), the cumulative counters (`files_done`/`bytes_done`)
and the totals of the current item (`files_total`/`bytes_total`). Those two totals
are `None` while unknown — the item is still being counted, or the bounded count
gave up — which is what keeps the bar indeterminate instead of showing a
percentage that cannot be kept. `ImportItem` (`hsync_desktop/file_panel/import_ops.py::ImportItem`)
is the resolved plan: one source copied or moved to an absolute destination.

### PreviewStats / PreviewItem (`hsync_desktop/preview_summary_dialog.py::PreviewStats`)

The plan one comparison produced, as the confirmation renders it: counters and
sizes per action (`to_download`/`to_upload`/`to_delete`/`to_rename`/`synced`,
`download_size`/`upload_size`/`delete_size`), the two engine-reported facts
(`skipped_deletes`/`skipped_delete_size`, `guard_deletes`/`guard_local`) and the
bounded detail rows (`deletes`, `renames`, `largest` of `PreviewItem`, capped by
`DETAIL_CAP`/`LARGEST_CAP`). `record_*` are the only writers, `reset` clears the
comparison and `has_work`/`action_count`/`transfer_size` are the derived values
the dialog and `_show_preview_summary` share.

### TransferStatus (`hsync_desktop/file_panel/models.py::TransferStatus`)

Enum of row states: `LOCAL`, `SYNCED`, `TO_DOWNLOAD`/`TO_UPLOAD`/`TO_DELETE`/
`TO_RENAME`, `DOWNLOADING`/`UPLOADING`, `DELETED`, `COMPLETED`, `ERROR`, plus
`QUEUED`/`TRANSFERRING`. Render maps: `STATUS_COLORS` (`hsync_desktop/file_panel/models.py::STATUS_COLORS`),
`_NO_PROGRESS_STATUSES` (`hsync_desktop/file_panel/models.py::_NO_PROGRESS_STATUSES`).

### TransferStats (`hsync_desktop/engine/process.py::TransferStats`)

Per-session counters accumulated by the engine; `reset` (`hsync_desktop/engine/process.py::TransferStats.reset`)
clears them and the path sets. `files_sent` / `files_received` are the size of
`sent_paths` / `received_paths`, the distinct bucket-relative paths moved this
session (a repeated transfer stays one; `record_content` adds a path,
`follow_rename` moves identity on a rename — including `src/` descendants for a
directory — and a rename of an untracked path is a no-op). `bytes_sent` /
`bytes_received` sum every content transfer, repeats included. Keys come from
`hsync_desktop/engine/process.py::HsyncEngine._relative_key` against `HsyncEngine.local_root`.

## Persisted configuration

Not a model — `QSettings` keyed by `config.py` `DEFAULT_*` constants. Secrets are
stored Fernet-encrypted (`crypto.py`, `_ENC_PREFIX` marker). See
[settings.md](modules/settings.md) for keys, encryption, and the
config→CLI-args mapping.

## Setup wizard models

| Type | Location | Role |
| ---- | -------- | ---- |
| `WizardMode` | `hsync_desktop/wizard/model.py::WizardMode` | StrEnum of the four use cases |
| `WizardProfile` | `hsync_desktop/wizard/model.py::WizardProfile` | derived defaults per mode |
| `WizardDraft` | `hsync_desktop/wizard/model.py::WizardDraft` | editable wizard state (secrets in clear in memory, encrypted at rest) |
| `Issue` | `hsync_desktop/wizard/validation.py::Issue` | `(level, code, field)` validation issue |
| `ProbeOutcome` | `hsync_desktop/engine/async_probe.py::ProbeOutcome` | async probe result (wizard, Settings probes, trust pre-flight) |
| `ServerProbeResult` | `hsync_desktop/engine/probes.py::ServerProbeResult` | HTTP probe result (status/latency/auth) |
| `_TrustCheck` | `hsync_desktop/main_window/trust.py::_TrustCheck` | one unpinned `host:port` the trust pre-flight must authenticate |
| `FolderCheck` | `hsync_desktop/settings/validators.py::FolderCheck` | sync-folder validation outcome |
| `ApplyResult` | `hsync_desktop/wizard/apply.py::ApplyResult` | trust-pin result (`""`/`no_binary`/`failed`) |

The draft is persisted under `wizard/*`; see [wizard.md](modules/wizard.md).
