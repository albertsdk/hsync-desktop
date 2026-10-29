# HSYNC Desktop — Setup wizard

Guided, re-runnable configuration assistant (desktop-only). It configures a
**subset** of QSettings from four use-case choices; the Settings dialog remains
the full reference and the only place for advanced options.

## Entry points

| Entry | Code |
| ----- | ---- |
| Menu bar "Setup wizard" | `main_window/ui.py::UiBuildMixin._create_menu_bar` (after Settings) |
| Tray menu "Setup wizard…" | `system_tray.py::SystemTray` (`wizard_requested`) |
| Unconfigured-folder placeholder | `main_window/start.py::StartMixin._on_path_clicked` (empty `_local_path`) |
| First run (once) | `main_window/start.py::StartMixin.maybe_show_setup_wizard`, called by `main.py::main` after the first-launch welcome overlay (`splash.finished`) or directly when the overlay is skipped |

`StartMixin._open_setup_wizard` stops a running sync (with a prompt) before
opening, keeps a single instance, and after an applied run calls
`StartMixin._apply_settings_changes`; "Start syncing" runs after the dialog
closes so the normal pre-flight dialogs stay on the main window. The stop prompt
is a themed confirmation whose Yes/No labels are translated and carry the app
`dialog-ok`/`dialog-cancel` icons (`StartMixin._build_stop_sync_dialog`).

## Shell and pages

`wizard/dialog.py::SetupWizard` is a custom `QDialog` + `QStackedWidget` with a
`wizard/stepper.py::StepIndicator` ("Step N of 4"). Pages implement
`wizard/pages/base.py::WizardPage` (`load`/`store`/`apply_translations`/
`field_error_targets`); the dialog owns validation, the draft and the result
(`applied`, `start_requested`).

The footer (`SetupWizard._update_footer`) shows **Do this later** only while the
app is unconfigured (`wizard/model.py::is_configured` — the same `path/local`
predicate as the first-run prompt), **Skip** only on the Connection step (its
tooltip names what it keeps: `wizard.action.skip_defaults_tip`), Back above the
first step, and Continue/Finish elsewhere.

| Step | Page | Content |
| ---- | ---- | ------- |
| 1 Purpose | `wizard/pages/mode.py::ModePage` | four radio cards (one `QButtonGroup`, single choice) + "Help me choose" |
| 2 Folder | `wizard/pages/folder.py::FolderPage` | path, browse, localized suggestions, free space |
| 3 Connection | `wizard/pages/connection.py::ConnectionPage` | mode-specific fields, in-line probe buttons, automation block |
| 4 Review | `wizard/pages/review.py::ReviewPage` | scrollable summary with uniform Edit buttons |
| Success | `wizard/pages/success.py::SuccessPage` | confirmation, invite, start/dashboard |

"Help me choose" opens `wizard/pages/mode.py::HelpChoiceDialog`: three explicit
questions, each with its own `QButtonGroup` and all labels via `tr()`. The first
("sharing with a team?") resolves `team_share`; otherwise the "Only a copy" /
"Edits from both sides" answer resolves `backup` (a server copy never needs the
network) or, for edits, the same-network question separates `lan_sync` from
`remote_sync`. Nothing is hidden: follow-ups that do not apply stay visible but
are disabled, with a short explanation (`wizard.help.note_*`); the theme grays
the disabled radio labels too (`QRadioButton:disabled`). Confirm stays disabled
until the active path is answered, so all four modes are reachable. The mapping
is `wizard/model.py::resolve_mode` (Qt-free, unit-tested; answers as
`wizard/model.py::ChoiceAnswers`/`ChoiceAudience`), shared by the Confirm gating
and the returned mode so the two can never disagree.

## Interaction details

- **Folder suggestions** (`wizard/defaults.py::suggested_folders`) resolve the
  localized user directories through `QStandardPaths`
  (Documents/Pictures/Music/Videos/Home); each suggestion carries its own icon
  (`x-office-document`, `image-x-generic`, `audio-x-generic`,
  `video-x-generic`, `folder-open`). A suggestion whose path is unset or missing
  is disabled, and the "create an HSYNC folder" entry creates it on click. The
  path placeholder is that suggestion's path (the label above the field already
  names it, so repeating the label inside the field read as a second caption).
