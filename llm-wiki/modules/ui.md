# HSYNC Desktop — UI (window, panels, presentation)

Qt widgets that render engine state. All UI mutation stays on the main thread,
driven by `HsyncEngine` signals (see [engine.md](engine.md)).

## main_window/ — MainWindow

`MainWindow` is assembled from responsibility mixins (all sharing `self`):
`window.py` (`MainWindow`, `__init__`, `_connect_signals`), `ui.py`
(UI construction), `events.py` (engine-signal slots), `trust.py`
(trust/pinning + pre-flight), `start.py` (start/stop/compare/pre-flight checks),
`actions.py` (menu actions) and `lifecycle.py` (tray/quit/close/eventFilter).
The mixins suppress `attr-defined` in mypy because they operate on the composed
window's attributes.

| Symbol | Location | Role |
| ------ | -------- | ---- |
| `MainWindow` | `hsync_desktop/main_window/window.py::MainWindow` | top-level window; owns engine + tray; single open `SettingsDialog` (`_settings_dialog`, re-raised on re-open) |
| `_load_ui` | `hsync_desktop/main_window/ui.py::UiBuildMixin._load_ui` | build/compose the central UI |
| `_create_menu_bar` | `hsync_desktop/main_window/ui.py::UiBuildMixin._create_menu_bar` | menus + actions (start/stop/compare/direction/file ops/help) |
| `_connect_signals` | `hsync_desktop/main_window/window.py::MainWindow._connect_signals` | bind every engine `Signal` to a slot |
| `_apply_translations` | `hsync_desktop/main_window/ui.py::UiBuildMixin._apply_translations` | re-translate on language change |
| `_update_peers_label_title` | `hsync_desktop/main_window/ui.py::UiBuildMixin._update_peers_label_title` | status-bar presence title: **Devices** in p2p, **Connected users** in Server Mode |
| `_update_menu_state` | `hsync_desktop/main_window/ui.py::UiBuildMixin._update_menu_state` | enable/disable actions by run state; a stop in flight (`_stop_requested`) keeps Start/Stop disabled, and the comparison action (menu, action-bar button, tray) comes from `StartMixin._can_preview_changes`, which does not depend on the run state |
| `_on_preview_changes` / `_begin_start` | `hsync_desktop/main_window/start.py::StartMixin._on_preview_changes` / `hsync_desktop/main_window/start.py::StartMixin._begin_start` | the single comparison entry point: stopped → `_begin_start(preview=True)` (Start's gates and dry-run), running → `StartMixin._compare_running_engine`; `_begin_start` records `_preview_intent` (`"start"` \| `"preview"`) so the two entry points cannot drift |
| `_enter_preparing_plan_ui` / `_exit_preparing_plan_ui` | `hsync_desktop/main_window/start.py::StartMixin._enter_preparing_plan_ui` / `hsync_desktop/main_window/start.py::StartMixin._exit_preparing_plan_ui` | the **Preparing the plan…** state: progress toast + log marker, ended by the plan, a failed comparison, a stop or a teardown |
| `_apply_plan_without_dialog` | `hsync_desktop/main_window/actions.py::ActionsMixin._apply_plan_without_dialog` | applies a plan the dialog did not confirm: one with no deletions is applied, a deletable one stops with `_report_plan_needs_confirmation` (the caller routes a deletable plan here only for an unattended run) |
| `_report_plan_needs_confirmation` | `hsync_desktop/main_window/start.py::StartMixin._report_plan_needs_confirmation` | warns (log + notification) that an automatic plan with deletions waits for a manual Preview/Start |
| `_stop_preview_run` | `hsync_desktop/main_window/actions.py::ActionsMixin._stop_preview_run` | Close/Cancel of a dry-run plan: `stop_and_wait` + the stopped UI, never a `SYNC` |
| `_on_stop` / `_confirm_stop_running` / `_enter_stopping_ui` | `hsync_desktop/main_window/start.py::StartMixin._on_stop` / `hsync_desktop/main_window/start.py::StartMixin._confirm_stop_running` / `hsync_desktop/main_window/start.py::StartMixin._enter_stopping_ui` | user Stop: a confirmation while the engine runs (declining changes nothing, `hsync_desktop/widgets/dialogs.py::confirm`), then the non-blocking `HsyncEngine.request_stop` plus the immediate `Stopping…` state (badge, disabled actions, progress toast, log marker). Every caller (button, menu, tray) funnels here |
| `_on_stop_timeout` | `hsync_desktop/main_window/start.py::StartMixin._on_stop_timeout` | `HsyncEngine.stop_timeout`: leave `Stopping…`, restore the stopped UI and warn (`notif.stop_timeout`) |
| `_fit_table_width` | `hsync_desktop/main_window/window.py::MainWindow._fit_table_width` | one-shot startup growth so the file table stays readable (see *Columns*) |
| `_check_auto_sync` | `hsync_desktop/main_window/start.py::StartMixin._check_auto_sync` | queued at startup only when `hsync_desktop/settings/cli_args.py::is_auto_sync_enabled` (`sync/auto_sync`) is on |
| `_on_auto_start` | `hsync_desktop/main_window/start.py::StartMixin._on_auto_start` | runs `_on_start` with `_start_is_automatic` set, so failures and prompts avoid modals on a tray-only window |
| `_quit` | `hsync_desktop/main_window/lifecycle.py::LifecycleMixin._quit` | tray "Quit": confirm while a sync runs, then `_shutdown` |
| `_shutdown` | `hsync_desktop/main_window/lifecycle.py::LifecycleMixin._shutdown` | prompt-free close (stop engine, save geometry, hide tray, quit); shared by the SIGINT handler |

Engine→slot wiring (in `_connect_signals`, `hsync_desktop/main_window/window.py::MainWindow._connect_signals`): `log_received→_append_log`,
`event_error→_on_engine_event_error` (`hsync_desktop/main_window/ui.py::UiBuildMixin._on_engine_event_error`, which logs it as the desktop's own `[EVENT ERROR]` line),
`status_changed→_on_status`, `peers_changed`/`master_changed`, `file_transferred→_on_file_transferred`,
`transfer_failed→_on_transfer_failed`, `warning_cleared→_on_engine_warning_cleared`,
`sync_paused→_on_sync_paused`,
`file_progress`/`file_renamed`, `folder_size_changed→_on_folder_size`,
`file_panel.share_size_changed→_on_share_size_changed`,
`pairing_needed→_on_pairing_needed` / `fingerprint_changed→_on_fingerprint_changed`,
and the two comparison marker pairs (`preview_started`/`preview_ended`,
`status_pass_started`/`status_pass_ended`) → `_on_preview_started` /
`_on_status_pass_started` and `_on_preview_ended` / `_on_status_pass_ended`.
`error_occurred` is always routed to `_on_engine_error` (`hsync_desktop/main_window/ui.py::UiBuildMixin._on_engine_error`),
which stores the message, mirrors it into the log panel and raises an in-app
error toast through `_notify_error` (an OS notification is sent too, only when a
notifier exists and the window is out of focus). Its non-fatal counterpart is
`warning_occurred → _on_engine_warning` (`hsync_desktop/main_window/ui.py::UiBuildMixin._on_engine_warning`):
the same pipeline (log panel + banner + OS notification when unfocused) with
`kind="warning"` and the dedicated `warnings` notification category, never the
error path — the run continues. The signal's fourth argument carries the
machine-readable detail the engine emitted (`reason`, plus `needed`/`limit` when
it measured a bounded resource); `hsync_desktop/warnings.py::remedy_text` turns
the actionable causes into localized advice and it is appended to the message, so
the banner and the notification both say what to change. A persistent warning
also exposes the guide link inside the toast (`hsync_desktop/docs_links.py::TROUBLESHOOTING`,
`notif.open_guide`): a system notification is not clickable, so the remedy has to
stay visible in the window. The event's `reason="transient"` instead selects
the `notice` kind: same warning tone, auto-hidden, never a system
notification and never a remedy, because a self-healing condition (dropped
events, an unreadable file recovered by the next scan) is not actionable. The
client already deduplicates that stream per `(source, message)` window, and a
warning arriving after an operator stop is logged but not notified. A
*persistent* warning is a state: it is recorded in the problems registry (see
*Problems badge*) and the client retracts it with `warning_cleared` when the

**"In front" means the app owns the focused window, dialogs included.** The
notification policy (`hsync_desktop/notifications.py::NotificationManager.notify`)
suppresses the OS notification while the app is in front, because the in-app
toast already carries the message; `hsync_desktop/foreground.py::app_in_foreground`
is the single definition, shared with
`hsync_desktop/main_window/actions.py::ActionsMixin._is_window_foreground` (which
decides dialog vs notification for an important result). A modal dialog holds the
focus while it is open, so testing only `window.isActiveWindow()` made the app
look backgrounded and pushed a duplicate notification for something already on
screen; the check walks the `QObject` parent chain instead of
`isAncestorOf` (which reports `False` for a top-level dialog), and a minimised
window is never "in front".

Clicking a notification brings the app forward: `QSystemTrayIcon.messageClicked`
is forwarded as `hsync_desktop/system_tray.py::SystemTray.notification_clicked`
and handled by `hsync_desktop/main_window/lifecycle.py::LifecycleMixin._on_notification_clicked`,
which restores a minimised window, shows a hidden one and raises/activates it.
The same `_bring_to_front` backs the tray Show/Hide entry, so both entries behave
identically. Notification-click reporting depends on the platform: Windows
balloons and macOS notification centre forward it, while some Linux
notification daemons handle the click themselves and never tell the app.
condition heals, so no surface ever reports a problem that is gone.

### Problems badge

`hsync_desktop/problems.py::ProblemRegistry` holds the conditions that still hold, and
`hsync_desktop/main_window/ui.py::UiBuildMixin._refresh_problems_badge` renders them on the
status-bar `QToolButton` (`ui/main_window.ui::problemsBadge`): hidden while the
registry is empty, otherwise a count coloured by the worst kind, a tooltip that
names every entry and a menu whose actions select the log line that reported one
(`UiBuildMixin._reveal_log_line`), plus `problems.dismiss_all`
(`UiBuildMixin._dismiss_problems`). It is wired to the registry's `changed`
signal, so every record/resolve repaints it, and `_apply_translations` re-renders
it on a language change.

A problem is keyed by identity, so a repeat updates the entry instead of stacking
it: a failure by bucket-relative path, a warning by the subsystem that reported
it (`source`). Each one carries its own lifetime —
`EventsMixin._on_transfer_failed` records a failure and `_on_file_transferred`
resolves it for the same path, `EventsMixin._on_sync_completed` drops them all
when the engine's `failed` counter is zero (the authoritative end-of-cycle
verdict), `_on_sync_paused` records the deletion guard for the cycle that
tripped it, `_on_no_master_warning` records the missing primary,
`_on_master_conflict` records a prefer-master contest (retracted on the
`takeover` that settles it), `_on_duplicate_identity` records a cloned device
identity (nothing heals it but the user, so it stays until the run ends), and
`UiBuildMixin._on_engine_warning`/`_on_engine_warning_cleared` record and retract
a subsystem condition. A run boundary
(`ActionsMixin._prepare_engine_run`, `EventsMixin._on_process_finished`) clears
the registry: the state described that run.

An entry renders in two places: the menu label is the identity
(`UiBuildMixin._problem_label`: the path plus the error for a failure, the
condition for a warning) and the tooltip adds the detail
(`UiBuildMixin._problem_line`), which is where the localized remedy
(`hsync_desktop/warnings.py::remedy_text`) fits without turning the menu into paragraphs. A
problem carrying a `help_url` also puts `problems.open_guide` in the menu
(`hsync_desktop/docs_links.py::open_docs_link`), so the advice outlives the toast.

Every toast auto-hides (`UiBuildMixin._show_info_banner`: 20 s for
`error`/`warning`, 15 s otherwise), because a toast is a notification and the
state lives in the badge; `_clear_run_toast` keeps the finished run's outcome on
screen until its own timer and clears it when a new run starts. The per-file
failure notification to the OS is sent once per burst (`_on_transfer_failed`
checks the registry was empty), not once per file.
File-action menu slots: open/open-with/copy-to/rename/trash/
properties (`hsync_desktop/main_window/ui.py::UiBuildMixin._create_menu_bar`).

**Startup run** (`sync/auto_sync`, the Sync-tab *Auto-sync on startup* switch) is
opt-in: the wizard draft starts from `hsync_desktop/config.py::DEFAULT_AUTO_SYNC`
(`hsync_desktop/wizard/model.py::WizardDraft.auto_sync`) and Settings writes the same key, so
`MainWindow.__init__` queues `_check_auto_sync` only when
`hsync_desktop/settings/cli_args.py::is_auto_sync_enabled` is true. The automatic run follows
the manual path (disclaimer → pre-flight gates), except for the file-deletion
confirmation: `hsync_desktop/main_window/start.py::StartMixin._check_deletion_risk` is called
with `interactive=False`, which reports the risk instead of prompting, and
`hsync_desktop/main_window/start.py::StartMixin._report_deletion_risk_needed` surfaces
`notif.deletion_risk_manual` through `_notify_warning` (in-app toast + OS
notification when out of focus) and drops the run. A confirmation nobody was
asked to answer therefore never starts a destructive sync — and a tray-only
`--minimized` launch never raises a modal on a hidden window. The one exception
is an explicit acknowledgement: `deletion_risk.is_acknowledged` (key
`ui/deletion_risk_ack`) covers one folder and one posture, and a covered
configuration lets the automatic run through to the dry-run preview — which
cannot delete anything — while `ActionsMixin._apply_plan_without_dialog` still refuses
to apply a plan that deletes. The same rule
applies to the one-time disclaimer: `hsync_desktop/main_window/start.py::StartMixin._show_disclaimer`
takes `interactive=False`, returns without a dialog and
`StartMixin._report_disclaimer_needed` surfaces `notif.disclaimer_manual`. The
user reviews the settings and presses Start, which prompts interactively as
before.
The confirmation *after* the run is covered by the same rule:
`ActionsMixin._apply_plan_without_dialog` never opens the dialog and stops with
`notif.plan_needs_confirmation` when the plan it computed deletes files (see
*Preview changes — intent, preparing state, automatic runs*).
`_on_auto_start` hands the origin over as `MainWindow._pending_start_automatic`
instead of setting `_start_is_automatic` for the duration of the call, because
`_on_start` defers the run by half a second: the flag has to be live when the
deferred continuation and a startup failure are handled, and a manual Start
clears it again.

The presence value (`peersLabel`, set by `_on_peers`) is `connected/total`. p2p
counts **devices** (self + peers); Server Mode counts **share accounts** with a
live WebSocket (admins excluded), so its title is "Connected users"
(`label.users`) — two devices on the same account count once.

**Keyboard shortcuts** live only on the menu-bar actions (a context menu cannot
be reached from the keyboard, so it never displays them): `Return`/`Ctrl+O` open,
`F2` rename, `Delete` trash, `Alt+Return` properties, `Ctrl+Shift+C` copy path,
`Ctrl+Alt+C` copy to, `F5` compare, `Ctrl+Shift+S` start, `Ctrl+Shift+P` preview
changes, `QKeySequence.StandardKey.Preferences` settings and `.Quit` quit (Cmd
instead of Ctrl on macOS), `F1` documentation; the log menu shows
`StandardKey.SelectAll` / `.Copy` and lets the view handle them.

Help menu (`hsync_desktop/main_window/ui.py::UiBuildMixin._create_menu_bar`): external links
first (Documentation, Project on GitHub), then a separator and the local
app-info dialogs — **License** (`hsync_desktop/main_window/actions.py::ActionsMixin._show_license`
→ `hsync_desktop/license_dialog.py::LicenseDialog`, a scrollable read-only view of the bundled
`LICENSE`) and **About** last, the conventional position. The two external
targets come from `docs_links.py` (`DOCS_INDEX`, `GITHUB_REPO`) and open through
`docs_links.open_docs_link`, which only allows the project HTTPS pages.
`DOCS_INDEX` is the documentation landing page (`docs/README.md`), distinct from
`CONNECTION_MODES` (`docs/choose-connection.md`) that the wizard's mode step links to, so
**Help → Documentation** always starts from the docs index.

**Contextual documentation links**: the Server tab links to the hsync-server
guide (`help.server_setup`), the p2p "Finding devices" group to the hsync-rendezvous
guide (`help.rendezvous_setup`), and the wizard's mode step plus its "Not sure?"
dialog to the desktop choose-connection guide (`help.connection_modes`). The two
Settings links are labelled **"Configuration guide"** (each sits in the section it
documents, so the target is not repeated in the label); the wizard link keeps its
mode-specific label. They are
`QLabel#helpLink` anchors built by `hsync_desktop/widgets/links.py::help_link`, keyboard
accessible (`LinksAccessibleByKeyboard`), with the URL in the tooltip; the
Settings dialog re-applies the translated text in
`hsync_desktop/settings/tab_translations.py::apply_translations`. The toast's guide link is the
same widget retargeted at runtime (`hsync_desktop/widgets/links.py::set_help_link_url`): a
persistent engine warning points it at `hsync_desktop/docs_links.py::WATCHER_LIMITS` (the client
guide's file-watcher/inotify section, where the copy-paste host commands are) when
`hsync_desktop/warnings.py::remedy_text` produced a remedy, otherwise at
`hsync_desktop/docs_links.py::TROUBLESHOOTING` (the desktop symptom guide, which links the client
section for the watcher case). Both targets share the `notif.open_guide` label.
Link colours are themed
through `QPalette.Link`/`LinkVisited` in `themes.py`. The labels are
`hsync_desktop/widgets/links.py::_HelpLinkLabel`, whose `sizeHint` reports the wrapped height
at the width the label really has: a word-wrapped rich-text `QLabel` otherwise
claims the height of its document's ideal (very narrow) width — three lines for
one line of text — and the form row keeps that dead space.

### Startup disclaimer

`hsync_desktop/main_window/start.py::StartMixin._show_disclaimer` gates the first start of a
sync. `hsync_desktop/main_window/start.py::StartMixin._build_disclaimer_dialog` offers two
explicit actions with the app icons: **I understand**
(`disclaimer.acknowledge`, default) and **Not now** (`disclaimer.not_now`,
escape button). Closing the window or pressing Esc defers and never
acknowledges, so only the acknowledge button starts the sync. The "don't show
again" checkbox stores `ui/disclaimer_version` =
`hsync_desktop/main_window/start.py::DISCLAIMER_VERSION`; the previous bare boolean
(`ui/disclaimer_accepted`) counts as version 1 through
`hsync_desktop/main_window/start.py::_accepted_disclaimer_version`, so a later wording change
prompts again.

### Pre-flight gates

Before a run starts, `_continue_start_after_disclaimer`
(`hsync_desktop/main_window/start.py::StartMixin._continue_start_after_disclaimer`) chains the
gates in this order: `_check_deletion_risk`, `_check_keyless_p2p`,
`_check_disk_space`, then `_ensure_trust` (`hsync_desktop/main_window/trust.py::TrustMixin._ensure_trust`);
the scoped
Send/Receive path (`main_window/actions.py`) reuses the same checks. The
deletion-risk confirmation (`notif.deletion_risk`) guards the only posture that
can remove a local file, **Receive only** (`sync/direction` = `download-only`;
the client's `_check_deletion_risk` applies the same rule, and a bidirectional
run uploads the local-only files instead), so `_check_deletion_risk`
(`hsync_desktop/main_window/start.py::StartMixin._check_deletion_risk`) returns early for every
other direction and when **Simulation Mode** (`sync/dry_run`) is on or when the
deletion policy is `keep` (`hsync_desktop/settings/cli_args.py::get_deletion_policy`): none of
them can remove a local file, and an automatic startup run must not be dropped
for a risk that cannot materialise. `deletion_risk.folder_has_user_content`
skips the entries the engine ignores (`is_hidden_file` / `is_hidden_dir` /
`.hsynckeep`, the same walk as the client), and `deletion_risk.is_acknowledged`
ends the gate for a folder and posture the user confirmed with the dialog's
checkbox (value
`<DELETION_RISK_NOTICE_VERSION>|download-only|<sha256(folder+posture)[:16]>`).
`SettingsDialog._on_reset_deletion_risk`, under *Advanced → Deletion protection*,
removes the key. Simulation Mode makes
every run a preview-only one-shot: `build_hsync_args` emits `--once -n`, so the
client shows the preview and exits instead of parking in the dry-run "wait for a
`SYNC` command" state, where `SYNC` would flip it to a real sync
(`hsync-client` `preview.py`, function `_run_stdin_wait`). For the same reason
`_show_preview_summary` (`main_window/actions.py`) never sends `SYNC` under
simulation: it logs and toasts `preview.simulation_no_changes` and lets the
one-shot process finish.

### Simulation Mode indicator

While `sync/dry_run` is on the window says so everywhere, because the mode is a
setting the user would otherwise have to remember. `_refresh_simulation_state`
(`hsync_desktop/main_window/ui.py::UiBuildMixin._refresh_simulation_state`) is the single refresh point, called from `_apply_translations`
(so a language change re-reads it), from `MainWindow.__init__` and from
`_apply_settings_changes` (`hsync_desktop/main_window/start.py::StartMixin._apply_settings_changes`, the shared post-settings/wizard
hook). It drives:
* `QLabel#simulationBadge` in the bottom bar (`ui/main_window.ui`, `simulation.badge`,
  themed by `QLabel#simulationBadge` in `themes.py`), with the `simulation.tip` tooltip;
* the window title suffix (`simulation.window_title_suffix`) via
  `hsync_desktop/main_window/ui.py::UiBuildMixin._update_window_title`, also used by
  `_on_bucket_detected`;
* the tray tooltip note (`hsync_desktop/system_tray.py::SystemTray.set_simulation`) and the Start
  button hint (`tip.start_simulation`).

The run itself opens with a boundary marker (`_mark_new_run`,
`hsync_desktop/main_window/ui.py::UiBuildMixin._mark_new_run`, called by `_prepare_engine_run`
in `main_window/actions.py`): `simulation.log_start` in Simulation Mode,
`sync.log_start` otherwise. The marker is appended without wiping the panel,
which keeps the previous runs. The preview dialog swaps *Synchronize* for *Close*
(`hsync_desktop/preview_summary_dialog.py::PreviewSummaryDialog`, `simulation=True`), so no
control ever promises an application that cannot happen.

### Preview confirmation — `hsync_desktop/preview_summary_dialog.py::PreviewSummaryDialog`

The dialog is the point where a plan is accepted, so it states the outcome first
and the destructive part in the open:

* **Title**: `preview_summary.title_plan` for a `"start"` intent, and
  `preview_summary.title` for `"preview"` or Simulation Mode — the window title
  must not call a plan that a real sync is waiting on a preview.
* **Summary line** (`lblSummary`): `summary_changes` ("Changes: N") plus the
  transfer volume, from `PreviewStats.action_count` / `transfer_size`.
* **Context line** (`lblContext`, hidden when empty): the scoped path for a
  Send/Receive (`context_scope`), the direction when it is not bidirectional
  (`hsync_desktop/settings/cli_args.py::get_sync_direction` + the existing
  `menu.sync.direction.*` labels), the Simulation notice, and
  `skipped_deletions` when the policy dropped planned deletions.
* **Warning line** (`lblWarning`, hidden when empty, red with a ``glyph`` for a
  non-colour cue): `warning_guard` when the client reported a plan the
  mass-deletion guard will pause, otherwise `warning_delete` for any planned
  deletion.
* **Details** (`treeDetails`, hidden when the plan is empty): one group per
  non-empty category, destructive first (Deletions, Renames, Downloads,
  Uploads). Rows are paths with their size, renames as `src → dst`, transfers
  largest-first from `PreviewStats.largest`; `more_items` reports what the bounded
  lists do not name (`DETAIL_CAP` deletions/renames, `LARGEST_CAP` transfers).
  Counts and totals are always exact.
* **Estimate**: `estimate` ("≈ {time} at {rate}/s") is computed per direction
  from `hsync_desktop/settings/cli_args.py::get_bandwidth_limits`; with no limit there is no
  number, and the value is approximate by construction (delta transfer can move
  fewer bytes than the plan's sizes).
* **Footnote** (`lblFootnote`): `preview_summary.synced` when some files are
  already aligned.
* **Buttons**: *Cancel* is the default of a real run (applying a plan is never
  the default), *Synchronize* accepts, Simulation Mode keeps *Close* only and a
  plan with no work shows *OK*. With `intent="preview"` (the **Preview changes**
  action) the pair becomes *Close* (default) + *Sync now*: the run exists to show
  the plan, so applying it is the explicit second click.

### Preview changes — intent, preparing state, automatic runs

`_preview_intent` (set by `StartMixin._begin_start`, `main_window/window.py`) is
the only difference between *Start* and *Preview changes*: both run the same
gates (`_show_disclaimer`, `_check_deletion_risk`, `_check_keyless_p2p`,
`_check_disk_space`, `_ensure_trust`) and the same dry-run
(`StartMixin._start_preview_run`), and the apply mechanism stays one `SYNC` on the
already-running process (`ActionsMixin._show_preview_summary`).

| Case | `"start"` | `"preview"` |
| ---- | --------- | ----------- |
| empty plan | sends `SYNC` (keeps the dry-run phase armed) | `_stop_preview_run`, reports `preview.no_actions`, never `SYNC` |
| plan accepted | `HsyncEngine.sync()` | `HsyncEngine.sync()` |
| plan declined | `_stop_preview_run` | `_stop_preview_run` |
| Simulation Mode | preview only, never `SYNC` | preview only, never `SYNC` |

The intent is read only while `_is_dry_run_preview` is set, so the `PREVIEW` a
running session answers keeps the sync semantics of the run that started it.

The action lives in the Sync menu, the action bar (the `view-refresh` button) and
the tray: **one** entry, `menu.sync.preview` / `tray.preview_changes`, answering in
both engine states (`StartMixin._on_preview_changes` dispatches on
`HsyncEngine.is_running`). Both menus show its tooltip
(`QMenu.setToolTipsVisible(True)`; Qt hides tooltips in menus by default) and the
menu action owns `F5` plus `Ctrl+Shift+P`, so the plan is reachable from the
keyboard whether the app is stopped or syncing. `UiBuildMixin._update_preview_changes_tooltip`
renders the one sentence the state produces (`tip.preview_changes` while stopped,
`tip.compare_waiting` while running without a link, `sync.state.checking`
during a comparison) and appends `tip.compare_last` when a comparison has
already answered, so a stopped app still shows when the folder was last compared.

`_enter_preparing_plan_ui` covers the interval between the dry-run start and its
plan with a `progress` toast plus `--- notif.preparing_plan ---`; the toast is
kept alive by `EventsMixin._on_status` on `connected` (the previous progress
toast is otherwise hidden there) and removed by `_exit_preparing_plan_ui` from the
plan, a comparison error (`UiBuildMixin._on_engine_error`), a stop
(`_enter_stopping_ui`) and `_reset_ui_stopped`.

An unattended run (`_dry_run_unattended`, set by `_start_preview_run` from
`_start_is_automatic`, see `_on_auto_start`) never shows the dialog:
`ActionsMixin._apply_plan_without_dialog` applies the plan when
`PreviewStats.to_delete == 0` — reported through `_report_result`, so the apply
also reaches the OS while the window is in the tray — and otherwise stops and
calls `_report_plan_needs_confirmation` (category `sync`: a user who muted
connection problems still learns that nothing was applied). The *Sync without
asking* setting (`hsync_desktop/settings/cli_args.py::is_auto_apply_enabled`, `sync/auto_apply`)
extends the same rule to an interactive Start: a plan that deletes nothing is
applied without the dialog, while a deletable plan and an explicit Preview always
open it. The settings-level deletion gate
(`_check_deletion_risk(interactive=False)`) already refused the
destructive configurations, so this branch only covers deletions the plan itself
introduces. `to_delete` already counts the deletions the mass-deletion guard will
pause (the client emits the rows and only adds `preview_warning`), so
`guard_deletes` is not part of the condition.

`_dry_run_unattended` is per-dry-run on purpose: `_retry_after_auth_fix` clears it
after the credential prompt (the user is present again, so the retried plan is
confirmed like a manual one) and re-enters `_enter_preparing_plan_ui`, which the
restarted dry-run needs to avoid a silent wait.

### Engine start failure feedback

`_start_engine` (`hsync_desktop/main_window/start.py::StartMixin._start_engine`) wraps
`HsyncEngine.start`: on failure it records the reason emitted through
`error_occurred` and calls `_report_engine_start_failure`
(`hsync_desktop/main_window/start.py::StartMixin._report_engine_start_failure`), which raises a
critical `QMessageBox` (title `notif.error`, body `notif.engine_start_failed`,
the engine reason as informative text). Both start sites use it —
`_continue_start_after_disclaimer` and `_retry_after_auth_fix` — so a start that
cannot launch (missing/incompatible binary, spawn failure) surfaces the dialog
instead of a silent no-op; the caller resets the UI via `_reset_ui_stopped`.

A fatal exit that happens *after* the engine started (`fatal_exit`) is reported by
`_on_fatal_exit` (`hsync_desktop/main_window/events.py::EventsMixin._on_fatal_exit`) through
`_report_engine_stop_failure`, which reuses the same presentation with the body
`notif.engine_stopped` (exit code included) and skips a run the user stopped, a
scoped Send/Receive, and any failure the client already reported through
`error_occurred`. Both helpers delegate to `_report_engine_failure`, so the modal
vs banner + tray policy stays in one place.

### Remote endpoint icon (`_update_path_display`)

`hsync_desktop/main_window/start.py::StartMixin._update_path_display` picks the remote icon from
`QSettings`: server mode (`p2p/enabled` false) → `network-cloud`; p2p mode →
always `network-p2p` (the rendezvous does not change the icon). The remote label
carries the other side's identity: in p2p the group name — the CLI default
(`hsync_desktop/config.py::DEFAULT_GROUP`) when the setting is unset, the translated
`No group` label (`label.remote_p2p_no_group`) when the user cleared it — the client's
ungrouped partition — and in server mode the hostname, or `label.remote_server` when
none is configured. The role
indicator is p2p-only: `_apply_role_visibility`
(`hsync_desktop/main_window/ui.py::UiBuildMixin._apply_role_visibility`) shows it in p2p mode
once the election has decided the role (`_role_known`) and hides it entirely in
Server Mode and before the election — no placeholder glyph. `_retranslate_role`
renders the primary icon with the theme accent
(`themed_icon("role-master", <Highlight>)`; the SVG uses `currentColor`) and the
secondary icon in the theme text colour; the **Nodo primario/secondario** text
appears only when connected and the role is known
(`hsync_desktop/main_window/events.py::EventsMixin._on_master` + `_on_status`), and the state
resets per engine process (`_prepare_engine_run`).

### Share name next to the folder icon

The active share (bucket) is the user-facing identity, so it labels the local
folder in the action bar — next to the folder icon — as a clickable link
(`hsync_desktop/main_window/start.py::StartMixin._update_path_display`; the name comes from
`hsync_desktop/main_window/start.py::StartMixin._share_display_name`: detected bucket →
`sync/bucket` → folder name). Clicking it opens the local folder
(`hsync_desktop/main_window/start.py::StartMixin._on_path_clicked`); the full local path is the
label's tooltip. That tooltip is **intentionally exempt** from the "Show tooltips"
preference (`appearance/tooltips`), which only governs the settings fields. The
window title stays the bare app name (`hsync_desktop/main_window/events.py::EventsMixin._on_bucket_detected`).
The share name is seeded from `sync/bucket` and updated on the client's `bucket`
event (signal `hsync_desktop/engine/process.py::HsyncEngine.bucket_detected`).

### Trust refusal dialogs (SSH-style, no terminal)

`MainWindow` answers the client's trust refusals with dialogs instead of a
terminal (the client keeps retrying on the mDNS path, so the handlers dedupe):

- `_on_pairing_needed` / `_on_fingerprint_changed` (`hsync_desktop/main_window/trust.py::TrustMixin._on_pairing_needed` / `hsync_desktop/main_window/trust.py::TrustMixin._on_fingerprint_changed`)
  build their box through `_trust_prompt` (`hsync_desktop/main_window/trust.py::TrustMixin._trust_prompt`),
  the single warning-box construction (translated title/body, reject as default,
  returns the clicked button *role*), then
  route by `scope`: `master` → `add_peer_pin`/`remove_peer_pin`; `rendezvous`/`server`
  → the helpers returned by `_host_trust_actions` (`hsync_desktop/main_window/trust.py::TrustMixin._host_trust_actions`) (`add_rendezvous_trust`/
  `remove_rendezvous_trust` or `add_server_trust`/`remove_server_trust`). Dedupe is
  `_trust_prompted` `dict[(scope, identity)] → last fingerprint` (`hsync_desktop/main_window/window.py::MainWindow`) via
  `_should_prompt_trust` (`hsync_desktop/main_window/trust.py::TrustMixin._should_prompt_trust`), cleared on start/stop (`hsync_desktop/main_window/window.py::MainWindow`): a
  repeated refusal for the same fingerprint reuses no dialog, a changed one
  re-prompts. A dismissed or ignored dialog never touches the stored pin (the
  host branch acts only on the explicit Trust/Forget buttons).
- `_maybe_offer_restart` (`hsync_desktop/main_window/trust.py::TrustMixin._maybe_offer_restart`) offers to restart a stopped sync after a
  rendezvous/server pin change (those failures are fatal; mDNS refusals are not).
- `_ensure_trust` (`hsync_desktop/main_window/trust.py::TrustMixin._ensure_trust`) is the start
  pre-flight for both hosts: `_pending_trust_checks` collects the
  `_TrustCheck` (`hsync_desktop/main_window/trust.py::_TrustCheck`) entries that still need an
  operator decision (mode/policy/URL apply and the known-hosts store does not yet
  hold `host:port`), then `_run_next_trust_check` probes them one at a time on
  `hsync_desktop/engine/async_probe.py::AsyncProbe` and `_on_trust_probe_done`
  (`hsync_desktop/main_window/trust.py::TrustMixin._on_trust_probe_done`) confirms and pins.
  The run starts only from the `on_ready` continuation, so a refused host
  abandons it — except for an **unreachable discovery servers**: `_TrustCheck.kind`
  distinguishes the two, and a rendezvous whose fingerprint cannot be read only
  warns (log + the client's own `rendezvous`/`unreachable` banner) and continues on
  the local network (ADR-0045), because that source is optional. The probe never
  runs on the UI thread, and a progress toast (`common.checking`) covers the
  wait. Pins are written to the shared known-hosts stores (no GUI-only
  fingerprint settings).

## trusted_keys.py — TrustedKeysDialog

`TrustedKeysDialog` (`hsync_desktop/trusted_keys.py::TrustedKeysDialog`) lists and edits all three stores via
the `engine` subprocess helpers (never the store files directly): three tabs
(rendezvouss / servers / devices), each a `QTableWidget` + Add/Remove/Refresh. The
`initial_tab` keyword (`rendezvouss` default, or `servers`) selects the opening
tab; the settings dialog passes the tab matching the panel that launched it.
Tabs are filtered by the active mode
(`hsync_desktop/trusted_keys.py::TrustedKeysDialog._apply_mode_tab_visibility`, reading
`p2p/enabled`): p2p shows **Discovery servers** + **Devices** and hides the server
store; Server Mode shows only **Server HSYNC** and hides the p2p stores. When
`initial_tab` is hidden, the dialog falls back to the first visible page. The
server tab is labelled **Server HSYNC** (`trusted_keys.tabs_servers`). The
rendezvous/server tabs share `_HostAddDialog` and `_build_host_tab` (host:port
stores); *Add* supports "read from server" or manual entry. *Read from server*
(`hsync_desktop/trusted_keys.py::_HostAddDialog._read_from_node`) runs the fingerprint probe on
`hsync_desktop/engine/async_probe.py::AsyncProbe` and labels the button `common.checking`
meanwhile. Device *Add* pre-fills
the bucket from `sync/bucket`. The tab/column labels are localized in every
locale (`trusted_keys.tabs_peers` = Devices, `trusted_keys.peer` = Device,
`trusted_keys.fingerprint` = the locale's term for the certificate fingerprint).

The rendezvous/server tabs show host, fingerprint, **source** and **added** date.
The raw client `source` (`cli` / `tofu` / `prompt` / `flag`, from
`hsync-client/hsync_client/known_hosts.py::TRUST_SOURCES`) is humanized by
`hsync_desktop/trusted_keys.py::_source_label` (`trusted_keys.source_cli` …), and the
`first_seen` column is labelled **Added on** (`trusted_keys.first_seen`), not the
SSH jargon "first seen". The devices tab shows device, fingerprint and the
**Added on** date: the client's peer pin store (`hsync-client/hsync_client/pinning.py::PinStore`)
records `{fingerprint, first_seen}` per `(cid, bucket)`, exposed by
`hsync trust peer list --json`.

The devices tab shows
`trusted_keys.capability_missing` when the binary lacks the `trust` subcommand
(`supports_peer_trust`).

## file_panel/ — live transfer view

| Symbol | Location | Role |
| ------ | -------- | ---- |
| `FilePanel` | `hsync_desktop/file_panel/panel.py::FilePanel` | container: table + detail pane + overlay |
| `FileTransferTable` | `hsync_desktop/file_panel/transfer_table.py::FileTransferTable` | `QTableView` showing per-file rows (status/progress/size) |
| `FileTransferModel` | `hsync_desktop/file_panel/transfer_table.py::FileTransferModel` | `QAbstractTableModel` holding the visible rows and rendering each cell on demand |
| `FileDetailPanel` | `hsync_desktop/file_panel/detail_panel.py::FileDetailPanel` | metadata pane for the selected file (path, name, size, modified, status, device coverage, last synced) |
| `ProgressBarDelegate` | `hsync_desktop/file_panel/delegates.py::ProgressBarDelegate` | progress-bar cell rendering |
| `LoadingOverlay` | `hsync_desktop/file_panel/overlay.py::LoadingOverlay` | busy overlay shared by the folder scan and the drag & drop import (the import mode is cancellable) |
| `_confirm_dialog` | `hsync_desktop/file_panel/dialogs.py::_confirm_dialog` | reusable confirm prompt |
| `DirectoryScanWorker` | `hsync_desktop/file_panel/workers.py::DirectoryScanWorker` | off-thread local tree scan |
| `ImportWorker` | `hsync_desktop/file_panel/workers.py::ImportWorker` | off-thread copy/move of the dropped sources, reporting per-item and per-file progress |
| `count_tree` / `copy_tree` | `hsync_desktop/file_panel/import_ops.py::count_tree` / `hsync_desktop/file_panel/import_ops.py::copy_tree` | bounded metadata count and per-file copy behind the import progress |
| `_classify_file` / `format_mtime` | `hsync_desktop/file_panel/utils.py::_classify_file` / `hsync_desktop/file_panel/utils.py::format_mtime` | type/icon + mtime formatting |

The table is a **model/view pair** (`hsync_desktop/file_panel/transfer_table.py::FileTransferModel`
+ `FileTransferTable`): the view computes one `(display_name, transfer,
folder_data)` row per visible folder/file and hands the list to `FileTransferModel.set_rows`;
cells are produced through `QAbstractTableModel.data` roles (Display, Decoration,
Foreground, Font, ToolTip, UserRole for the progress bar), so no per-cell
`QTableWidgetItem` is retained and the rows are virtualized. Column-header sorting
is model-side (`FileTransferModel.sort`): it stays off until the user sorts, and a
refresh re-applies the recorded sort, preserving the user's order across rebuilds.
The sort key is the column's **value, not its display text**
(`hsync_desktop/file_panel/transfer_table.py::FileTransferModel._sort_key`): a formatted string
would sort lexicographically ("9.5MB" > "10.0MB", the localized date string is not
chronological) and the progress column has no display text at all (the bar is
drawn from `UserRole`), so a text sort there was a no-op. Progress, Size, Modified,
ETA and Speed use numeric/epoch keys (a folder's Size key is its item count, what
the cell shows); Name, Type, Status and Direction keep the display string.
`FileTransferTable` keeps the navigation, context-menu, column-visibility/width
and selection logic and exposes `_model` (and `model().display_name(row)`) to
callers that need a row's transfer or display name.

The panel lists exactly what the engine synchronises: the local scan, the
consistency pass and the status-bar size share
`hsync_desktop/file_panel/filter.py::is_synced_entry`, built on the engine's
`hsync_common.ignore.IgnoreMatcher` (so `.hsyncignore`, the built-in default
patterns, internal names and `*.part` artifacts are excluded) plus an explicit
`.hsynckeep` exclusion — the sentinel is synced by the engine but stays internal
to the UI, and the client's folder-size totals exclude it too. `.hsyncignore` is
re-read when its `(mtime_ns, size)` changes (`hsync_desktop/file_panel/filter.py::ignore_file_stamp`).

Dot-prefixed names are only a **view** option: `ui/show_hidden_files`
(`FileTransferTable._SHOW_HIDDEN_SETTINGS_KEY`) hides an item when its own name
at the current level starts with `.`, toggled from the header context menu next
to the column toggles (`FileTransferTable.set_show_hidden`). It changes neither
`_transfers` nor the scanned size; a non-dot folder whose children are all
view-hidden stays listed, with counts from its visible children only. The
default is off (hidden).

Renaming a row (`hsync_desktop/file_panel/transfer_table.py::FileTransferTable.rename_file`)
keeps its modification date: the new row inherits the previous row's mtime when
the filesystem read returns nothing (the rename event may arrive before the local
rename lands — `hsync_desktop/main_window/events.py::EventsMixin._on_file_renamed` reads the
destination, falling back to the source).

`FileTransferTable.set_connected` (`hsync_desktop/file_panel/transfer_table.py::FileTransferTable.set_connected`,
driven from `hsync_desktop/main_window/events.py::EventsMixin._on_status`) greys **Local** rows
(`TransferStatus.LOCAL` → `STATUS_COLORS`) only while a connection is active.
When the link is disconnected/connecting/waiting the rows keep the default text
colour, because "Local" is the resting state rather than a comparison result;
real transfer states keep their own colours.

A folder row with no aggregated children (an empty directory) shows the folder's
own status instead of defaulting to *Local*. Every verdict lands on the
trailing-slash key through
`hsync_desktop/main_window/events.py::EventsMixin._on_directory_status`: a directory the engine
created from a remote event (`_on_directory_created`) and an empty directory the
comparison classified (`dir_status` — its `.hsynckeep` sentinel never becomes a
file row) both resolve there. The status itself is mapped
from the folder's own transfer by `_STATUS_PRIORITY` / `_FOLDER_STATUS_KEYS` in
`file_panel/transfer_table.py`. A folder that does have children still takes the
highest-priority child status.

**Verdicts land at the end of a comparison, not per event.** `preview_started` /
`status_pass_started` open a buffer
(`hsync_desktop/main_window/events.py::EventsMixin._pending_verdicts`); the
per-file, per-directory and per-rename verdicts are collected there (the last
one per path wins) and `_flush_verdicts` applies them once, from
`EventsMixin._end_comparison`. Plan counters are still recorded immediately,
because they populate the summary dialog rather than a row. Two consequences:
a folder row no longer flips `synced` → `to sync` → `synced` (with its Modified
time jumping forward and back) while the classification is still computing, and
the tree is rebuilt once per comparison instead of once per verdict. A directory
verdict stores no timestamp: its mtime is read at flush time, against the settled
tree. A verdict that arrives outside a comparison (a live `dir_status`, a stalled
row refresh) is applied at once, and a process that dies mid-comparison drops its
buffer.

**Busy feedback is delayed and shared.** An indicator appears only after
`hsync_desktop/busy.py::BUSY_DELAY_MS` (2 s), so a fast task never flashes
something; below the threshold nothing is shown at all. Three surfaces use the
same single-cell braille glyph (`SPINNER_FRAMES`) so the layout can never jump:

- **comparison** — the sync-state label swaps its trailing ellipsis for the glyph
  (`busy_text`), driven by `hsync_desktop/main_window/events.py::EventsMixin._render_sync_state`.
  It is keyed on `_comparison_in_flight`, **not** on the `checking` state: that
  state is also the resting "waiting for a file-set answer" (a link that just came
  up, an inventory not published yet), which is not work happening now. For the
  same reason `_end_comparison` re-renders after clearing the flag — a pass that
  classified nothing leaves `checking` and must not keep the glyph spinning;
- **folder scan** — `hsync_desktop/file_panel/overlay.py::LoadingOverlay` reveals
  the overlay (determinate, `current/total`) after the same delay and cancels the
  pending reveal in `hide_loading`; a scan shorter than the threshold shows
  nothing;
- **plan preparation** — the `kind="progress"` toast stays immediate (it
  acknowledges the click) and keeps its indeterminate bar, which already is the
  busy language; no glyph is added there.

The glyph never widens a label (it replaces the ellipsis, or is prefixed when the
text has none), the accessible name stays the plain text so a screen reader is
not read a glyph changing eight times a second, and `start()` is idempotent
because the busy label is re-rendered on every state change.

A **"Synced" row is a claim about the remote copy**, so it is asserted only while a
link exists: `hsync_desktop/file_panel/transfer_table.py::FileTransferModel._row_status` swaps
the label for `detail.synced_stale` (and `_foreground` uses the same muted grey as
*Local*) whenever `FileTransferTable.set_connected(False)` has cleared the link.
The timestamp of the last full comparison (`FileTransferTable.mark_verified`,
stamped from `_on_preview_ended` and `_on_sync_completed`) feeds the tooltip, so
an offline row reads "last checked at HH:MM". It is deliberately *not* turned into
*Local*: that label means the remote side was never compared (a different, and
misleading, statement).

A scoped **Send now** / **Receive now** reloads the local tree before starting
its one-shot (the preview and the confirmed run both call
`_prepare_engine_run`). `FilePanel.load_local_files(..., restore_view=...)`
forwards the folder and row captured before the reload to
`FileTransferTable.restore_view`, so the user stays in the same folder with the
acted-on row selected instead of jumping to the root. The row is applied as a
sticky selection (`_apply_sticky_selection`) across the asynchronous scan's
refreshes and is cleared on user navigation, a new click, or a panel clear
(`hsync_desktop/main_window/actions.py::ActionsMixin._selection_display_name` maps a nested
target to the first path segment below the current folder).

The reload **keeps the per-file classifications**:
`hsync_desktop/file_panel/transfer_table.py::FileTransferTable.clear_transfers` drops every row
and the scan that follows re-emits plain `LOCAL` placeholders
(`TransferStatus.LOCAL` means "exists here, status unknown"), so
`FilePanel.load_local_files` captures
`hsync_desktop/file_panel/transfer_table.py::FileTransferTable.status_snapshot` — copies of the
rows that carry a classification — and hands it to
`FileTransferTable.add_transfers_batch(..., known=...)`, which merges it back:
`status`, device coverage and client attribution survive, while `size`/`mtime`
come from the fresh scan. A classification that lands *while* the scan runs wins
as well (`hsync_desktop/file_panel/transfer_table.py::FileTransferTable._classified_row`
consults the live row first), so the race between the
scan's batches and the engine's per-file events cannot grey a row the engine
already classified. The snapshot is dropped at the end of the rebuild
(`FilePanel._on_scan_finished`) and whenever the folder changes: the keys are
relative paths, so another base starts clean.

The row context menu (`hsync_desktop/file_panel/transfer_table.py::FileTransferTable._show_file_context_menu`)
offers `Open` — a **folder** navigates into it inside the panel (same as a
double-click) while a **file** opens with the system default app — followed by
`Open containing folder` (reveals the entry in the OS file manager:
`FileTransferTable._ctx_open_containing`), then **Send now** / **Receive now** —
one-shot upload-only / download-only of the selected subtree (`signals
FileTransferTable.send_selection_requested` / `receive_selection_requested` →
`hsync_desktop/main_window/actions.py::ActionsMixin._sync_selection`, scoped through
`hsync_desktop/settings/cli_args.py::build_selection_args`) — Open With / Copy To / Rename /
Trash / Properties. Send/Receive first run a scoped dry-run preview whose summary
dialog confirms the actions; on accept the real one-shot starts from
`MainWindow._start_selection_run` (the pending selection is carried by
`MainWindow._pending_selection_sync`, consumed by `MainWindow._show_preview_summary`).
The entries are disabled while a sync is running
(`FileTransferTable.set_sync_active`); the File menu hosts the same two actions
(`hsync_desktop/main_window/actions.py::ActionsMixin._menu_file_send` / `_menu_file_receive`),
enabled only with a selection and a stopped engine.

Destructive acts (`Rename` / `Trash`) add a **per-row** gate on top:
`FileTransferTable._entry_is_busy` returns True while the engine owns the path —
planned (`TO_*`), in-flight (`DOWNLOADING`/`UPLOADING`),
`QUEUED`/`TRANSFERRING` or `DELETED` rows — or, for a folder, while any row
below it is busy (`_subtree_is_busy`, a prefix scan over the flat transfer
map, because a folder's aggregate status can look resting while a child
transfers). `Copy to…` is additionally gated by `_copy_enabled` — the source
must be materialized on disk (an incoming download commits at the end and a
DELETED row is gone) and a folder must not be busy below it (the copy would
sweep the engine's `.part` staging files), while a busy *file* row stays
copyable — so the menu never offers an action that would race the transfer or
fail on a missing file. The same helpers drive the window File menu at selection
time (`_on_file_selection_changed`) and are re-checked
inside `_ctx_rename` / `_ctx_trash` / `_ctx_copy_to`, whose enabled state can
lag a transfer that only just started; Open / Copy path / Properties stay
available because they are read-only. The rename submission is guarded too
(`_apply_rename`, called by `_ctx_rename` after the dialog): a free-form new
name is re-checked against the row map (`_rename_collides_with_engine`) because
the *selected* row may be resting while the typed *destination* is a
planned/in-flight transfer — renaming over it would clobber the file the engine
is writing.

The menu is built by `FileTransferTable._build_file_context_menu` (split from the
`exec` so its order is asserted in tests) and groups the entries by kind: open ▸
send/receive ▸ copy ▸ rename ▸ destructive ▸ properties (last, the conventional
position). The **copy group** holds `Copy to…` (`_ctx_copy_to`, a file copy) and
the two clipboard commands `Copy path` / `Copy relative path`
(`FileTransferTable.copy_path`): the first puts the absolute path, the second the
path inside the shared folder, both through `os.path.normpath` because the wire
keys use `/` and a folder key ends with `/` (a host would otherwise get mixed
separators and a trailing one). The same two commands are in the **File** menu
(`hsync_desktop/main_window/actions.py::ActionsMixin._menu_file_copy_path` /
`_menu_file_copy_path_relative`), which is the keyboard-reachable surface, with
`Ctrl+Shift+C` on the absolute form (the conventional "copy as path" chord) and
no shortcut on the relative one; `Copy to…` moved to `Ctrl+Alt+C` to free it.

The table re-localizes its **column headers** on a live language change
(`hsync_desktop/file_panel/transfer_table.py::FileTransferTable.retranslate`, called through
`hsync_desktop/file_panel/panel.py::FilePanel.retranslate_columns` from
`hsync_desktop/main_window/ui.py::UiBuildMixin._apply_translations`). The same path (and
`refresh_fonts`, the restored layout and `_toggle_column` when a hidden column is
shown again) runs
`hsync_desktop/file_panel/transfer_table.py::FileTransferTable._ensure_readable_headers`: a
section narrower than its own header hint is widened, because the header is
centred and would otherwise clip the label on both sides (the `Estimated time`
column started at the 100 px style default).

**Columns**: the default order is `hsync_desktop/file_panel/utils.py::_COLUMN_KEYS` — Name,
Direction, Size, Type, Modified, Progress, Status, Estimated Time, Speed. The row
icon is a **decoration of the Name cell** (`FileTableModel.data` `DecorationRole`,
no icon column), so identity leads; Direction follows the name because it is the
one column that says what will happen to the row (the transfer-queue convention)
and it stays on screen in a narrow window instead of being the first section
scrolled out. **Type** and **Speed** are optional and start hidden
(`FileTransferTable._DEFAULT_HIDDEN`): the icon already conveys the type and the
live rate (`file.speed`, `speed_bps`) matters only while a transfer runs.
Direction (`file.direction`, the ↑/↓ arrow — ✕ on a deleted row, ⇄ on a rename) is
**empty at rest** (the dash placeholder is noise in a dense column) and its
operative glyphs are **bold**, a second cue beside the status colour. Visibility
is toggled from the header menu (`FileTransferTable._show_header_context_menu`),
which omits **Name** (the primary column carries the row identity); Name is also
pinned as the first section (`QHeaderView.setFirstSectionMovable`), so a reorder
cannot push the identity column inward. The **data columns are user-resizable**
(`Interactive`, floor `_MIN_COLUMN_WIDTH`, which is also the header's
`setMinimumSectionSize`, so Qt enforces it on a drag), **Name** stays `Stretch`
(the flexible column, still sized by the window); a double-click on a section
handle fits that column to its content
(`FileTransferTable._fit_column_to_contents`).

The whole layout — widths, visual order and hidden sections — is one
`QHeaderView` state blob persisted in `ui/file_table_header_state_v2`
(`FileTransferTable._save_header_state` / `_restore_header_state`), written after
the drag settles (`_STATE_SAVE_DELAY_MS` debounce, flushed by
`FileTransferTable.hideEvent`). **Bump the `_vN` suffix whenever the column set
changes** (as `_v2` did when the icon column became a cell decoration):
`restoreState` does not validate the section count and would apply a
stale blob to the wrong sections. Widths are seeded once from the content on the
first populated refresh (`FileTransferTable._size_columns_to_contents`) when
nothing is stored. Stretch-driven resizes are **not** persisted: Name also
resizes when the window grows, which is not a layout the user chose, so a plain
window resize never marks the profile as having a saved layout. The blob stores
the sort indicator too, which `FileTransferTable._restore_sort_indicator` clears
after the restore (the table starts in the natural folders-first order until the
user clicks a header). **Reset columns** (`file.reset_columns`,
`FileTransferTable._reset_columns`) removes the blob, restores the default
order/visibility and re-fits the widths without persisting, so the next launch is
again a first run.

Because **Name** is the stretch column, Qt answers a shortage by shrinking it
down to the minimum section size instead of extending the scroll range, so the
persisted widths in a narrow window leave file names
unusable while the horizontal scrollbar stays empty:
`FileTransferTable.required_viewport_width` therefore reports the width the
visible sections need with `FileTransferTable.name_floor()` reserved for Name —
`_MIN_NAME_WIDTH` normally, or the roomier `_MIN_NAME_FIRST_RUN` while the
profile has never saved a layout (`FileTransferTable.has_saved_layout`,
captured at construction because the header persists its initial section sizes
on the first layout pass) — and the one-shot
startup fit (`hsync_desktop/main_window/window.py::MainWindow._fit_table_width`, re-scheduled
from `MainWindow.showEvent` and the model's `rowsInserted` through
`MainWindow._schedule_table_fit`) grows the window by that deficit, clamped to
`QScreen.availableGeometry`. The default and minimum window size live in
`ui/main_window.ui` (not in code), so the fit only ever grows the window beyond
them. The fit is consumed only after a valid measurement
(rows present, window visible) and never fights a later manual resize
(`MainWindow._table_width_fitted`). `FileTransfer.speed_bps`
(`hsync_desktop/file_panel/models.py::FileTransfer.speed_bps`) also backs the ETA, so the two
stay consistent. A folder keeps the neutral aggregate status (`folder.status.to_sync`)
because it can mix operations; its tooltip spells out the planned actions
(`folder.ops_item`, e.g. "To upload: 3, To download: 1") while files keep the
precise per-action label (`detail.to_upload`, `detail.to_download`, …).

**Live progress**: a received file does not exist on disk before it completes, so
its row cannot come from the scan. `update_transfer_progress`
(`hsync_desktop/file_panel/transfer_table.py::FileTransferTable.update_transfer_progress`)
creates the row on the first `progress` event (direction taken from the event's
`op`, `size` from the event's total) and the completion handler writes the final
size (`hsync_desktop/file_panel/models.py::FileTransfer`), so a receive shows its percentage
and rate while it happens and its real size afterwards. The same events arrive
when this app is the device the others sync from (the p2p master): the client
reports the files it serves (`op=upload`) and the pushes it receives
(`op=download`), so the panel shows activity in both roles — the contract lives
in the client wiki (`hsync-client/llm-wiki/modules/sync-core.md`). A transfer
that gives up is flagged `TransferStatus.ERROR`
(`hsync_desktop/file_panel/transfer_table.py::FileTransferTable.mark_failed`); rows still marked
in flight when the engine stops are reset or dropped
(`hsync_desktop/file_panel/transfer_table.py::FileTransferTable.clear_transient_progress`).
A status refresh must never downgrade a live in-flight row:
`update_file_status` ignores a *planned* status (`TO_*` — the master's
`master_status` re-emits every file on each pass) while the row is
`DOWNLOADING`/`UPLOADING`, and any status at all when the update is a preview.
Letting it through flipped the row to `TO_UPLOAD`, which hid the ETA (it needs an
in-flight status, `FileTransfer.speed_bps`) while the progress bar kept
rendering; only a terminal event ends a live in-flight row. A row whose last
sample is older than `hsync_desktop/file_panel/models.py::IN_FLIGHT_STALE_SECONDS` is stale, not
live: it accepts any status, preview included, so the engine's answer can resolve
it when its terminal event was lost.
The rate is the bytes moved over the last `SPEED_WINDOW_SECONDS` of progress
samples (`hsync_desktop/file_panel/models.py::FileTransfer.note_progress`), not
`bytes / (now - start_time)`: the column follows the real stream, drops back to
the sustained rate within a second and hides the per-chunk pacing of the
limiter. A sample pair closer than `_RATE_MIN_INTERVAL` measures nothing — the
client flushes its closing sample as soon as the wire total is reached, so a
burst absorbed by the transport would otherwise be reported at hundreds of MB/s
with an ETA of zero — and the previous measurement stands. `progress_total` keeps
the wire total (compressed upload size, delta payload) separate from the on-disk
`size`.

An in-flight **upload** never reads as finished:
`hsync_desktop/file_panel/models.py::clamp_upload_progress` caps its percentage at
`_UPLOAD_MAX_PROGRESS` (99), for the row
(`hsync_desktop/file_panel/transfer_table.py::_TableModel._row_progress`) and for the folder
aggregate (`hsync_desktop/file_panel/transfer_table.py::FileTransferTable._aggregate_folder`).
The client counts the bytes handed to the transport, so a burst absorbed by the
socket/relay buffers reaches the wire total long before the receiver commits the
file; the bar closes with the row, on the terminal `transfer` event. A download
is unaffected: its bytes really are on disk. The reverse also holds: a row that
already reached a settled classification (`hsync_desktop/file_panel/transfer_table.py::_SETTLED_STATUSES`
— `SYNCED`, `COMPLETED`, `DELETED`) is **not** restarted by a trailing progress
sample (`FileTransferTable.update_transfer_progress` returns early). The peer
echoes progress asynchronously from the upload commit, so over a relay a tail
sample can arrive after the terminal event; restarting the finished row stranded
it at the upload cap with no further terminal event to close it.

A row the engine stops reporting on never stays in flight forever. The periodic
consistency pass asks for in-flight rows silent longer than
`hsync_desktop/file_panel/models.py::IN_FLIGHT_STALE_SECONDS`
(`hsync_desktop/file_panel/transfer_table.py::FileTransferTable.stale_in_flight_paths`, fed by
`hsync_desktop/file_panel/models.py::FileTransfer.last_progress_at`) and, **once per stall and
again every `hsync_desktop/file_panel/panel.py::_STALL_REASK_SECONDS` while it lasts**, requests
a status refresh
(`hsync_desktop/file_panel/panel.py::FilePanel._request_status_for_stalled_rows` →
`FilePanel.scan_found_new_files`), so the engine's own answer resolves the row —
a lost terminal event or a wedged transfer cannot leave a frozen bar behind. The
same threshold relaxes `update_file_status`, so the preview answer that refresh
triggers is accepted for a stale row (a live row still ignores it). The
re-check matters when the refresh itself fails (a link that is down): the row is
asked again instead of staying in flight forever. A fresh sample (or a resolved
row) clears the record, so the next stall asks again.

Row changes that arrive in bursts are **coalesced**: the preview/status
(`FileTransferTable.update_file_status`), live-progress and scan-batch paths
schedule a single debounced rebuild (`FileTransferTable._schedule_refresh`,
100 ms) instead of rebuilding the whole table per event, and the periodic
consistency pass batches its additions and removals
(`FileTransferTable.add_transfers_batch` / `FileTransferTable.remove_transfers`).
Tests that assert rendered cells right after such a call must flush the debounce
with `FileTransferTable.refresh_view()`.

The consistency pass walks with an iterative `os.scandir` and derives each
relative key by slicing the prefix `hsync_desktop/file_panel/panel.py::_scandir_child_prefix`
builds, matching `os.scandir`'s own `base`/`name` join (a separator is appended
only when the share path does not already end with one, alt separator included).
It recurses only into real directories and, like `os.walk(onerror=None)`, skips a
nested unreadable or vanished directory instead of aborting the whole pass; an
unreadable share root aborts the pass rather than diffing an empty set.

**Clickable links**: the share name, every breadcrumb segment and the
detail-panel file path use the default text colour with
`text-decoration: underline` instead of the palette link colour, so they read as
normal text; the hand cursor and the `linkActivated` handlers still mark them as
clickable. In the breadcrumb a parent segment navigates to its folder, while the
current segment — the folder the list already shows — re-scans it instead of
performing a dead navigation (`hsync_desktop/file_panel/panel.py::FilePanel._on_breadcrumb_clicked`),
so a click never navigates to the folder already displayed; the root icon stays
inert when the list already shows the root.

**Breadcrumb notation**: segments are joined by
`hsync_desktop/file_panel/panel.py::_breadcrumb_separator` — `" / "` (GNOME Files, and every
textual path on macOS) or `" > "` on Windows (Explorer) — and the breadcrumb
never starts with a separator: the root icon is the first segment, so a leading
`/` would read as an absolute path. The navigation buttons and the root icon
render at `hsync_desktop/file_panel/panel.py::_NAV_ICON_PX` (20 px, a downscale of the bundled 24×24
SVGs); the root icon keeps a `hsync_desktop/file_panel/panel.py::_NAV_ICON_BOX_PX` (24 px) click target,
the WCAG 2.2 minimum. `hsync_desktop/file_panel/panel.py::FilePanel._refresh_breadcrumb_icon` is the only
place that re-renders that icon, including after a theme change.

### Drag & drop import

Dropping OS files onto the table (`hsync_desktop/file_panel/transfer_table.py::FileTransferTable.dropEvent`)
emits `files_dropped(sources, target_rel, action)`; the destination is the folder
row under the cursor, else the folder being browsed
(`hsync_desktop/file_panel/import_ops.py::target_rel_dir`). `hsync_desktop/file_panel/panel.py::FilePanel._on_files_dropped`
validates the sources (`hsync_desktop/file_panel/import_ops.py::validate_sources`), confirms a
move, resolves each name conflict (`Replace` / `Keep both` / `Skip`, with
apply-to-all) and hands a list of `hsync_desktop/file_panel/import_ops.py::ImportItem` to
`FilePanel._start_import`, which runs them in `hsync_desktop/file_panel/workers.py::ImportWorker`
and refuses further drops meanwhile (`FileTransferTable.set_drop_enabled`).

**The import is visible while it runs.** `ImportWorker` reports a
`hsync_desktop/file_panel/import_ops.py::CopyProgress` per item and per file
(`hsync_desktop/file_panel/import_ops.py::copy_tree` for a directory, so a dropped folder — a
single item — still moves the bar), and the panel renders it in the shared
`hsync_desktop/file_panel/overlay.py::LoadingOverlay` through `FilePanel._sync_loading_overlay`.
That helper is the single owner of the overlay: the scan and the import both use
it, so visibility is derived from `_importing`/`_overlay_scan_active` instead of
paired show/hide calls — a scan ending mid-import must not hide the import's
indicator, and the import wins when both are active. The bar is **determinate only
when the totals are known**: a directory is counted first with
`hsync_desktop/file_panel/import_ops.py::count_tree`, bounded by
`hsync_desktop/file_panel/import_ops.py::COUNT_BUDGET_S`; an incomplete count (budget spent or
cancelled) reports `files_total`/`bytes_total` as `None` and the overlay stays
indeterminate with its file and byte counters, rather than promising a percentage
it cannot keep. A move stays indeterminate: `shutil.move` is a rename while both
sides share a filesystem, and it reports nothing either way.

The overlay's Cancel button emits `LoadingOverlay.cancel_requested` →
`FilePanel._cancel_import` → `ImportWorker.cancel`, which stops at the next item or
file boundary. An item cut short mid-tree is neither imported nor failed, and
`ImportWorker.finished(imported, failed, errors, cancelled)` reports the batch as
cancelled, so the panel shows `dnd.import_cancelled` instead of a success.

Models for the panel live in `file_panel/models.py` — see
[data-models.md](../data-models.md).

### Scoped Send/Receive outcome

A user-invoked *Send now* / *Receive now* is tracked as a one-shot with its own
lifecycle so its result is surfaced exactly once:

- State: `MainWindow._selection_sync_active`, `_selection_sync_phase`
  (`"preview"` | `"confirm"` | `"run"`) and `_pending_selection_sync`
  (`(subdir, direction)`) — `hsync_desktop/main_window/window.py::MainWindow`.
  `_begin_selection_sync` arms them and shows a persistent progress toast
  (`_show_info_banner(..., auto_hide_ms=0, kind="progress")`); `_finish_selection_sync`
  (`hsync_desktop/main_window/actions.py::ActionsMixin._finish_selection_sync`) clears them and is
  **idempotent**, so a later engine event never re-surfaces the same result.
- Outcome: `hsync_desktop/main_window/events.py::_scoped_outcome` derives it from the counters
  on `sync_complete` (the engine's `SyncCycleResult`): `done` when any of
  `downloaded`/`uploaded`/`deleted`/`renamed` is non-zero, `already_synced` when
  the cycle applied nothing, `failed` on failures. Counting `file_transferred`
  events was wrong for renames and deletes, which move no bytes.
- **A transient "alone so far" never ends a scoped op.** `sync_pending(reason=
  "no_device")` (`EventsMixin._on_sync_pending`) also describes the moment a
  device has just elected itself, before discovery answers, so it finalizes the
  op only when the run is already over (`not engine.is_running`). A running
  scoped run is one-shot (`--once`) and reports its own verdict. Finalizing on
  the transient state produced a fake "no device found", delivered the real
  result down the non-scoped path, and — because `_reset_ui_stopped` disables the
  toolbar while the engine kept running — left Start and Stop both unclickable
  until the app was restarted. `no_peers` (the one-shot abort before exit) still
  finalizes immediately.
- Progress toast: the phase text is `sync.sel_search` (p2p) / `sync.sel_server`
  (server); `_on_peers` (`hsync_desktop/main_window/events.py::EventsMixin._on_peers`) adds the
  other-device count (`sync.sel_peers_fmt`) while the op is active.
- Outcome: `_surface_selection_outcome` (`hsync_desktop/main_window/actions.py::ActionsMixin._surface_selection_outcome`)
  routes an *important* result (no devices, server unreachable, failed) through
  `_important_selection_outcome` — a modal dialog when the window is in the
  foreground, otherwise a warning notification (`_notify_warning`, which also
  raises the in-app warning toast) — and a *non-critical* result through
  `_report_result` (a green `success` toast for a sent/received count, a
  plain `info` toast for *already up to date* / *nothing to do* / an automatic
  plan that was applied, plus an info notification suppressed while the window
  is focused, so exactly one surface shows).
- Wiring (in `_connect_signals`): `error_occurred → _on_engine_error`
  (`hsync_desktop/main_window/ui.py::UiBuildMixin._on_engine_error`, `reason="connection"` in
  server mode → *server unreachable*; a launch failure is skipped and reported by
  `_start_engine`), `no_peers_warning → _on_no_peers`,
  `sync_pending → _on_sync_pending`,
  `sync_completed → _on_sync_completed`, `process_finished → _on_process_finished`
  and `stop_timeout → _on_stop_timeout` finalize. `_on_file_transferred` counts real
  transfers during the `run` phase.
- A lost connection raises the `notif.connection_lost` notification from
  `_on_status` (`hsync_desktop/main_window/events.py::EventsMixin._on_status`) on the first
  non-connected link status (`waiting` in server mode and p2p, `disconnected`
  when the process ends) after a link existed. `_ever_connected`
  (`hsync_desktop/main_window/window.py::MainWindow`) is set on the first `connected` and reset
  per engine process, so a one-shot that never linked does not claim a lost
  connection; `_link_lost_notified` (`hsync_desktop/main_window/window.py::MainWindow`),
  re-armed on every `connected`, keeps one drop from raising the toast twice
  (`waiting` then the terminal `disconnected`). The engine's own `connecting`
  (pre-start, credential retry) is not a link loss and never notifies.
- Stopping is visible at once: `_on_stop` (`hsync_desktop/main_window/start.py::StartMixin._on_stop`)
  marks the run user-stopped and calls `HsyncEngine.request_stop` (non-blocking, so
  the window never freezes), and `_enter_stopping_ui`
  (`hsync_desktop/main_window/start.py::StartMixin._enter_stopping_ui`) sets `_stop_requested`, the
  `Stopping…` badge (`_set_status_label`, `hsync_desktop/main_window/events.py::EventsMixin._set_status_label`),
  disables Start/Stop/Check-changes (tray too, `hsync_desktop/system_tray.py::SystemTray.set_stopping`)
  and shows a `progress` toast plus a log marker. `_on_process_finished`
  (`hsync_desktop/main_window/events.py::EventsMixin._on_process_finished`) clears `_stop_requested`
  and restores the stopped state; if the engine never confirms the exit,
  `stop_timeout → _on_stop_timeout` restores it with the `notif.stop_timeout` warning.

### Transient feedback (overlay toast)

`MainWindow._info_banner` is an **overlay child of `centralWidget()`**, never in
`rootLayout` (`hsync_desktop/main_window/ui.py::UiBuildMixin._create_info_banner`), so
showing/hiding it cannot reflow the splitter. `_show_info_banner(message,
auto_hide_ms, kind, title, help_url)` places it bottom-right above the bottom bar
(`_position_info_banner`, kept anchored on `resizeEvent`) and maps `kind`
(`progress`, `info`, `success`, `warning`, `error`) to a severity colour through a
dynamic `severity` QSS property; `error`/`warning`/`success` also prefix a
severity glyph and the given title, so the severity is recognisable without
relying on colour. `help_url` reveals the `_info_banner_link` affordance — a
`hsync_desktop/widgets/links.py::help_link` retargeted through
`hsync_desktop/widgets/links.py::set_help_link_url`, the only way to offer a click during a
toast, since the banner is an overlay whose text cannot be selected. That link is
built with an explicit `color=#FFFFFF` (`help_link(..., color=...)` → an inline
anchor style plus underline): a rich-text anchor ignores the label's QSS `color`,
so without it the link fell back to the theme's blue, which does not contrast
against the orange/red fills, and the underline keeps it a link without relying on
hue (WCAG 1.4.1). Persistence:
`error`/`warning` stay until dismissed (`✕`) and
survive both the engine process finishing and a new run, `success` survives the
process finishing, `progress`/`info` auto-hide (`_clear_run_toast` with
`_SURVIVES_FINISH`/`_PERSISTENT_ACROSS_RUNS`). Errors and warnings are surfaced
in-app regardless of the notifications preference:

- `_notify_error` (`hsync_desktop/main_window/ui.py::UiBuildMixin._notify_error`) and
  `_notify_warning` (`hsync_desktop/main_window/ui.py::UiBuildMixin._notify_warning`) always show
  the in-app toast and, when the window is out of focus, the OS notification.
- Per-file transfer failures are consolidated into a single error toast at the end
  of a non-scoped run (`_on_transfer_failed` increments `_transfer_failure_count`,
  `_on_process_finished` aggregates).
- `info`/`progress` keep the plain message; the normal `connected` path hides the
  `progress` toast.

One instance `QTimer` (`_info_timer`) owns the auto-hide, so a newer message is
never hidden by an older timeout.

### Desktop log lines

Every line in the panel — the engine's and the window's own — follows the
grammar of ADR 0046: `<timestamp> - [<pid>] [<correlation field>] LEVEL: message`,
UTC with milliseconds, levels from `hsync_common.logger.LEVEL_STYLES`. Client
lines arrive verbatim (`[<pid>] [<client_id>]`). Desktop-originated events use
`_append_desktop_log(level, message)`
(`hsync_desktop/main_window/ui.py::UiBuildMixin._append_desktop_log`), which renders the same
shape through `hsync_common.logger.format_log_line` with `desktop` in the
correlation slot (no client session exists, so the app's own pid is rendered and
`[desktop]` replaces the CID): `<timestamp> - [<pid>] [desktop] LEVEL: message`.
Nothing writes to the panel with a hand-built prefix — the phase markers
(`--- … ---`: run start, comparison started/ended, stopping, preparing a plan,
selection sync, process finished) are `INFO` lines through the same helper, and
the engine's malformed-event diagnostic is an `ERROR` one (`event_error` →
`hsync_desktop/main_window/ui.py::UiBuildMixin._on_engine_event_error`).

The panel **keeps its lines across runs**: `_mark_new_run`
(`hsync_desktop/main_window/ui.py::UiBuildMixin._mark_new_run`) appends the run boundary
(`sync.log_start`, or `simulation.log_start` in Simulation Mode) instead of
clearing the document, and `_scroll_log_to_end`
(`hsync_desktop/main_window/ui.py::UiBuildMixin._scroll_log_to_end`) jumps the view to it one
event-loop turn later (the scroll range is final only after Qt lays the new block
out). Only the context-menu **Clear Log** empties the panel.

Both producers show the timestamp in the same gray: the engine's lines carry the
client's `<dim>` SGR, and for the SGR-free desktop lines
`hsync_desktop/log_style.py::_fallback_runs` dims the `timestamp` group of `LOG_LINE_RE` with
the `dim` palette entry, so the two never read as two panels.

Events surfaced to the user (Send/Receive busy, nothing to sync, connection
results) additionally raise a toast, so their outcome is visible without the log
panel. Master role changes (`_on_master_conflict`,
`hsync_desktop/main_window/events.py::EventsMixin._on_master_conflict`) are informational: a
takeover by a peer that prefers the primary role is logged only (the role
indicator updates), while a genuine two-prefer_master conflict raises a warning.

### Sync state (link status ≠ file-set state)

The status dot answers "is a device reachable"; it never says whether the file
sets match. A second muted label sits in the bottom bar (built in
`hsync_desktop/main_window/ui.py::UiBuildMixin._load_ui`, right of the share size) and is
rendered by `hsync_desktop/main_window/events.py::EventsMixin._render_sync_state` from the
state remembered in `EventsMixin._set_sync_state`:

| State | When | Key |
| --- | --- | --- |
| `idle` | no engine run, or the link was never up | `sync.state.idle` |
| `offline` | the link dropped after a real connection; per-file statuses keep their last known value | `sync.state.offline` |
| `checking` | on `connected` and on every comparison start `preview_start` or `status_pass_start` | `sync.state.checking` |
| `waiting_inventory` | `sync_pending` with `reason="awaiting_inventory"` (a device is connected but has not published its inventory) | `sync.state.waiting_inventory` |
| `no_devices` | `no_peers` (one-shot abort) or p2p with `total <= 1` | `sync.state.no_devices` |
| `in_sync` | a comparison end (`preview_end` or `status_pass_end`) with nothing pending | `sync.state.in_sync` |
| `pending` | a comparison end with downloads/uploads (a serving pass reports the **worst device's** backlog) | `sync.state.pending` (`{download}`/`{upload}`) |
| `pending_other` | a preview end with only deletes/renames (a serving pass never reports them) | `sync.state.pending_other` (`{count}`) |

The counts come from two sources, one per side of the comparison.

* Requester side: `PreviewStats` (`preview_summary_dialog.py`), filled by
  `EventsMixin._on_file_status` / `_on_file_rename_status` during the preview
  (counts, sizes, the bounded plan rows and the engine-reported policy/guard
  facts); `_sync_state_after_preview` turns its counters into the state.
* Serving side: `EventsMixin._device_stats`, filled by
  `EventsMixin._on_device_status` from the `device_status` rows of the pass;
  `EventsMixin._serving_sync_state` reports the **worst device** (largest
  `pending_here + pending_there`) and its own counts. The state is never a set
  union: a file only one device holds is `in_sync` for that device and pending
  for the others, so `in_sync` here means every device is converged (ADR 0042).

`EventsMixin._begin_comparison` resets both, so repeated comparisons never
inflate the counts nor keep a device that has left. The label is **live during a
transfer**: `EventsMixin._note_transfer_progress` (called from
`EventsMixin._on_file_transferred`) retires one plan item per completed
download/upload and settles to `in_sync`/`pending_other` when nothing is left,
so the counts follow the transfer instead of staying at the plan for its whole
duration. A transfer
observed while the label still reads `checking` — a comparison that left no
verdict (the peer publishes its inventory through the serving pass) — re-derives
the counts from the plan rows the table shows
(`EventsMixin._pending_from_table`), because a file actually moving proves the
peer is reconciled. The label is re-rendered on a
language change from `_apply_translations`; its tooltip
(`EventsMixin._sync_state_tooltip`) starts from `tip.sync_state` and lists every
device as `cccccccc  ↓ pending_here · ↑ pending_there`, plus the published/expected
inventory counts while the waiting state lasts. Per-file rows carry the same
coverage: `file_status` carries `holders`/`devices`, and
`hsync_desktop/file_panel/transfer_table.py::FileTransferModel._row_status` renders
`Synced · 2/3` when some device still lacks the content.

Per-file statuses are a **last known value**, not a live-only signal: dropping
the link sets the summary to `offline` but never rewrites rows to "Local". Only a
new preview/classification (or a fresh scan after an engine restart) changes
them, so a synced file does not look unsynced just because the peer went away.

An engine error whose `reason` is `connection` is the same situation seen from
the comparison side: `hsync_desktop/main_window/ui.py::UiBuildMixin._on_engine_error` sets
`hsync_desktop/main_window/events.py::EventsMixin._link_down` and moves the summary to the
`offline` state (`idle` when nothing was ever linked), and
`hsync_desktop/main_window/events.py::EventsMixin._begin_comparison` refuses to claim `checking`
while it is set. The client retries a comparison whose link dropped on its own,
so without this the state oscillated "Checking…" under a "Disconnected" badge;
the flag clears on the next `connected` status. A non-connection error leaves the
state alone.

Every per-file status burst is bracketed by exactly one marker pair, and both
pairs share one window (`EventsMixin._begin_comparison` … `EventsMixin._end_comparison`),
so the window never infers the end of a burst and the manual check stays disabled
for exactly one comparison:

* `preview_start`/`preview_end` — the preview **this window** requested through
  `hsync_desktop/engine/process.py::HsyncEngine.preview`. Only its end may confirm a pending
  sync: `EventsMixin._on_preview_ended` credits `_pending_initial_reconcile` (only
  when no engine error hit the comparison) and opens
  `ActionsMixin._show_preview_summary` (skipped on failure: the error already
  surfaced, and a plan that was never computed is not offered).
* `status_pass_start`/`status_pass_end` — the classification pass a **serving
  device** runs on its own share (whenever the client re-classifies the share it
  serves; see the client wiki).
  `EventsMixin._on_status_pass_ended` renders the rows, the per-device state and
  stops there: the device that serves the share has nothing to pull, so there is
  no summary and no `SYNC`.

Keeping the pairs distinct is what protects the confirmation one-shot: a
background pass can never consume the preview the window is waiting for.

**Preview changes / compare** (`hsync_desktop/main_window/start.py::StartMixin._on_preview_changes`)
is one entry point with two answers, the model the comparison-first tools use
(FreeFileSync/GoodSync *Compare*, `rsync --dry-run`):

* **engine stopped** → `StartMixin._begin_start(preview=True)`: the dry-run whose
  plan the summary offers as "Sync now";
* **engine running** →
  `hsync_desktop/main_window/start.py::StartMixin._compare_running_engine`, which
  writes `PREVIEW` on the client's stdin and leaves the rest to the role: a
  secondary node answers with the preview cycle (the summary then offers the
  sync), a primary node with its classification pass. `_awaiting_preview_for_sync`
  is therefore armed only for the requester side.

Availability is one predicate,
`StartMixin._can_preview_changes` (a folder is set, no stop in flight, no
comparison in flight, no scoped op — deliberately **not** the run state),
consumed by `UiBuildMixin._update_menu_state` for the menu action, the action-bar
button and `SystemTray.set_preview_changes_enabled`, so the three can never
disagree.

The running-side guards keep the click honest:

* a comparison already running returns at once — `EventsMixin._begin_comparison`
  disables the action and `EventsMixin._end_comparison` re-enables it, and both
  marker pairs (`preview_*`, `status_pass_*`) share that window, so a click never
  queues a second full re-hash;
* no link yet: nothing is written, and the window toasts `tip.compare_waiting`
  instead. A `PREVIEW` there could only fail, and a failed preview still emits
  `preview_end`, which would read as "everything in sync";
* Simulation Mode toasts `simulation.tip`: the whole run is already a preview.

`EventsMixin._stamp_last_check` records `_last_check_at` only when no engine error
hit the comparison (`UiBuildMixin._on_engine_error` sets `_comparison_errored`), and
`UiBuildMixin._update_preview_changes_tooltip` renders it through
`tip.compare_last`; the same helper explains the waiting and "Checking…"
states, and pushes one string to the menu action, the icon-only button and the
tray (`SystemTray.set_preview_changes_tooltip`).
`ActionsMixin._show_preview_summary` reports `compare.no_devices` instead of
`preview.no_actions` when `_sync_state` is `no_devices`, so a lone device never
looks in sync.

The action bar button is **icon-only** (`hsync_desktop/main_window/ui.py::UiBuildMixin._load_ui`
clears its text) and uses the bundled `view-refresh` icon (a magnifier reads as
"search"), so the tooltip is the control's only text; it names the same action as
the menu and the tray (`menu.sync.preview`), which is also the log marker the click
writes (`StartMixin._compare_running_engine`).

The status bar is the second entry point: `EventsMixin._render_sync_state` puts a
pointing cursor and `tip.sync_state_click` on the sync-state label while it reports
`pending`/`pending_other`, and `LifecycleMixin.eventFilter` routes that click to
`StartMixin._on_preview_changes`. Any other state keeps the label inert, so the
bar never starts a run by accident.

The p2p **post-initial-sync catch-up** (`EventsMixin._on_connected_refresh`) is
credited only when the preview answers: it arms
`EventsMixin._pending_initial_reconcile` and
`EventsMixin._on_preview_ended` sets `_initial_reconcile_done`. A command the
client never consumed (or a failed preview) therefore cannot burn the one-shot.

The **initial dry-run** launch (`main_window/start.py` → `_on_start` with
`force_dry_run`) ends with a `SYNC` from
`ActionsMixin._show_preview_summary`. That command is written to the client's
stdin, which only the **slave** role reads, while a freshly started node serves
as master first and runs its own dry-run preview before it yields: the phase is
therefore re-armed (`_awaiting_preview_for_sync`) and the `SYNC` is retried on the
next preview, until a live link clears `_is_dry_run_preview` in
`EventsMixin._on_status`. `_dry_run_preview_reported` keeps the "nothing to sync"
toast to a single message.

### Share size

The status bar (right side, before Peers) shows a muted `QLabel`, rendered by
`hsync_desktop/main_window/ui.py::UiBuildMixin._render_share_size` from the single key
`label.share_size_fmt` ("Shared: X / Y"; `Condivisi: X / Y` in Italian). **X** is
the local size and **Y** the whole-share size; when the total is unknown the
label reads "X / —", and it is a bare `—` before the first value arrives.
**Local** reuses the existing `DirectoryScanWorker` scan: it already `stat`s
every file, so the total is an integer sum with no extra I/O
(`hsync_desktop/file_panel/workers.py::DirectoryScanWorker.size_progress` →
`hsync_desktop/file_panel/panel.py::FilePanel.share_size_changed` →
`hsync_desktop/main_window/ui.py::UiBuildMixin._on_share_size_changed`). All three legs carry
the total as an arbitrary-size Python `int` (`Signal(object)`), so a share
above 2 GiB crosses the Qt marshalling intact. Scan teardown parks (never destroys) a still-running thread
(`FilePanel._join_thread`) and the worker always emits `finished` exactly once.
**Total** is the
`folder_size` event's sync-set union (see the client wiki): the remote/master
listing sizes plus local-only pending uploads, so it is the whole share, not
local + remote; scoped runs skip it. While stopped the total is `—` and the scan
value is kept; `_on_process_finished` clears the total and `_prepare_engine_run`
clears it for the new session.

The client emits `folder_size` once per cycle, *before* that cycle's transfers,
so the value it leaves behind describes the folder as of the cycle start.
`FilePanel.refresh_share_size` (`hsync_desktop/file_panel/panel.py::FilePanel.refresh_share_size`)
therefore re-runs the walk in size-only mode
(`hsync_desktop/file_panel/workers.py::DirectoryScanWorker` with `emit_rows=False`: one pass, no counting
pass, no `files_found`/`progress`) when a cycle completes
(`hsync_desktop/main_window/events.py::EventsMixin._on_sync_completed`) and when the process
ends (`hsync_desktop/main_window/events.py::EventsMixin._on_process_finished`), without
reloading the file table. It is skipped while a full scan is already running.
Sizes use `hsync_common.format.format_bytes`.

## updates.py — Release update check (ADR-0048)

`updates.py` answers one question — is a newer release published? — and never
downloads or runs anything. `fetch_latest_version`
(`hsync_desktop/updates.py::fetch_latest_version`) issues a `HEAD` to the pinned
`releases/latest` redirect (`docs_links.LATEST_RELEASE`, guarded by
`docs_links.is_allowed_docs_url`) and reads the tag from the final URL, so no
GitHub API and no token are involved. `parse_version`/`is_newer`
(`hsync_desktop/updates.py::parse_version`, `hsync_desktop/updates.py::is_newer`) compare dotted integers and
drop `-rc`/`+build` suffixes; unparseable input is never reported as an update.

State lives in `QSettings`: `updates/check_enabled` (opt-in, default
`config.DEFAULT_UPDATE_CHECK` = off), `updates/last_check`,
`updates/latest_version` and `updates/dismissed_version`. `should_check`
(`hsync_desktop/updates.py::should_check`) gates the startup path on the flag and a 24 h
interval; `record_check` (`hsync_desktop/updates.py::record_check`) writes the attempt time
even when the request failed, so an offline machine retries tomorrow rather than
on every launch.

The UI wiring is `ActionsMixin` (`main_window/actions.py::
ActionsMixin.maybe_check_updates_on_startup` and
`hsync_desktop/main_window/actions.py::ActionsMixin._check_for_updates`): the first is called
from `hsync_desktop/main.py::main` and skipped when autostart launched the app into the tray,
the second is the Help-menu `menu.help.updates` action. Both run the blocking
call on `AsyncProbe` (`hsync_desktop/engine/async_probe.py::AsyncProbe`) and render it in
`_on_update_checked`: a failure is reported only for the manual path, a newer
release opens `_offer_update` (Download → the artifact of **this** installation,
`hsync_desktop/release_assets.py::package_url`; the dismissed version is stored per release), an
up-to-date result opens `_show_up_to_date`. Both manual dialogs carry the "check at
startup" switch, which is the only place the opt-in is toggled.

`release_assets.py` answers "which published file is mine?"
(`hsync_desktop/release_assets.py::install_channel`): the snap (`SNAP`) and AppImage (`APPIMAGE`)
markers are checked first, then the platform (`win32`, `darwin`) and the Linux
family from `/etc/os-release` (`ID`/`ID_LIKE` → `.deb` for the Debian family, `.rpm`
for the RPM one). `package_asset` maps that channel plus `platform.machine()` to the
**fixed-name alias** every release publishes (RELEASES.md §5.8), and `package_url`
builds `…/releases/download/v<version>/<alias>` — never the releases *index*, which
renders only its first ten assets behind a "Show all N assets" toggle and hides the
packages the operator is looking for. A channel with no single answer (a snap, which
refreshes itself; an architecture with no build; an unknown distribution) falls back
to the release's **tag** page, whose asset list is complete. ADR-0048 is unchanged:
the button only opens the operator's browser, the app still never downloads or
installs anything.

## splash_screen.py — Splash / About

`SplashScreen` (`hsync_desktop/splash_screen.py::SplashScreen`) loads `ui/splash_screen.ui` and
doubles as the Help → About window. It is a fixed 420×330 frameless window whose
vertical order is: the horizontal brand logo
(`resources/icons/hsync-logo-horizontal.svg`, the same wordmark as the README top
banner, drawn at 240 px wide) above the app name (`app.name`, bold at the default
label size), the version line (`about.version`, `lblVersion`) — the app version
(`__version__`) and the engine version on one line, the latter resolved off the
UI thread by `hsync_desktop/engine/cli.py::BinaryVersionProbe` and shown as an em dash when
undeterminable — the tagline (`app.tagline`), then the copyright (`about.copyright`) and author
(`about.author`) with space above. As the startup welcome it is a short,
click-dismissible overlay (`hsync_desktop/main.py::SPLASH_MS`, 1500 ms): it is shown **only on
the first launch** (`hsync_desktop/main.py::_should_show_splash`: `ui/splash_shown` absent and
`path/local` empty, so an upgraded install with a configured folder never sees it
again) and **never delays** the main window — `hsync_desktop/main.py::main` calls
`activate_window()` first, then shows the overlay, and connects its `finished` to
the setup-wizard hook. On later launches the window is revealed immediately with
no overlay. `show_as_about`
(`hsync_desktop/splash_screen.py::SplashScreen.show_as_about`) keeps it open.
A click anywhere dismisses it: for the splash it emits `finished`
(`main.py` connects it to the setup-wizard hook), for the About it just closes.
The Help → About menu entry is the short `menu.help.about` label ("About" /
"Informazioni"), without the app name.

**Frame.** Being frameless, the window draws a 1 px border from the theme's
`QWidget#SplashScreen` rule (`hsync_desktop/themes.py::_COMMON_QSS`, colours `window_bg` /
`window_border`), so it follows light/dark like the rest of the app. A plain
`QWidget` ignores its stylesheet background/border unless `WA_StyledBackground`
is set, so `SplashScreen.__init__` opts into it; `ui/splash_screen.ui`
deliberately carries no stylesheet.
`tests/test_splash_screen.py::TestSplashFrame` guards both halves.

## Presentation helpers


| Concern | Code | Notes |
| ------- | ---- | ----- |
| Theme | `themes.py` | `detect_system_theme` (`hsync_desktop/themes.py::detect_system_theme`), palettes `_build_light_palette`/`_build_dark_palette` (`hsync_desktop/themes.py::_build_light_palette`/`hsync_desktop/themes.py::_build_dark_palette`), `apply_theme` (`hsync_desktop/themes.py::apply_theme`). KDE/GTK INI reads (`kdeglobals`, `settings.ini`) go through `kde.py` (`hsync_desktop/kde.py::read_ini`, `hsync_desktop/kde.py::config_home`) |
| Confirmations | `widgets/dialogs.py` | `confirm` (`hsync_desktop/widgets/dialogs.py::confirm`) / `build_confirm_box` (`hsync_desktop/widgets/dialogs.py::build_confirm_box`) — one localized Yes/No box (safe `No` default, optional app icons) used by every hand-built confirmation in the main window and the Settings dialog |
| Form rows | `widgets/forms.py` | `add_row` (`hsync_desktop/widgets/forms.py::add_row`) — the labelled `QFormLayout` row shared by the Settings dialog and the setup wizard: caption in the label column, control in the field column, `setBuddy` for focus/mnemonics, alignment left to the platform style hints |
| Fonts | `fonts.py` | `resolve_system_fonts` (`hsync_desktop/fonts.py::resolve_system_fonts`), `apply_system_fonts` (`hsync_desktop/fonts.py::apply_system_fonts`), `ui_font` (`hsync_desktop/fonts.py::ui_font`), `monospace_font` (`hsync_desktop/fonts.py::monospace_font`), `table_font` (`hsync_desktop/fonts.py::table_font`), `small_monospace_font` (`hsync_desktop/fonts.py::small_monospace_font`), `log_monospace_font` (`hsync_desktop/fonts.py::log_monospace_font`) — desktop UI/monospace fonts + text scaling |
| Icons | `icons.py` | themed SVG load `_load_themed_svg` (`hsync_desktop/icons.py::_load_themed_svg`), `icon` (`hsync_desktop/icons.py::icon`)/`themed_icon` (`hsync_desktop/icons.py::themed_icon`), cache `clear_icon_cache` (`hsync_desktop/icons.py::clear_icon_cache`) |
| Tray | `hsync_desktop/system_tray.py::SystemTray` | tray icon/menu; `_make_icon` (`hsync_desktop/system_tray.py::_make_icon`) |
| Notifications | `hsync_desktop/notifications.py::NotificationManager` | OS notifications gated by the notifications pref and the tray being visible; suppressed while the main window is in the foreground (`is_foreground` callback wired in `main.py`) and delivered only when out of focus — errors/warnings are then covered by the in-app toast |
| Single instance | `hsync_desktop/single_instance.py::SingleInstance` | reject a 2nd launch |
| UI loading | `hsync_desktop/ui/loader.py::UiLoader`, `load_ui_widget` (`hsync_desktop/ui/loader.py::load_ui_widget`) | load `.ui` resources |
| Interface language | `i18n.py` | `tr` (`hsync_desktop/i18n.py::tr`), `init_language` (`hsync_desktop/i18n.py::init_language`), `set_language` (`hsync_desktop/i18n.py::set_language`), `_detect_system_language` (`hsync_desktop/i18n.py::_detect_system_language`) — see *Interface language* below |

### Interface language

`hsync_desktop/main.py::main` calls `hsync_desktop/i18n.py::init_language` before any widget exists. The stored
preference is `appearance/language`: `hsync_desktop/i18n.py::AUTO_LANGUAGE` (the default, and
what an absent or unknown value falls back to) follows the system, any other
supported code pins the language, and `hsync_desktop/i18n.py::set_language` stores the
preference as given so `auto` stays dynamic on later launches.

`hsync_desktop/i18n.py::_detect_system_language` resolves the system language in this order:

1. `QLocale.system()` — resolves the desktop locale even when the C library
   reports `("C", "UTF-8")` (glibc with `LANG=it` or `it_IT@euro`), and reads the
   OS locale directly on Windows/macOS.
2. Python's `locale.getlocale()`.
3. `hsync_desktop/i18n.py::_system_wide_locale` — only when the process carries **no** locale
   variable at all (`LC_ALL`, `LC_MESSAGES`, `LANG`, `LANGUAGE` all unset, i.e. a
   stripped environment: `sudo`, a service, a container, a launcher that drops
   the environment). It reads `hsync_desktop/i18n.py::_SYSTEM_LOCALE_FILES` (`/etc/locale.conf`,
   `/etc/default/locale`) with the glibc precedence `LC_ALL` > `LC_MESSAGES` >
   `LANG`. Without this step such a start silently came up in English on a machine
   configured in another language.
4. English.

An explicit process locale always wins over step 3 — including `C`, which stays
English. `hsync_desktop/i18n.py::_language_from_locale` maps a POSIX locale name
(`it`, `it_IT`, `it_IT.UTF-8`, `it_IT@euro`) to its supported base code.

### Host fonts

The GUI follows the desktop's configured fonts instead of Qt's generic default.
`main.py` forces `QT_QPA_PLATFORMTHEME=generic` on Linux (the GTK3 theme plugin
crashes against the bundled GLib/schemas), so `fonts.py` reads the settings
directly: GNOME/Ubuntu via `gsettings` (`font-name`, `monospace-font-name`,
`text-scaling-factor`) and KDE via `~/.config/kdeglobals` (`[General] font`,
`fixed`), then `apply_system_fonts` sets the UI font on the `QApplication` and
caches the monospace font for the log viewer and license dialog. A configured
family that is not installed is kept (Qt/fontconfig substitutes it, as in a
native app) so the configured size is preserved; only a failed probe or an
unknown desktop falls back to `QFontDatabase.systemFont`. The `gsettings`
subprocess runs with
`LD_LIBRARY_PATH`/`PYTHONHOME`/`PYTHONPATH`/`GI_TYPELIB_PATH`/
`GDK_PIXBUF_MODULE_FILE` removed (`hsync_desktop/fonts.py::_host_env`) so the host binary does
not load the bundled GLib. No fonts are bundled. All three sizes derive from the
same cached monospace font (`hsync_desktop/fonts.py::_point_smaller_monospace`): the license
dialog uses `small_monospace_font` (`hsync_desktop/fonts.py::small_monospace_font`, one point
smaller, floor 8 pt) and the log viewer uses `log_monospace_font`
(`hsync_desktop/fonts.py::log_monospace_font`, two points smaller, floor 7 pt) because its lines
are long — at a 9 pt desktop monospace that is 13 visible lines and ~22% more
characters per line than the 8 pt size. `appearance/font_scale` (`standard`
default / `compact`) scales the resolved UI and monospace bases in
`hsync_desktop/fonts.py::resolve_system_fonts` (`compact` = one point smaller, floor 8 pt), so
every derived font follows. The file table uses `table_font`
(`hsync_desktop/fonts.py::table_font`), the cached UI font with no extra delta: desktop size
with `standard`, one point smaller with `compact` (UI labels `Standard` /
`Slightly reduced`, `locales/en.py` keys `settings.font_size_standard` /
`settings.font_size_compact`). `table_row_height`
(`hsync_desktop/fonts.py::table_row_height`, WCAG 2.2 target size) is applied in
`hsync_desktop/file_panel/transfer_table.py::FileTransferTable.refresh_fonts`, which
`hsync_desktop/main_window/start.py::StartMixin._apply_settings_changes` calls when the preference changes.
A live scale change re-resolves the whole window:
`hsync_desktop/main_window/start.py::StartMixin._apply_settings_changes` applies the new
application font and then calls `hsync_desktop/fonts.py::reset_widget_fonts`, which clears the
font of every widget in the tree. That step is mandatory because the stylesheet
resolves each widget's font at polish time and Qt then treats it as explicitly
set, so `QApplication.setFont` alone leaves the status bar and the share/mode
labels at the previous size (only the widgets that receive an explicit
`setFont` — file table, log view, menus — followed). Those explicit fonts are
re-applied right after the reset.
The fonts are set programmatically
(`hsync_desktop/main_window/ui.py::UiBuildMixin._load_ui`, `hsync_desktop/license_dialog.py::LicenseDialog`);
the QSS pins no `font-family`/`font-size` (`hsync_desktop/themes.py::_COMMON_QSS`) but
does frame the log box via `QPlainTextEdit#logView` (the selector must match the
object name in `ui/main_window.ui`; `tests/test_themes.py::TestObjectNameSelectors`
guards it).

### Log panel colors

`build_hsync_args` (`settings/cli_args.py`) launches the engine with
`--color=always` (the client's `--color` contract, `hsync_common.runtime.ColorMode`),
so the raw stdout feed carries the SGR sequences loguru builds from
`hsync_common.logger.LEVEL_STYLES` and `hsync_common.labels.LABEL_STYLES`.
`hsync_desktop/ansi.py::parse_sgr` splits each line into `hsync_desktop/ansi.py::AnsiRun`s (foreground index,
bold, dim) and `hsync_desktop/log_style.py::styled_runs` turns them into `QTextCharFormat`s via
`LOG_COLORS` (`log_style.py`, per theme). Lines without SGR — the Desktop's own
`[<pid>] [desktop] LEVEL:` lines, plain logs — fall back to the same two shared
mappings, matched by `hsync_common.logger.LOG_LINE_RE` (the level, at its grammar
position) and `hsync_desktop/log_style.py::_LABEL_RE` (labels longest-first so
`[REMOTE DOWNLOAD]` never collapses into `[DOWNLOAD]`).

`hsync_desktop/main_window/ui.py::UiBuildMixin._append_log` inserts the runs with a `QTextCursor` (never
`appendPlainText` for styled lines), so the escape sequences are stripped from
`toPlainText()` (copy, tests, `maximumBlockCount` unchanged). Colors are baked
into the formats, so `_rerender_log` (`hsync_desktop/main_window/ui.py::UiBuildMixin._rerender_log`) re-renders the document when the
theme changes, called from `_apply_settings_changes` and
`_on_system_color_scheme_changed`; the re-render works from the plain text and
therefore re-applies the level/label fallback colors.

The panel is bounded on both axes. `hsync_desktop/engine/process.py::HsyncEngine._on_stdout`
emits **one** `log_received` per stdout read (the lines joined by `\n`), and
`hsync_desktop/main_window/ui.py::UiBuildMixin._append_log` splits the payload back and inserts
the whole batch inside a single `beginEditBlock()`/`endEditBlock()`
(`hsync_desktop/main_window/ui.py::UiBuildMixin._insert_log_lines`): the layout, the block
eviction and the scrollbar settle once for the whole burst instead of once per
line. The line count is capped by
`hsync_desktop/main_window/ui.py::_LOG_MAX_BLOCKS` (`QPlainTextEdit.maximumBlockCount`, the
oldest block evicted; the `.ui` declares no cap, so the code is the single source
of truth) and a single line by `hsync_desktop/main_window/ui.py::_LOG_LINE_MAX_CHARS`
(`hsync_desktop/main_window/ui.py::_insert_log_line`, applied after `styled_runs` so an SGR
sequence is never cut in half, marked with `…`).

Dialog buttons use the **bundled (app-theme)** icons: `icon(name)` always prefers
the bundled SVG (recoloured per light/dark) over the system theme, falling back
to the system theme only when no bundled icon exists. The application icon
`hsync-desktop` is bundled in `resources/icons/` and applied in
`hsync_desktop/main.py::_configure_app` together with `setDesktopFileName("hsync-desktop")`, so
the running window's WM_CLASS/app_id matches `hsync-desktop.desktop` and the
taskbar shows the app icon. The app-icon SVG keeps `<svg` at the very top of the
file (no long leading comment): gdk-pixbuf/GNOME only recognizes an SVG when the
root element is within the first bytes, otherwise the icon renders blank. The
dialog accept button's icon **follows the action**
(`hsync_desktop/icons.py::style_ok_cancel_button_box`): an **Apply** caller passes
`accept_icon_key="dialog-ok"` (the confirm check — the Settings dialog and the
bandwidth dialog do), while a **Save** caller keeps the default `document-save`
(the floppy, which means *write to disk* — the credential prompts, the
`TrustedKeysDialog` add dialogs and the `.hsyncignore` editor), always paired
with `dialog-cancel` and the translated `settings.cancel` label. The
`TrustedKeysDialog` **Close** button uses `window-close` with the `action.close`
label (translated in every locale).

> Strings shown here must be looked up via `i18n.tr` and exist in all locales
> (see [settings.md](settings.md)).

> **Ampersands.** `QGroupBox`, `QAbstractButton` and the tab bar read `&` as a
> mnemonic marker and underline the character after it, so prose such as
> "Share & Path" or "Save & Retry" renders as "Share_Path" / "Save_Retry"
> unless the sink escapes it. Those sinks must receive
> `hsync_desktop/widgets/text.py::escape_mnemonics` output; menus keep
> the single `&`, which there *is* the Alt shortcut. A `QLabel` without a buddy,
> the combo-box items, window titles and message boxes already show the
> ampersand and take the raw string. `tests/test_mnemonic_escaping.py` scans
> every locale for a leftover single `&` in the Settings and credential dialogs.

## Safety badges in the bottom bar

Two independent indicators sit next to the status label of
`ui/main_window.ui` (both hidden by default, both refreshed by
`hsync_desktop/main_window/ui.py::UiBuildMixin` on build, on language change and after the
settings are applied):

- `simulationBadge` — `hsync_desktop/main_window/ui.py::UiBuildMixin._refresh_simulation_state`, driven by
  `hsync_desktop/settings/cli_args.py::is_simulation_mode` (window title suffix and tray
  tooltip change with it).
- `deletionBadge` — `hsync_desktop/main_window/ui.py::UiBuildMixin._refresh_deletion_badge`, driven by
  `hsync_desktop/settings/cli_args.py::get_deletion_policy`: visible only while the deletion
  policy is `keep`, so a device that silently never deletes always says so.
  `get_deletion_policy` is the single read of `sync/deletion_policy`, also used
  by `hsync_desktop/settings/cli_args.py::build_hsync_args`, so the badge cannot disagree
  with the flag the engine receives.