- **Free space** is rendered with `hsync_common.format.format_bytes`
  (`FolderCheck.free_bytes`).
- **Test buttons** sit above their own result line and stay disabled until the
  required inputs are present (server: address + key; discovery servers: address);
  `ConnectionPage._update_test_enabled`. The result is a dedicated form row
  below the button (a long error can never overlap it), reported via
  `ConnectionPage._set_status` (grey "checking…" / green success / red error;
  QSS `#statusOk`/`#statusError`), and the rendezvous-server trust buttons appear
  under the result. Editing a test's fields clears its result and captured
  fingerprint (`_on_server_edited`/`_on_rendezvous_server_edited`) so a stale trust pin is
  never applied.
- **Tooltips and placeholders**: every connection field and automation switch
  has a short explanation (`wizard.tip.*`) without changing the visible labels;
  the text fields show language-neutral example placeholders. The rendezvous-server
  field is labelled "Discovery servers address".
- **Controls**: on/off options use the Settings `widgets/toggle_switch.py::ToggleSwitch`
  as plain `QFormLayout` fields (`widgets/forms.py::add_row`), so the automation
  block shares the same two columns and caption/control distance as the fields
  above it (switches in the field column, one line per option); secrets
  show/hide through an icon toggle (`view-visible`/`view-hidden` + tooltip).
  Helper paragraphs use the shared `widgets/labels.py::muted_label`
  (`QLabel#mutedHint`), the same widget the Settings tab descriptions use.
- **Input restriction**: `wizard/widgets.py::char_class_validator` blocks
  disallowed characters on the share name and group; structural rules stay in the
  on-Continue validation.
- **Automation defaults**: the wizard only *recommends* the continuous behaviour.
  `WizardDraft.auto_sync` starts from `config.py::DEFAULT_AUTO_SYNC` and neither
  `SetupWizard._apply_mode_defaults` nor `SetupWizard._on_skip_defaults` turns it
  on: a startup run begins with no user action, so it stays an explicit choice
  (see the *Startup run* note in [ui.md](ui.md)).

## Layout

- **Progress**: `wizard/stepper.py::StepIndicator` shows numbered badges (done =
  check, current = accent, todo = muted) with labels elided to the available
  width; it carries the accessible "Step N of M" name. Labels keep a **uniform
  weight** — step state is carried by the badge and by muting future steps,
  while the bold page title is the single heading emphasis. The dialog adds a
  consistent 24/20/16 margin rhythm.
- **Mode cards**: `wizard/widgets.py::RadioCard` shows a per-mode icon and a
  `selected` dynamic property; `themes.py` draws the border/background state
  (`QFrame#radioCard`, `#radioCard[selected="true"]`) so selection is visible
  without relying on the radio dot alone. Icons: `backup` (cloud + up arrow),
  `network-p2p` (local peers), `network-cloud` (discovery servers/anywhere), `people`
  (team share). The caption is word-wrapped, and a wrapped ``QLabel`` reports one
  line as its minimum height: `RadioCard._sync_description_height` pins it to
  ``heightForWidth(width)`` (on resize and re-translation) so a short window
  cannot squeeze a card until its description is clipped top and bottom.
- **Page host**: the page stack lives in a frame-less, widget-resizable
  `QScrollArea` (`SetupWizard._stack_scroll`) instead of the dialog layout. A
  page therefore never shrinks below its `minimumSizeHint` — the window scrolls
  (`dialog.minimumSize` is the smallest size that triggers it) — which is what
  keeps the mode cards, the connection forms and the review list readable at any
  font scale.
- **Connection**: `ConnectionPage` keeps the share name in a common area and puts
  the server-only and network-only fields in two dedicated forms inside a
  `QStackedWidget` (`_server_page`/`_network_page`), so each topology has a clean
  order instead of interleaved show/hide rows. Field labels carry no trailing
  colon — the label column separates them, as in Settings — and share one fixed
  label-column width (`ConnectionPage._align_labels`), so the share-name field
  aligns with the mode-specific fields; long translations wrap.
  The p2p "receive only" switch resolves
  `ConnectionPage._current_direction` → `draft.direction = "download-only"`, the
  value Settings shows as **Sync Type → Receive only (from other devices)**.
- **Review**: sections are separated by rules and the "Checks" section reflects
  the last real probe (`server_verified`/`rendezvous_server_verified` in the draft, rendered
  as a localised time or the discovery servers fingerprint); editing a section's
  fields clears it. `_set_step` reloads the page on entry, because the summaries
  are rendered from the draft (a stale review used to keep the previous
  direction). The page writes its own ``label: value`` separator over the
  colon-free captions, so each line shows exactly one colon.
- **Success**: `dialog-ok` icon, a centred confirmation line, the p2p invite
  (labelled from `wizard.success.invite`) as a read-only selectable field
  (`SuccessPage._invite_text`) that can also be copied with one click, and the
  action bar is anchored at the bottom of the screen. The invite labels come from
  `wizard.connection.share/group/password`, so it names each value exactly like
  the Connection step, and `wizard.success.invite_text` supplies the single
  separator. The success screen is a destination, not a step: the subtitle and
  the step index are hidden (`SetupWizard._set_step`).

## Modes, defaults and inference

`wizard/model.py::WizardMode` (StrEnum) + `wizard/model.py::profile_for` hold the
per-mode defaults (p2p on/off, direction, keep-deleted, launch-at-login, rendezvous
server, server trust). `wizard/model.py::infer_mode_from_settings` preselects a mode on
re-run from the distinctive traits (p2p on/off, `sync/direction`,
`p2p/rendezvous_server_endpoints`).

Derived names (`wizard/defaults.py::default_share_name`,
`generate_group_name`, `generate_password`) are sanitized so they always pass the
client's bucket/group grammars.

## Draft persistence

`wizard/model.py` saves the draft under `wizard/*` (secrets Fernet-encrypted via
`crypto.py`), debounced from the dialog. Resume restores the last step; a version
bump discards a stale draft. On finish the draft is cleared and
`wizard/completed`/`wizard/version` set.

## Validation, probes and apply

- `wizard/validation.py` returns `Issue(level, code, field)`; the dialog maps
  codes through `wizard/messages.py::issue_message` to `wizard.error|warn.<code>`.
- `engine/async_probe.py::AsyncProbe` runs blocking probes on a `QThread` (mirrors
  `file_panel/workers.py::DirectoryScanWorker`) with a generation counter; the
  wizard, the Settings probes, the trusted-keys read and the MainWindow trust
  pre-flight share it.
- `engine/endpoints.py` normalizes the server/rendezvous-server fields; `engine/probes.py`
  performs `GET /health` and `GET /api/v1/buckets/{bucket}` (the latter is
  mode-aware: a 404 is benign for a fresh backup share — auto-created on first
  upload — and blocks Finish for a team share).
- `wizard/apply.py::apply_draft` writes only the wizard's keys (see the plan's
  mapping) and pins a confirmed certificate through
  `engine/cli.py::add_rendezvous_trust` / `add_server_trust`; a failed pin blocks
  Finish unless the user skips it. Both pins run through
  `_pin_endpoint` (`wizard/apply.py::_pin_endpoint`): resolve the endpoint, fetch
  the fingerprint when the user left it empty, pin, and report `""`/`failed` —
  the server and rendezvous-server paths differ only in those three callables.

## Trust

Discovery servers and server trust use **TOFU + pin** with policy `ask`: "Trust … and save"
writes the fingerprint to the client known-hosts store, "Ask on first start"
leaves the existing first-start pre-flight (`main_window/trust.py`) to confirm.
Never `strict`/`accept-new`.

## Tests

`tests/test_wizard_model.py`, `tests/test_wizard_validation.py`,
`tests/test_wizard_apply.py`, `tests/test_wizard_probes.py`,
`tests/test_wizard_ui.py`; MainWindow wiring in `tests/test_main_window.py`;
terminology/i18n in `tests/test_locales.py`.
