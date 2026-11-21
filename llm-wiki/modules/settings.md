# HSYNC Desktop — Settings, config & CLI args

How the GUI persists user config and turns it into the binary's command line.

## config.py — defaults + keys

Plain module of `DEFAULT_*` constants and app identity (`config.py`): app/org/id
(`hsync_desktop/config.py::SETTINGS_ORG`), server defaults (`hsync_desktop/config.py::DEFAULT_SERVER_TRUST`), sync defaults
(`hsync_desktop/config.py::DEFAULT_CONTINUOUS`), p2p defaults
(`hsync_desktop/config.py::DEFAULT_P2P_TRUST` and neighbours) and NTP servers
(`hsync_desktop/config.py::DEFAULT_NTP_HOSTS`). These seed `QSettings` and the dialog.

Values the GUI shares with the CLI engine are **aliases** of
`hsync-common/hsync_common/defaults.py` (HTTP timeout, retry/stability delays, sync direction,
bandwidth bounds, mass-delete guard, free-space/inbound limits, peer-download
defaults); the delta floors are derived from the client's byte constants
(`hsync-common/hsync_common/constants.py::DELTA_MIN_FILE_SIZE` and
`hsync-common/hsync_common/constants.py::DELTA_MIN_FILE_SIZE_P2P`), since the dialog works in
KB. `tests/test_defaults_parity.py` fails if any of them is written back as a
literal.

`DEFAULT_NO_COMPRESSION` (`hsync_desktop/config.py::DEFAULT_NO_COMPRESSION`) is read only to
migrate a stored `sync/no_compression` value into
`DEFAULT_COMPRESSION_ENABLED` (`hsync_desktop/config.py::DEFAULT_COMPRESSION_ENABLED`).

`DEFAULT_P2P_ENABLED` (`hsync_desktop/config.py::DEFAULT_P2P_ENABLED`) is **True**: a fresh
install (no stored `p2p/enabled` yet) starts in direct mode. Every read of the
`p2p/enabled` key passes it as the QSettings default — `build_hsync_args`
(`hsync_desktop/settings/cli_args.py::build_hsync_args`, picks the `p2p`/`server` subcommand),
`SettingsDialog.load` (`hsync_desktop/settings/dialog.py::SettingsDialog.load`) and the
`main_window/` gate reads — so the dialog toggle, the path display and the
emitted subcommand always agree.

## settings/ — the settings UI

| Symbol | Location | Role |
| ------ | -------- | ---- |
| `SettingsDialog` | `hsync_desktop/settings/dialog.py::SettingsDialog` | settings tabs (sync, connection, general, advanced); load/save QSettings |
| tab builders | `hsync_desktop/settings/tab_builders.py::build_sync_tab`, `hsync_desktop/settings/tab_builders.py::build_connection_tab`, `hsync_desktop/settings/tab_builders.py::_build_server_fields`, `hsync_desktop/settings/tab_builders.py::_build_direct_fields`, `hsync_desktop/settings/tab_builders.py::build_advanced_tab`, `hsync_desktop/settings/tab_builders.py::build_general_tab`, `hsync_desktop/settings/tab_builders.py::setup_language_combo` (+ banner/icons/size helpers) | build each tab's widgets on the dialog; `_load_ui` only orchestrates them |
| tab indices | `hsync_desktop/settings/tab_indices.py::_CONNECTION_TAB_INDEX` | sync/connection tab positions (shared by dialog + builders + layout) |
| tab layout | `hsync_desktop/settings/tab_layout.py::reorganize_sync_tab`, `hsync_desktop/settings/tab_layout.py::reorganize_connection_tab`, `hsync_desktop/settings/tab_layout.py::_scrollable_page`, `hsync_desktop/settings/tab_layout.py::_group_box`, `hsync_desktop/settings/tab_layout.py::_mode_line` | regroup the Sync and Connection tabs into `QGroupBox` sections inside the scrolling page |
| tab translations | `hsync_desktop/settings/tab_translations.py::apply_translations` | apply the i18n strings to every widget, including the tab titles and group titles |
| form helpers | `hsync_desktop/settings/form_helpers.py::_replace_checkbox_with_toggle`, `hsync_desktop/settings/form_helpers.py::_maybe_tip`, `hsync_desktop/settings/form_helpers.py::_paired_label`, `hsync_desktop/settings/form_helpers.py::_set_field_tooltip`, `hsync_desktop/settings/form_helpers.py::_action_row`, `hsync_desktop/settings/form_helpers.py::_insert_row_after` | QFormLayout/QWidget construction helpers shared by the dialogs |
| `ApiKeyDialog` | `hsync_desktop/settings/credential_dialogs.py::ApiKeyDialog` | enter/replace the server API key (secret) |
| `P2PKeyDialog` | `hsync_desktop/settings/credential_dialogs.py::P2PKeyDialog` | enter/replace the p2p key (secret) |
| `HsyncIgnoreEditorDialog` | `hsync_desktop/settings/hsyncignore_dialog.py::HsyncIgnoreEditorDialog` | edit `.hsyncignore` patterns |
| reset sync state | `hsync_desktop/settings/dialog.py::SettingsDialog._on_reset_state` → `hsync_desktop/settings/reset_state_dialog.py::ResetStateDialog` → `SettingsDialog.reset_state_folder` → `hsync_desktop/main_window/start.py::StartMixin._reset_sync_state` | **Settings → Sync → Advanced options → "Reset sync state…"**: a custom dialog rather than `QMessageBox` — the Qt-owned details toggle has no bundled translation and the standard buttons carry no app icon — with a translated details toggle and themed Reset/Cancel icons. It only confirms and closes (setting `reset_state_folder`); the window runs `hsync_desktop/engine/cli.py::reset_sync_state` and logs the outcome. Cancel is the destructive default, so a stray Enter never resets. Gated on `supports_subcommand(doc, "state")` in `_apply_capabilities` and disabled while the sync runs (`set_connection_active`). Never touches files/settings/secrets/identity — see the client's `hsync state reset` |

The settings dialog is a **modal Apply/Cancel** pair: the primary button is
labelled with `settings.apply` (not "Save" — it applies preferences, it does
not store a document) via `hsync_desktop/settings/tab_translations.py::apply_translations` →
`hsync_desktop/icons.py::style_ok_cancel_button_box(accept_text_key="settings.apply", accept_icon_key="dialog-ok")`.
The icon follows the action: Apply carries the confirm check (`dialog-ok`), not
the floppy (`document-save`, which means *save to disk*). The same helper keeps
**Save** — label `settings.save` and the floppy — for the credential prompts,
the trusted-keys Add dialogs and the `.hsyncignore` editor, where persisting an
entry is the operation. The dialog closes on Apply (the window re-applies live
after `hsync_desktop/main_window/start.py::StartMixin._open_settings`); there is no stay-open
Apply button.

**Tab sections** (`_reorganize_sync_tab` / `_reorganize_connection_tab`):
the sync tab groups Path & Bucket, Sync Mode, Timing & Intervals, Advanced Options;
the connection tab groups the choice itself (Connection mode) and then, per
selected mode, the direct boxes (Group, Finding devices, Role & security, Advanced
Options) or the server ones (Server: URL, API key, server identity check and the
manage/test action row; Certificates: skip-certificate check, CA file; Advanced
Options: request timeout) — the user-facing group titles; the wiki below names the
settings keys.
In the sync "Share & Path" group the remote bucket is shown **first** and
presented as **Share name** (`settings.bucket`; `tip.bucket` and the
`trusted_keys.bucket` column use the same share terminology, and `label.bucket`
shares the label though it is currently unused), followed by the local folder
(`settings.shared_path`), so
the user names the share before choosing where to materialize it. All group
titles are refreshed in `_apply_translations`, and both that refresh and the
`_group_box` constructor pass them through `hsync_desktop/widgets/text.py::escape_mnemonics`, so
the `&` of "Share & Path" / "Zeiten & Intervalle" is displayed instead of being
consumed as a keyboard mnemonic (see [ui.md](ui.md)).

**Page padding, no purpose lines**: no settings tab opens with a descriptive
sentence. The group titles and the connection page's two option sentences are
the index, so `_scrollable_page` gives every page its breathing room through the
scroll content's margins (16 px above the first group box, 12 px below the last),
and the connection page's option sentences come from
`hsync_desktop/settings/tab_layout.py::_mode_line` — `muted_label` with a 24 px
indent under the option and a width capped by `_TAB_DESCRIPTION_MAX_WIDTH`, so a
word-wrapped translation wraps instead of widening the dialog. That cap is also
what keeps a long translation inside `finalize_size`'s 640 px floor. Two
constraints to keep:
* `SettingsDialog._set_tab_labels_enabled` skips the labels passed in `exclude`
  and the capability-unsupported ones: the connection page passes its two option
  sentences (`_connection_hint_labels`), so the choice stays readable while a
  running sync grays the fields.
* Keep every locale within `tests/test_locales.py::TestModeOptionSentences`
  (≤ 24 words, no master/rendezvous/relay jargon, rendezvous-server wording in
  the p2p line).

**Tab order**: the tab widget order is sync (0), connection (1), General (2),
Advanced (3), sourced from `ui/settings_dialog.ui` (Advanced is last, after the
app preferences, matching comparable tools). `_SYNC_TAB_INDEX` /
`_CONNECTION_TAB_INDEX` / `_GENERAL_TAB_INDEX` / `_ADVANCED_TAB_INDEX`
(`hsync_desktop/settings/tab_indices.py::_ADVANCED_TAB_INDEX`) name the positions; the
prefer-primary-role prompts' tab jumps and the per-tab enable/disable handlers use
them instead of literals. Advanced holds the engine tuning (performance, delta
transfer, deletion protection, bandwidth, logging); General holds the app
preferences (font size, language, theme, notifications, tooltips, log panel,
launch at login).

**Connection mode**: the connection tab asks one thing first — how this device
reaches the others — through two `QRadioButton`s in an exclusive `QButtonGroup`
(`mode_direct` / `mode_server`, labels `settings.p2p` / `settings.server_mode`,
subtitles the two mode descriptions). `SettingsDialog._apply_connection_mode`
(`hsync_desktop/settings/dialog.py::SettingsDialog._apply_connection_mode`) is the
single place that decides the page: it shows the selected mode's section and hides
the other (values intact, so switching back finds them — nothing but visibility
changes), and composes the three enable axes of the page — the selected mode, a running sync
(`_connection_active`) and the capability gates (`_unsupported_widgets`). It also
refreshes the show-group-key row, the "exclude the local network" toggle and the
changed-password warning, which all depend on the direct half. The choice is
persisted as `p2p/enabled` (`mode_direct` on = direct mode; the fresh-install
default is direct) and `ui/settings_dialog.ui` owns the four pages, with both
modes' fields on `tabConnection`.
Validation follows the selection: `_commit` normalizes the server endpoint, asks
about an API key over plain HTTP and runs the share probe only in server mode, and
validates the shared password plus the discovery-server key reminder only in
direct mode — a value left in the hidden half never blocks a save.
Without the `p2p` subcommand the direct option is disabled with the
capability tooltip and the server option is selected. There is no cross-tab banner
about a disabled tab: the page it used to gray no longer exists.

**Form rows** (`hsync_desktop/widgets/forms.py::add_row`): every option is a `QFormLayout`
row — caption in the label column, control (switch, combo box, spin box, line
edit) in the field column — added through one helper that gives each caption its
`setBuddy` target (mnemonic/focus) and lets it **word-wrap**: a long translation
or a large system font makes the row taller, never wider (see *Content column*).
Single-action rows (`_spanning_row`) span both columns for the same reason: in
the field column a wide caption column squeezes a `QPushButton` below its own
hint, and a button clips its label instead of eliding it. Captions carry
no trailing colon: the two columns separate them (the detail panel and the
status bar keep one because there it introduces a value). Label alignment, field
growth and row wrapping are left to the Qt style hints, so the dialog follows the
host OS (right-aligned captions on macOS, left on Windows/Linux) instead of
hard-coding one desktop's convention. Switches are plain form fields: they share
the one control column with the other controls instead of being pushed to the
window edge, which kept short captions hundreds of pixels away from their switch.

**Content column** (`hsync_desktop/settings/tab_layout.py::_CenteredColumn`): every tab hosts
its groups in one column capped at `_CONTENT_MAX_WIDTH` and centred in the page
(`_scrollable_page`). A wider window grows the empty margins, not the form,
so controls keep a readable width and the caption-to-control distance stays
bounded at any window size. The cap is **hard** — the same measure in every tab,
locale and font size — and the *rows* adapt to it instead: captions wrap
(`forms.py::add_row`), single actions span both columns
(`tab_layout.py::_spanning_row`) and a pair of action buttons that cannot fit
side by side stacks (`form_helpers.py::_ActionRow`). A cap that yields to the
content's size hint instead makes one tab widen towards the window edge while
the others stay centred — the page with the widest label wins, and which page
that is depends on the locale and the system font. The one thing the measure
still follows is an **action button wider than it**
(`tab_builders.py::fit_column_width`): a `QPushButton` neither wraps nor elides,
so the column takes the widest button plus its margins — and the vertical bar's
`PM_ScrollBarExtent`, because a page that scrolls loses it from its viewport —
and every tab follows, keeping the pages aligned. Windows' larger system metrics are what makes that
reachable at the default font — the Italian deletion-risk caption needs 658 px
where a 640 px column leaves 612. Both sizing helpers measure the column itself
(`column.max_width`), so a page whose content prefers less cannot open the dialog
at a narrower width than its siblings; the *realized* column of a scrolling page
is at most one bar narrower, which the tests bound explicitly. The wrapper never
resizes
itself to its own size
hint: its width belongs to the host — a parent layout stretches it, a scroll
area sizes it to the viewport — so only the scroll-area host opts into the
`LayoutRequest` re-apply (`reapply_size_on_layout_request`) that makes the
scroll area pick up a content height change. A plain page item that re-applied
its size hint collapsed to the label's hint as soon as its page was laid out at
the full width, which broke the alignment with the groups below.

**Standard vs advanced**: the General tab's `show_advanced` toggle
(`settings.show_advanced`, persisted as `ui/show_advanced`, default **off**)
drives `SettingsDialog._apply_advanced_visibility`
(`hsync_desktop/settings/dialog.py::SettingsDialog._apply_advanced_visibility`): it hides the
Advanced tab (`setTabVisible`) and the Advanced Options groups in the Sync and
connection tabs plus the Certificates group of the server mode.
`set_current_tab` (`hsync_desktop/settings/dialog.py::SettingsDialog.set_current_tab`) falls
back to the first visible tab so a hidden target never shows a blank page. The
advanced values themselves are preserved; the toggle only changes visibility.

**Notifications**: `hsync_desktop/settings/tab_builders.py::build_general_tab` creates the
master switch plus one `(toggle, label)` pair per entry of
`hsync_desktop/config.py::NOTIFICATION_CATEGORIES`, and
`hsync_desktop/settings/tab_layout.py::reorganize_general_tab` adds the heading
(`settings.notifications_categories`, a spanning row) and every category as a
form row of `SettingsDialog._grp_general_notifications`, so the whole block
shares the page's two columns. The master switch gates the rows through
`SettingsDialog._set_notification_categories_enabled` (it enables each caption
and toggle; there is no container widget any more), and the per-category choices
persist as `appearance/notifications/<category>`. Because a switch is custom-painted, the
disabled state must be drawn:
`hsync_desktop/widgets/toggle_switch.py::ToggleSwitch.paintEvent` fades track and thumb
(`_DISABLED_OPACITY`) and `themes.py` gives `QLabel#mutedHint:disabled` the
disabled tone, so a gated block looks greyed instead of merely inert. Labels
come from `settings.notifications_<category>`; the `peers` category reads
**Devices and role changes** ("Dispositivi e cambi di ruolo") because the UI
never says "peer". The `warnings` category (`settings.notifications_warnings`)
governs the engine's non-fatal `warning` stream — a degraded file watcher, an
unreachable rendezvous — while `connection` keeps the connection-loss and
p2p-role warnings it already had, so the two are tunable independently.

**Dialog sizing & scrolling** (`hsync_desktop/settings/tab_layout.py::_scrollable_page`,
`hsync_desktop/settings/tab_builders.py::finalize_size`): every tab page hosts its content in a
frameless `QScrollArea` (`_scroll_area`), so a tall page — the Advanced tab, or the
mode tabs with their Advanced Options groups shown — scrolls instead of forcing a
tall, fixed window. `finalize_size` runs **after**
`_apply_advanced_visibility`, and the `show_advanced` toggle re-fits the dialog
through `SettingsDialog._on_show_advanced_toggled` with `allow_shrink=False` (it
only grows a too-small window; a maximized or user-resized dialog is left
untouched); the dialog is resizable (no `setFixedSize`) with a 640 px minimum
width, and width/height are clamped to 90% of `_available_screen_size` (the dialog
screen's `availableGeometry`; `None` on a headless platform → content-sized
fallback). The General page is **rebuilt into three sections** like the other tabs
(`hsync_desktop/settings/tab_layout.py::reorganize_general_tab`, wired as
`SettingsDialog._reorganize_general_tab`): **Appearance**
(`settings.group.appearance`: language, theme, font size), **Notifications**
(`settings.group.notifications`: the master switch plus the per-event block) and
**Window & Startup** (`settings.group.window`: tooltips, log panel, launch at
login, with the advanced disclosure as the last row). Each section is a
`QGroupBox` with its own form, so within a section every switch shares one
control column with the other fields; a group whose rows are all switches starts
them at the field column's left edge (the label column is empty), which is the
same shape the Sync/p2p groups already use.
`build_general_tab` only creates the widgets and leaves the layout to the
reorganizer, so the `.ui` form is not reused and the layout is rebuilt. After
the first layout, `fit_current_tab`
(`hsync_desktop/settings/tab_builders.py::fit_current_tab`) grows the dialog for the current
tab when its content fits on screen, so a fitting page shows no vertical
scrollbar; a tab switch re-checks, while a maximized or user-resized window is
never shrunk. `SettingsDialog.showEvent` schedules the first fit so the wrapped
content is measured at its final width. The width it adds to the content hint is
the measured chrome (`_chrome_width`: frame, bars and tab strip as
`dialog.width() - viewport.width()`); `_CONTENT_WIDTH_MARGIN` is only the
pre-show estimate, since the platform's metrics decide the real value.

**Theme**: `appearance/theme` stores `system`/`light`/`dark`.
`get_theme_setting` (`hsync_desktop/settings/cli_args.py::get_theme_setting`) returns the raw
preference and `get_saved_theme` (`hsync_desktop/settings/cli_args.py::get_saved_theme`)
resolves `system` through `hsync_desktop/themes.py::detect_system_theme`. Qt's
`styleHints().colorScheme()` is the primary source; on Linux the app forces
`QT_QPA_PLATFORMTHEME=generic`, so Qt usually reports `Unknown` and detection
falls back to the host settings (`GTK_THEME`, GNOME `gsettings`,
KDE `kdeglobals`, GTK `settings.ini`) and finally the host palette. The General
combo carries stable item data (Light=0, Dark=1, System=2);
`hsync_desktop/main_window/window.py::MainWindow._on_system_color_scheme_changed` follows
`QGuiApplication.styleHints().colorSchemeChanged` and re-applies the theme and
icons live **only** while the preference is `system` (with the generic Linux
platform theme that signal may not fire; launch/settings-apply re-detection is
the reliable path there).

**Font size**: `appearance/font_scale` (General tab) stores `standard` (default)
or `compact` — labelled `Standard` / `Slightly reduced` in the UI
(`locales/en.py` keys `settings.font_size_standard` / `settings.font_size_compact`).
`hsync_desktop/settings/cli_args.py::get_saved_font_scale` reads it;
`hsync_desktop/fonts.py::resolve_system_fonts` scales the resolved UI and monospace bases once
(compact = one point smaller, floor 8 pt), so every derived font follows;
`hsync_desktop/main_window/start.py::StartMixin._apply_settings_changes` re-applies the app font and the explicit
log/table fonts live (`FileTransferTable.refresh_fonts`).

**Timing floors**: the Sync tab enforces the client contract. The periodic full
check is `0` (disabled) or `>= 20 s`;
`SettingsDialog._normalize_resync` snaps 1..19 to 20, and
`hsync_desktop/engine/process.py::apply_settings_env` inserts `HSYNC_RESYNC=0` when disabled
(the client's CLI > env > default precedence makes that authoritative; an
enabled value still travels as `-i`). The retry delay is `>= 5 s`, the maximum
wait uses the shared default
(`hsync-common/hsync_common/defaults.py::MAX_WAIT_TIMEOUT_DEFAULT`) and its spin box spans
`GUI_MAX_WAIT_MIN`..`MAX_WAIT_MAX` (`hsync_desktop/config.py`), and the
HTTP/rendezvous timeouts are `>= 5 s`; `build_hsync_args` clamps stored values to
the same shared bounds (`hsync-common/hsync_common/defaults.py`), so the GUI never emits a
value the CLI rejects.

**Server address**: `settings.server_url` accepts `host`, `host:port`, IPv6 and a
full URL; `_normalize_server_endpoint`
(`hsync_desktop/settings/dialog.py::SettingsDialog._normalize_server_endpoint`) implies
`https://` and the default port (`_SERVER_DEFAULT_PORT`), so the field is labelled
"Server address", not "URL". There is no separate port field. A field left on the
default port also reaches a reverse-proxy deployment on 443: the client's startup
resolution and the Test Connection probe try
`hsync_common/endpoint.py::server_fallback_url` (`SERVER_FALLBACK_PORT`) when the
standard port does not answer.

**Capability gating (§8)**: the direct-mode option (`mode_direct`, which the
server then replaces as the only choice) and the p2p toggles (`prefer_master`,
`never_master`, `p2p_trust`, `peer_download` and its caps) are disabled +
unchecked when the probed `CapabilitiesDoc` (from `engine.get_binary_capabilities`)
lacks the matching CLI option; the unsupported widgets carry the
`tip.capability_unsupported` tooltip. The Advanced engine knobs
(`autotune`, `max_concurrent_transfers`, `delta_enabled`, the delta sizes, the
deletion-protection controls and the bandwidth limits) are gated on the union of
the subcommands' advertised options (the same flags exist for p2p and server);
`--no-peer-download` is p2p-only.
Tooltips are mirrored onto the row's label (and a toggle's inline label) through
`_paired_label`/`_set_field_tooltip`, so hovering the label explains the row too;
the same applies to the capability and the disabled-during-sync tooltips.

**Disabled while syncing**: `SettingsDialog.set_connection_active`
(`hsync_desktop/settings/dialog.py::SettingsDialog.set_connection_active`) shows the warning banner
(`settings.connection_active_warning`) and disables the connection page (both
mode radios included), the sync and the Advanced fields while a sync runs (the
General tab stays live: theme, language and the log panel change without a
restart). The connection page's enable state is composed in one place,
`SettingsDialog._apply_connection_mode`, from the selected mode, this lock and the
capability gates; `_set_tab_labels_enabled`
(`hsync_desktop/settings/dialog.py::SettingsDialog._set_tab_labels_enabled`) grays the
field labels, skipping the banner, the tab description and the connection page's
explanatory lines.

**Prefer-master live gate**: `--prefer-master` is incompatible with a
non-bidirectional direction (it only applies to bidirectional syncs, and is
emitted solely in direct mode). `SettingsDialog._prefer_master_conflict`
(`hsync_desktop/settings/dialog.py::SettingsDialog._prefer_master_conflict`) is True only when all three hold:
direction combo != `bidirectional`, `mode_direct` on, `prefer_master` on.
`SettingsDialog._maybe_warn_prefer_master` (`hsync_desktop/settings/dialog.py::SettingsDialog._maybe_warn_prefer_master`)
shows a Yes/No prompt whose message depends on the trigger (`**fmt` fills the
localized message placeholders, e.g. the active direction label) and returns
True on "Yes". Three consumers:

* Save gate `SettingsDialog._on_accept` (`hsync_desktop/settings/dialog.py::SettingsDialog._on_accept`):
  `warn.prefer_master_msg`, "Yes" resets the direction to `bidirectional` and
  continues saving.
* Live direction check `SettingsDialog._on_sync_direction_changed`
  (`hsync_desktop/settings/dialog.py::SettingsDialog._on_sync_direction_changed`, connected in
  `_connect_signals` to `sync_direction_combo.currentIndexChanged` **after**
  `load()` runs, so restoring a saved conflicting state never warns):
  `warn.prefer_master_disable_msg` offers disabling prefer-master, "Yes"
  unchecks `prefer_master`, selects the direct mode and jumps to the connection tab
  (`_CONNECTION_TAB_INDEX`).
* Live toggle check `SettingsDialog._on_prefer_master_toggled`
  (`hsync_desktop/settings/dialog.py::SettingsDialog._on_prefer_master_toggled`, fires only when prefer-master
  is switched **on**): `warn.prefer_master_sync_msg` names the active direction
  and offers returning to bidirectional, "Yes" resets the direction combo and
  jumps to the sync tab (`_SYNC_TAB_INDEX`).

On "No" from either live check the selection is kept and only the save gate can
prompt again.

### Deferred commit — the bucket-check

`SettingsDialog._commit` returns `False` for two different reasons: a validation
veto, or a **deferred** save. `SettingsDialog._commit` (`hsync_desktop/settings/dialog.py::SettingsDialog._commit`)
ends by asking `_bucket_probe_job` (`hsync_desktop/settings/dialog.py::SettingsDialog._bucket_probe_job`)
for a job: in **server mode** a bucket is verified against the server before
anything is written (`hsync_desktop/engine/probes.py::probe_server_bucket_access`,
on `AsyncProbe`) when the field differs from the persisted `sync/bucket` **or**
when that bucket was never confirmed (`sync/bucket_verified` does not name it).
The second case is what a share created by the selector needs: it already holds
its fresh bucket name in the flat keys, so an equality test alone would skip the
check and the first listing answered 404. Renaming a *share* never reaches this
path — `ShareStore.rename` keeps the bucket.

The authenticated check resolves the connection trust before sending the API key
(`hsync_desktop/engine/server_trust_probe.py::resolve_bucket_trust`): `none`/
`insecure` use the unverified context only because the user asked for it, a
trusted chain uses standard validation, and a self-signed/pinned server uses a
context anchored to its certificate. `auto` resolves an untrusted first sighting
to a certificate-confined context and reports `needs_pin`; `ask`/`strict` require
a saved pin and refuse otherwise; a changed fingerprint is always refused.

The resolver never writes the trust store. `SettingsDialog._bucket_probe_outcome`
pins a first sighting only after the bucket check passed
(`hsync_desktop/engine/server_trust_probe.py::pin_observed_fingerprint`), so a check
that fails (`404`, rejected key, unreachable) leaves no stored identity behind;
only a successful one reports `pinned` and shows `settings.bucket_probe.tofu_saved`
with the fingerprint that was just written.

The callers (`SettingsDialog._on_accept` and the reset-state flow) go through
`SettingsDialog._commit_then` (`hsync_desktop/settings/dialog.py::SettingsDialog._commit_then`):
they hand over a **continuation** (`_commit_continuation`) that runs only once the
answer is in. `_on_probe_done` routes a `probe_target="bucket"` outcome to
`_on_bucket_probe_done` (`hsync_desktop/settings/dialog.py::SettingsDialog._on_bucket_probe_done`):

| Outcome | Action |
| --- | --- |
| 200 | `_mark_bucket_verified` → `_finish_deferred_commit` → `save()` + continuation |
| 404 `share_missing` | three-choice box (`hsync_desktop/widgets/dialogs.py::build_choice_box`): **create the share on the server** (`SettingsDialog._create_bucket_then_commit` → `hsync_desktop/engine/probes.py::create_server_bucket`, then a re-check; 409 counts as success), **save without creating**, or cancel |
| `create_failed` | warning (`settings.bucket_probe.create_failed`) and the save is dropped — for a connection the user edited in this session (see below) |
| `create_quota` | warning (`settings.bucket_probe.quota`, the server's `max_buckets_per_account` in `{max}`) and the save is dropped — the account owns as many shares as the server allows (edited connection only) |
| `unreachable` / `server_error` | localized confirm (`settings.bucket_probe.offline`): offline work stays possible (edited connection; an unrelated save goes through without a prompt) |
| `unauthorized` / `bad_share` | warning (`hsync_desktop/probe_messages.py::probe_reason_text`) and the save is dropped (edited connection; an unrelated save goes through) |

The check never traps the dialog. `SettingsDialog._connection_changed`
(`hsync_desktop/settings/dialog.py::SettingsDialog._connection_changed`) compares
`SettingsDialog._connection_signature`
(`hsync_desktop/settings/dialog.py::SettingsDialog._connection_signature`) — server
URL, bucket, API key, trust policy, insecure flag and CA certificate — with the
values the dialog loaded and last saved. `SettingsDialog._bucket_probe_job`
(`hsync_desktop/settings/dialog.py::SettingsDialog._bucket_probe_job`) returns no
job for an unchanged connection, so `SettingsDialog._commit` saves straight away
and only an edited connection is probed (then warned about and dropped through
`SettingsDialog._on_bucket_probe_done`). A save that changes none of those
fields (language, theme, sync cadence, …) must not depend on the server: it goes
through and leaves the bucket unverified for the next connection edit. Without
that split a revoked key or an unreachable host made every preference unsavable,
because an unverified bucket was probed on every OK press.

A share is never created implicitly: the client's first listing answers 404 for a
missing bucket, so the upload that would create it never runs. The creation is
explicit and the user decides (a typo would create an empty share).

`sync/bucket_verified` is a `SHARE_KEYS` entry, so it travels with the share
record and is written by `SettingsDialog.save`: it holds the bucket the server
confirmed and is emptied as soon as the field names another one (an offline
"save anyway" leaves an unverified name, which the next save checks again).

The OK button is the progress surface (`common.checking`), Cancel stays usable and
closing the dialog drops the continuation (`SettingsDialog.done`).

All the programmatic `setChecked` fixes above (and the mutual exclusion in
`_on_prefer_master_toggled` / `_on_never_master_toggled`, and the
deletion-policy restore) deliberately leave the toggle's signals connected:
`ToggleSwitch` paints from a thumb animation driven by `toggled`, so
swallowing the signal with `blockSignals` freezes the switch painted ON
while `checked` is False — the user's click then re-enables it and
re-triggers the prompt in a loop. Covered by
`tests/test_settings_dialog_warnings.py::TestPreferMasterLiveWarning` and
`tests/test_settings_dialog_warnings.py::TestDeletionPolicyWarning`.

**NTP hosts (ADR-0023)**: `ntp_hosts` (`hsync_desktop/settings/dialog.py::SettingsDialog`, dynamic widget injected
after the rendezvous-timeout row) + `_lbl_ntp_hosts`; save/load under the
`p2p/ntp_hosts` QSettings key (`hsync_desktop/settings/dialog.py::SettingsDialog`); the label comes from
`settings.ntp_hosts` and the tooltip from `tip.ntp_hosts` (all locales). It is
an env-driven setting (no client CLI flag), so `settings/cli_args.py` deliberately does
NOT handle it: the engine injects it as ``HSYNC_NTP_HOSTS`` via
`apply_settings_env` (`hsync_desktop/engine/process.py::apply_settings_env`, called from `hsync_desktop/engine/process.py::HsyncEngine.start`). Empty = the
client's built-in defaults.

**Rendezvous node** (user-facing label **Search server**, translated in every
locale — `Server di individuazione`, `Erkennungsserver`, `Serveur de
découverte`, … — `settings.p2p_rendezvous`):
`p2p_rendezvous` (dynamic `QLineEdit` injected right after the
group row via `_insert_row_after`) + `p2p_rendezvous_trust` (`QComboBox`, filled
by `_populate_rendezvous_trust`) + `p2p_rendezvous_transport` (`QComboBox`,
filled by `_populate_rendezvous_transport` — `auto`/`quic`/`tcp`, the shared
`hsync_common.constants.RDV_TRANSPORTS` vocabulary; RFC 8305 race with QUIC/UDP
preferred and TLS/TCP as the fallback for `auto`) + `btn_manage_trusted_keys` (`QPushButton`,
opens `TrustedKeysDialog` on the rendezvouss tab) + `btn_test_rendezvous`
(`QPushButton`, probes the rendezvous via `fetch_rendezvous_fingerprint` on
`hsync_desktop/engine/async_probe.py::AsyncProbe`) +
`p2p_upnp` (`ToggleSwitch`) + `no_mdns` (`ToggleSwitch`, "Exclude the local
network": enabled only with a search server set, `_refresh_no_mdns_enabled`),
saved/loaded under
`p2p/rendezvous_server_endpoints` / `p2p/rendezvous_server_trust` / `p2p/rendezvous_transport` / `p2p/upnp_enabled` /
`p2p/no_mdns`; labels from
`settings.p2p_rendezvous` / `settings.manage_trusted_keys` /
`settings.p2p_rendezvous_trust` (+ `trust_option.auto` and the three
`*_ask`/`*_strict`/`*_none` option labels) / `settings.p2p_rendezvous_transport` (+ the three
`*_auto`/`*_quic`/`*_tcp` option labels) / `settings.p2p_upnp` / `settings.p2p_no_mdns` (all locales); tips from
`tip.p2p_rendezvous` (what a rendezvous is/does) / `tip.p2p_rendezvous_trust` /
`tip.p2p_rendezvous_transport` /
`tip.manage_trusted_keys` / `tip.p2p_upnp` / `tip.p2p_no_mdns` / `tip.test_rendezvous`, shown per the
`tooltips` preference. These rows are grouped (like the sync tab) into four
`QGroupBox` sections by `reorganize_connection_tab`, inside the direct-mode half of
the page: Group (`settings.group.p2p_group`), Finding devices
(`settings.group.p2p_rendezvous`), Role & Pairing (`settings.group.p2p_role`) and
Advanced Options (`settings.group.advanced`, shared with the sync tab).
Like NTP hosts this is
env-driven (the client positional exists, but `HSYNC_RENDEZVOUS_SERVER_ENDPOINTS` is the documented
equivalent needing no argument plumbing): `apply_settings_env` inserts
`HSYNC_RENDEZVOUS_SERVER_ENDPOINTS` (a `HOST[:PORT]` endpoint: `host`, `host:port`, `[IPv6]`,
`[IPv6]:port`), `HSYNC_MAP_DATA_PORT` (the user's explicit choice),
and — when a rendezvous is set — `HSYNC_RENDEZVOUS_SERVER_TRUST` (`auto` / `ask` /
`strict` / `none`; a stored `chain`/`accept-new` is normalized to `auto` by
`hsync_desktop/config.py::normalize_trust_value`) for the ADR-0035 trust policy. The transport selector travels
as the **`--rendezvous-transport` CLI flag** (`hsync_desktop/settings/cli_args.py::_append_p2p_args`,
`auto`/`quic`/`tcp` from the shared `RDV_TRANSPORTS` vocabulary; `p2p/rendezvous_transport`
QSettings key) — the client reads it that way and there is nothing to interpolate
into the env block. The rendezvous pin itself is not
a GUI setting: it lives in the client's known-hosts store, edited through the
`TrustedKeysDialog` (`trusted_keys.py`) or the pre-flight in
`hsync_desktop/main_window/trust.py::TrustMixin._ensure_trust` (using the
endpoint's real port). The GUI
cannot answer the client's terminal prompt,
so it always sends an explicit policy. Empty rendezvous = mDNS-only rendezvous.
The trust combo and `btn_manage_trusted_keys` follow the panel's gating: both are
disabled when direct mode is off (server mode) and while a sync is running. The
button opens the dialog on the rendezvouss tab; the server panel has its own twin
(`btn_manage_trusted_keys_server`) opening the servers tab, so the two buttons
gate independently. `btn_test_rendezvous` (`_on_test_rendezvous`) is gated like the
other p2p fields (disabled in server mode and while syncing); it reuses the
`settings.test_connection` label and the existing `settings.invalid_rendezvous_endpoint`
key, and reports the rendezvous's certificate fingerprint on success.

**Action rows**: each mode panel pairs its two related secondary actions in one
horizontal row via `_action_row` (`hsync_desktop/settings/form_helpers.py::_action_row`) —
the p2p *Manage trusted keys* + *Test connection* (`btn_test_rendezvous`), and the
Server twin `btn_manage_trusted_keys_server` + `btn_test_connection`. One row reads
as a group and uses less vertical space than two stacked form rows. The pair is
**trailing-aligned** to the content (field) edge — its right edge follows the
inputs instead of floating left under the captions — using a leading stretch that
only grows while the row is horizontal. Both test buttons carry the
`settings.test_connection` label (set in `_apply_translations`).

The row is added with the **single-widget** `QFormLayout` overload
(`hsync_desktop/settings/tab_layout.py::reorganize_connection_tab` →
`g2.addRow(manage_direct)`,
`reorganize_server_tab` → `g1.addRow(action_row)`), so it spans both columns and
gets the full form width; `addRow("", container)` would confine it to the field
column (~330 px at the 640 px dialog minimum), where the localized labels do not
fit and `QPushButton` clips instead of eliding. The row is **rebuilt** in
`reorganize_*` from the two buttons (`_action_row(button, button)`) rather than
captured via `btn.parent()`: the container created in `build_*_tab` is discarded
with the old layout. `hsync_desktop/settings/form_helpers.py::_ActionRow`
re-evaluates on every resize and layout request and stacks the pair vertically
when `_row_width` (both labels plus their spacing) does not fit the row; its
`sizeHint` still reports that side-by-side width while stacked, so the page can
ask for a window wide enough to unfold the pair instead of freezing the stacked
column as the page's natural width. Its vertical size policy is `Minimum`, so a
short page scrolls instead of compressing the buttons below their own height.
The group help links are also spanning rows (`addRow(label)`) for the same
reason; `TestActionRow` pins the stacking, the advertised width and the trailing
alignment, and
`tests/test_settings_dialog_size.py::TestContentWidth::test_the_trust_action_rows_are_not_clipped`
guards the label invariant for the widest locales
(`TestContentWiderThanTheReadingColumn` repeats the labels past the cap, the
geometry the Windows leg failed on).

**Test Connection probes** (`hsync_desktop/settings/dialog.py::SettingsDialog._on_test_connection`
and `SettingsDialog._on_test_rendezvous`): the input validation and its warnings are
synchronous, then `_start_probe` disables the button, labels it
`common.checking` and runs the probe on `hsync_desktop/engine/async_probe.py::AsyncProbe`.
`_on_probe_done` restores both buttons and reports the outcome, and `_end_probe`
drops a pending result when the dialog closes (`SettingsDialog.done`). The
enable state is recomputed from the p2p-mode/capability/connection gates
(`_restore_test_buttons`), never blindly re-enabled. The probe never touches the
UI thread: the rendezvous fingerprint is a client subprocess (up to 15 s) and the
`/health` call waits up to the configured HTTP timeout. Under the `auto` identity
policy the health probe retries without verification when the chain check fails
(`SettingsDialog._server_probe_outcome`): it sends no credentials, and ADR-0051
resolves `auto` to accept-new (TOFU) for an untrusted chain, so a self-signed
server reads as reachable and the sync pins its fingerprint on first use.

**Server**: `server_trust` (`QComboBox`, filled by `_populate_server_trust`,
inserted after the `http_timeout` row), saved/loaded under
`connection/server_trust`; labels from `settings.server_trust` (+ the five
`*_chain`/`*_ask`/`*_accept_new`/`*_strict`/`*_none` option labels), tip from
`tip.server_trust` (all locales). The server pin is not a setting (ADR-0036):
it lives in the client's server known-hosts store. Like the rendezvous policy,
the combo is env-driven: `apply_settings_env` always inserts
`HSYNC_SERVER_TRUST` (`chain` default), and `build_hsync_args` emits no
server-trust flag. The server pin is
edited through the `TrustedKeysDialog` Servers tab, the
`_ensure_trust` pre-flight in `main_window/trust.py`, or the panel's
`btn_manage_trusted_keys_server` (`QPushButton`, opens the dialog on the servers
tab). Like the other Server fields, the combo and the button are disabled when
direct mode is active and while a sync is running.

**Log**: `show_log_panel` (toggle), `verbose` (toggle), `logfile` (`QLineEdit`
with a `LblLogfile` label) render in that order; `quiet` is built but hidden
(the desktop parses stdout, so suppressing output is unsupported). Labels from
`settings.show_log_panel` / `settings.verbose` / `settings.logfile` (all locales).
Enabling `verbose` while the log panel is hidden **and** no log file is set
(`hsync_desktop/settings/dialog.py::SettingsDialog._on_verbose_toggled`) shows a non-blocking
prompt offering to show the panel; "Yes" also checks `show_log_panel`. The option
is not disabled, because a configured log file still captures verbose output. The
signal is connected after `load()`, so a restored `output/verbose=true` never
prompts.

`verbose` maps to the client's `-v` (`hsync_desktop/settings/cli_args.py::_append_output_args`),
i.e. DEBUG level. `output/logfile` adds `--log-file`: the client mirrors the log
there and keeps its stdout sink, so the panel stays the live view while the file
records the same lines.

Validators for dialog fields: `settings/validators.py` — `_validate_path` (`hsync_desktop/settings/validators.py::_validate_path`),
`_validate_bucket` (`hsync_desktop/settings/validators.py::_validate_bucket`), `_validate_group_name`
(`hsync_desktop/settings/validators.py::_validate_group_name`).

## autostart.py — launch at login (desktop-only)

`appearance/start_at_login` is the General-tab toggle `start_at_login` (built by
`hsync_desktop/settings/tab_builders.py::build_general_tab`, placed in the General form,
label `settings.start_at_login`, tip `tip.start_at_login`), a desktop-only
preference (no client CLI flag, so `settings/cli_args.py` is not involved). On accept,
`SettingsDialog._apply_start_at_login` (`hsync_desktop/settings/dialog.py::SettingsDialog._apply_start_at_login`)
reconciles the OS login item through `autostart.py` — `autostart.is_supported`,
`autostart.is_enabled`, `autostart.set_enabled`: a freedesktop XDG entry
(`~/.config/autostart/hsync-desktop.desktop`), a macOS LaunchAgent
(`~/Library/LaunchAgents/io.hsync.desktop.plist`), or the Windows
`HKCU\...\Run` value (removed on uninstall by the `[Registry]`
`uninsdeletevalue` entry in `packaging/windows/hsync-desktop.iss`), each launching
`hsync-desktop --minimized`. The command
is resolved by `hsync_desktop/autostart.py::_launch_command` (`$APPIMAGE` → frozen
`sys.executable` → installed launcher on `PATH` → `python -m hsync_desktop`)
and validated by `hsync_desktop/autostart.py::_autostart_command` (absolute path, no control
characters); a relative `XDG_CONFIG_HOME` is ignored per spec. On supported
platforms `load()` seeds the toggle from `autostart.is_enabled()` (the on-disk
entry is the source of truth, the QSettings value is a mirror); on `OSError`
the dialog warns (`warn.start_at_login_failed`), restores the toggle to the
real state, and stays open without persisting. On a platform without a
mechanism the toggle is disabled (`tip.start_at_login_unsupported`). The
`--minimized` flag (`hsync_desktop/config.py::MINIMIZED_FLAG`) is handled at startup by
`hsync_desktop/main.py::_should_start_minimized` (start hidden only when a tray is
available).

## settings/cli_args.py — config → flags (the contract)

| Symbol | Location | Role |
| ------ | -------- | ---- |
| `build_hsync_args` | `hsync_desktop/settings/cli_args.py::build_hsync_args` | core translator: QSettings → arg list |
| `_relative_subdir` | `hsync_desktop/settings/cli_args.py::_relative_subdir` | normalise the `--subdir` filter to a bucket-relative value (never absolutised); drops `.`/empty components and raises for an invalid non-empty value (fail closed) |
| `secure_config_file` | `hsync_desktop/settings/cli_args.py::secure_config_file` | restrict the on-disk settings file perms (0600) |
| `get_saved_theme` / `get_theme_setting` / `are_notifications_enabled` / `is_log_panel_visible` / `is_auto_sync_enabled` / `is_auto_apply_enabled` | `hsync_desktop/settings/cli_args.py::get_saved_theme` / `hsync_desktop/settings/cli_args.py::get_theme_setting` / `hsync_desktop/settings/cli_args.py::are_notifications_enabled` / `hsync_desktop/settings/cli_args.py::is_log_panel_visible` / `hsync_desktop/settings/cli_args.py::is_auto_sync_enabled` / `hsync_desktop/settings/cli_args.py::is_auto_apply_enabled` | desktop-only prefs |
| `get_bandwidth_limits` / `save_bandwidth_limits` | `hsync_desktop/settings/cli_args.py::get_bandwidth_limits` / `hsync_desktop/settings/cli_args.py::save_bandwidth_limits` | persisted bandwidth caps (bytes/s in, MB/s out) |

**Bandwidth limits** have two entry points that share one set of values
(`sync/bandwidth_upload` / `sync/bandwidth_download`): the Advanced tab's Network
section and `hsync_desktop/bandwidth_dialog.py::BandwidthDialog` opened from the status-bar
sent/received labels (`hsync_desktop/main_window/actions.py::ActionsMixin._show_bandwidth_dialog`).
Both use the same strategy — a `0` field means unlimited (no enable checkbox) —
and the dialog additionally applies the change live through
`hsync_desktop/engine/process.py::HsyncEngine.set_bandwidth` while a sync runs.

The deletion policy (`sync/deletion_policy`) is a two-value combo built by
`hsync_desktop/settings/tab_builders.py::build_sync_tab` through
`hsync_desktop/settings/form_helpers.py::_replace_checkbox_with_combo`, populated and translated by
`hsync_desktop/settings/dialog.py::SettingsDialog._populate_deletion_policy`. Its vocabulary
is the client contract (`hsync-common/hsync_common/defaults.py::DELETION_POLICIES`, aliased
as `config.DELETION_POLICIES`): `propagate` applies deletions both ways,
`keep` never deletes on this device. Unlike a toggle, only the `keep` →
`propagate` transition can destroy data, so that is the only change
`_on_deletion_policy_changed` confirms (and restores on "No").

`build_hsync_args` (`hsync_desktop/settings/cli_args.py::build_hsync_args`) always appends `--allow-deletions` (non-interactive) and
`--color=always` (the client's own palette over the pipe, rendered by the log
panel); the engine appends `--allow-unauthenticated-p2p` for a
keyless p2p run after its own confirmation dialog; emits `--once` when continuous
is off, `--insecure`, `--deletion-policy <value>`, compression flags, the advanced numeric caps (`--min-free-disk-space`,
emitted as a size string such as `500MB`; `--max-inbound-size`), the
Advanced-tab engine knobs (`--no-autotune`,
`--max-concurrent-transfers`, `--no-delta`, `--delta-min-file-size[-p2p]`,
`--no-mass-delete-guard`, `--mass-delete-threshold`, `--mass-delete-percent`),
and the p2p block (the `p2p`/`server` subcommand is the
first token, then `--prefer-master`, `--never-master`, `--p2p-trust`,
`--no-peer-download`). Values matching the client default are omitted so the
engine keeps its own default/auto behaviour; the deletion thresholds are always
clamped and emitted.

The subdirectory filter (`sync/filter_path`) becomes `--subdir` only through
`hsync_desktop/settings/cli_args.py::_relative_subdir`: the engine's `--subdir` is
**bucket-relative** (it prefixes bucket-relative paths, it is never a filesystem
path), so the value is never resolved with `_validate_path` — that would absolutise
it and the filter would match nothing. The helper drops `.`/empty components, and a
non-empty value that cannot be bucket-relative **raises** instead of being dropped,
so the run fails closed rather than widening to the whole bucket; the Settings
dialog validates the field on save and blocks such a value. `build_selection_args`
(`hsync_desktop/settings/cli_args.py::build_selection_args`) uses the same helper for a
scoped Send/Receive.

The peer-download caps (`p2p/peer_read_cap`, `p2p/peer_sources_max`) are env-only
(no CLI flag) and exported by
`hsync_desktop/engine/process.py::apply_settings_env` as `HSYNC_P2P_PEER_READ_CAP` /
`HSYNC_P2P_PEER_SOURCES_MAX` in direct mode.
The UPnP toggle is gated on the client's `--map-data-port` flag (opt-in; enabled
via `--map-data-port` / `HSYNC_MAP_DATA_PORT`, exported by
`hsync_desktop/engine/process.py::apply_settings_env` with the rendezvous-server endpoints; no
`--no-map-data-port` flag exists). A capability-parity test
(`tests/test_cli_args_p2p.py::TestClientCapabilitiesParity`) asserts every
emitted long flag is advertised by the client help output.
One-shot is
expressed via the global `sync/continuous` setting, which maps to
`--once`; **Simulation Mode** (`sync/dry_run`, read through
`hsync_desktop/settings/cli_args.py::is_simulation_mode`) also forces `--once` alongside `-n`, so the
run is a preview-only one-shot instead of a continuous session that a `SYNC`
command could turn into a real sync. Secrets are
**not** here — they go through engine pipe FDs.

**`--group` is optional**, so `build_hsync_args` emits the flag only when
`p2p/group` is non-empty: an emptied field omits it and the client then joins the
**no-group partition** (in the client the group is a strict partition key — a peer
without a group matches only other peers without a group; it is not a wildcard).
Only a **missing** key falls back to `DEFAULT_GROUP` (`my-group`, the value the
dialog seeds on a fresh install), so deleting the name is honoured instead of
being silently re-applied; an invalid non-empty value also falls back to
`DEFAULT_GROUP`. The dialog strips the field on save
(`hsync_desktop/settings/dialog.py::SettingsDialog.save`).

> Any new flag here must mirror an option the client actually exposes
> (`hsync-client` [cli-config.md](../../../hsync-client/llm-wiki/modules/cli-config.md))
> and, if it is an `HSYNC_*`/behavior change, the WD OS5 web UI in `hsync-wd-os5`.

## crypto.py — secrets at rest

Secrets stored in `QSettings` are Fernet-encrypted with a machine-derived key:
`encrypt_value` (`hsync_desktop/crypto.py::encrypt_value`) / `decrypt_value` (`hsync_desktop/crypto.py::decrypt_value`); key derivation
`_derive_key` (`hsync_desktop/crypto.py::_derive_key`) from `_get_machine_id` (`hsync_desktop/crypto.py::_get_machine_id`) + `_APP_SALT` (`hsync_desktop/crypto.py::_APP_SALT`);
stored values carry the `_ENC_PREFIX` (`hsync_desktop/crypto.py::_ENC_PREFIX`) marker. **Both** the API key
(`connection/api_key`) and the p2p key (`p2p/key`) go through encrypt/decrypt
on save/load (`settings/dialog.py`). `decrypt_value` accepts a plaintext
value (no prefix), so an unencrypted stored p2p key stays readable until the
next save. Plaintext secrets only ever leave via the engine's pipe FDs.

The stored p2p secret is either a shared password (the client derives the group
key) or a raw group key, recorded in `p2p/key_mode`. The dialog persists the
mode it resolves for the current field value (`hsync_desktop/settings/dialog.py::SettingsDialog._effective_p2p_key_mode`):
an edited field is a password, an untouched one keeps its stored mode normalised
by `hsync_desktop/engine/process.py::p2p_secret_mode` — a secret shorter than
`hsync_common.protocol.rdv_tokens::MIN_GROUP_KEY_CHARS` cannot be a raw key, so
it is stored as `passphrase`. That normalisation is the same one the engine
applies at start, so a short secret stored as `raw` is repaired on
the next save and accepted by the running engine.

### Group key for a protected search server (connection tab, direct mode)

A protected/private search server derives its bucket tokens from the group
key, so the desktop derives it from the Shared password (`hsync_desktop/settings/credential_dialogs.py::resolve_group_key` →
`hsync_common.protocol.rdv_tokens::derive_group_key`); there is no token to type.

- **Show group key…** (`hsync_desktop/settings/dialog.py::SettingsDialog._on_show_group_key` /
  `_open_group_key_dialog`) lives in the **Finding devices** group
  (`hsync_desktop/settings/tab_layout.py::reorganize_connection_tab`) and is shown **only when a
  search server is configured** (`hsync_desktop/settings/dialog.py::SettingsDialog._refresh_group_key_button`,
  driven by the `p2p_rendezvous` text). The `GroupKeyDialog`
  (`hsync_desktop/settings/credential_dialogs.py::GroupKeyDialog`) shows the whole
  `bucket=<key>` provisioning line as a **single masked secret** (read-only
  `QLineEdit` + the usual reveal toggle), a static caption
  (`group_key.caption`) that never carries the key, a Copy button for the line,
  and the sensitivity warning.
- **Changed-password reminder**: `load()`
  (`hsync_desktop/settings/dialog.py::SettingsDialog.load`) snapshots the derived key the
  dialog opened with into `_group_key_loaded`. While a search server is
  configured and the Shared-password field derives a *different* key, an inline
  warning row appears under the password
  (`hsync_desktop/settings/dialog.py::SettingsDialog._rdv_key_mismatch` /
  `_refresh_rdv_key_warning`, key `settings.p2p_key_rdv_warning`), and
  `_commit` asks once per session before saving
  (`hsync_desktop/settings/dialog.py::SettingsDialog._confirm_rdv_key_update`): **Show group
  key…** (opens the masked dialog with the new line, then continues), **Apply**
  (continue) or **Cancel** (abort). The `P2PKeyDialog` credential prompt shows
  the same informational reminder after saving a changed password when a
  search server is configured (`hsync_desktop/settings/credential_dialogs.py::P2PKeyDialog._maybe_remind_rdv_key_update`),
  and the setup wizard's success page offers the derived line too
  (`hsync_desktop/wizard/pages/success.py::SuccessPage`, only for a draft with a rendezvous
  server — see [wizard.md](wizard.md)).

## i18n.py — localization

`tr` (`hsync_desktop/i18n.py::tr`) looks up keys across all locales (`SUPPORTED_LANGUAGES`, `hsync_desktop/i18n.py::SUPPORTED_LANGUAGES`,
`en/it/de/es/fr/pt/zh/ru/nl/pl/ja`); `init_language` (`hsync_desktop/i18n.py::init_language`) / `set_language` (`hsync_desktop/i18n.py::set_language`) with
`register_language_callback` (`hsync_desktop/i18n.py::register_language_callback`) for live re-translation. The stored
`appearance/language` preference may be `AUTO_LANGUAGE` (`hsync_desktop/i18n.py::AUTO_LANGUAGE` = `"auto"`, the
default, shown as **System default** in the General tab): it follows the system locale at
every launch; a supported code pins that language; an absent/unsupported value also
follows the system locale. `_detect_system_language` (`hsync_desktop/i18n.py::_detect_system_language`) resolves the
OS locale **Qt-first** (`QLocale.system()`, which works without a `QApplication` and still
resolves `LANG=it` / `it_IT@euro` / ISO-8859-1 values that glibc reports as `("C","UTF-8")`),
falls back to Python's `locale`, then English. Every user-facing
string **must** exist in all `hsync_desktop/locales/*.py`.

## Shared endpoint/probe helpers (Settings + wizard)

The server/rendezvous-server reachability logic is shared so the Settings dialog
and the setup wizard agree:

- `hsync_desktop/engine/endpoints.py::normalize_server_endpoint` / `normalize_rendezvous_server_endpoints`
  (the GUI default port `SERVER_DEFAULT_PORT` = 9753; the rendezvous variant is a
  thin wrapper over the shared `hsync_common.endpoint.normalize_bare_endpoint`,
  the same rule the client's `HSYNC_RENDEZVOUS_SERVER_ENDPOINTS` validator applies) and
  `build_probe_ssl_context`; `SettingsDialog._normalize_server_endpoint` /
  `_normalize_rendezvous_server_endpoints` / `_test_connection_ssl_context` delegate to them.
`_on_accept` still normalizes the fields before `save()`. The server probe
(`SettingsDialog._server_probe_outcome`) also tries the shared 443 fallback
(`hsync_common/endpoint.py::server_fallback_url`) so the test agrees with the
client's startup port resolution, and under `auto` retries
`hsync_desktop/engine/endpoints.py::unverified_ssl_context` when the chain is
not trusted (ADR-0051 TOFU). The authenticated bucket probe resolves the same
trust (`hsync_desktop/engine/server_trust_probe.py::resolve_bucket_trust`) before
it sends the API key: `auto` confines an untrusted first sighting to the presented
certificate, `ask`/`strict` require a saved pin, and a changed fingerprint is
refused, so the key never travels over an unverified connection.
- `hsync_desktop/engine/probes.py::probe_server_health` / `probe_server_bucket` /
  `ServerProbeResult`; the Settings "Test connection" action and the wizard both
  use them (`GET /health`, `GET /api/v1/buckets/{bucket}`).
- `hsync_desktop/engine/async_probe.py::AsyncProbe` runs every one of those probes (plus the
  `fetch_*_fingerprint` subprocesses) off the UI thread; see
  [engine.md](engine.md).
- `hsync_desktop/settings/validators.py::validate_sync_folder` / `FolderCheck` back the wizard's
  folder check (existence/type/permission/root error, home/system/low-space
  warning); `FolderCheck.free_bytes` feeds the human-readable free-space display
  (`hsync_common.format.format_bytes`). The system-tree warning is
  platform-aware: `hsync_desktop/settings/validators.py::protected_system_roots`
  returns the POSIX list on Linux, `/System`//`Library`//`Applications` on macOS and
  the `SystemRoot`/`ProgramFiles`/`ProgramFiles(x86)`/`ProgramData` environment
  roots on Windows, and `hsync_desktop/settings/validators.py::_is_protected_system_dir`
  matches a root exactly on Linux and a root **or a directory inside it**,
  case-insensitively, on Windows/macOS.

The setup wizard writes only a subset of keys; see
[wizard.md](wizard.md) for the mapping and the `wizard/*` draft/draft-encryption.

## Named shares (multi-share) — the store and its projection

The flat `QSettings` keys stay the **active projection** (the live config), so
`build_hsync_args` (`hsync_desktop/settings/cli_args.py::build_hsync_args`) and every reader are
unchanged. On top of them, `hsync_desktop/shares/store.py::ShareStore` keeps a list of **named
shares** and swaps the projection on switch.

- **Key set** — `hsync_desktop/shares/keys.py::SHARE_KEYS` is the typed registry
  (`key -> (default, type)`) of the per-share settings: `path/local`, all of
  `sync/*`, `p2p/*`, `connection/*`, `advanced/*` and `output/logfile`. The type
  is required (the INI backend returns strings; `"false"` re-read as a bool would
  be truthy). Global keys (`appearance/*`, `ui/*`, `output/verbose`,
  `output/quiet`, `binary/*`, `window/*`) are never stored per share.
  `hsync_desktop/shares/keys.py::SHARE_PREFIXES` bounds what `apply` may write, so a
  hand-edited blob can never clobber a global setting; the encrypted keys
  (`connection/api_key`, `p2p/key`) are copied verbatim as stored (never decrypted
  or logged; see `hsync_desktop/settings/crypto.py`).
- **Storage** — `BOOK_KEY` = `shares/v1`: a versioned JSON blob
  (`hsync_desktop/shares/model.py::ShareBook`) with the shares and the active id, in the same
  `QSettings`. An unreadable/unknown-version blob is moved aside
  (`shares/v1.corrupt-<ts>`) and migration re-runs.
- **Snapshot / apply** — `hsync_desktop/shares/store.py::ShareStore.snapshot_active` writes the
  current flat keys into the active share (one exception: a `path/local` another
  share claims, see *Invariants*); `hsync_desktop/shares/store.py::ShareStore.apply`
  **removes every `SHARE_KEYS` entry first** (so a value the target does not set
  cannot leak) then writes the record. The flat keys are the live truth: the
  active share is refreshed at startup and right before every switch, so a crash
  never loses edits (`hsync_desktop/shares/store.py::ShareStore.sync_from_flat` runs on every
  settings/wizard apply, `LifecycleMixin._shutdown` snapshots on quit).
- **Migration** — an existing install becomes share #1 (`migrate_if_needed`, the
  flat keys are never touched); a fresh install stays empty until the first
  configuration creates share #1 (`ensure_first_share`).
- **Naming** — `name` is a free-form unique label; `sync/bucket` is the stable
  identifier seeded at creation from the sanitized name (fallback
  `hsync_desktop/wizard/defaults.py::default_share_name`). **Renaming never changes the
  bucket**; the bucket changes only by an explicit Settings edit (Syncthing's
  Label vs Folder ID).
- **Invariants** — a local folder belongs to **one** share
  (`hsync_desktop/shares/store.py::ShareStore.folder_in_use`, canonical
  `normcase(realpath)`), because the client takes a per-directory instance lock
  (`hsync_client/identity.py::InstanceLock`) and keeps a per-folder state DB
  (`hsync_client/state_backend.py::resolve_bucket_folder`). Every entry point
  refuses a claimed folder: `hsync_desktop/main_window/shares.py::SharesMixin._create_share`,
  `hsync_desktop/main_window/shares.py::SharesMixin._duplicate_share`, the folder edit
  in `hsync_desktop/settings/dialog.py::SettingsDialog._commit` (scoped to a changed
  field, so a claim that predates the dialog can never block a save) and the
  folder step of the wizard (`hsync_desktop/wizard/validation.py::validate_folder`,
  issue code `folder_in_use`, wired by
  `hsync_desktop/main_window/start.py::StartMixin._open_setup_wizard` and re-checked by
  `hsync_desktop/wizard/dialog.py::SetupWizard._finish` for a resumed draft). As the last
  line of defence `hsync_desktop/shares/store.py::ShareStore.snapshot_active` never
  adopts a flat `path/local` another share claims: it keeps the record's folder,
  writes it back to the projection and returns the claiming share, which
  `hsync_desktop/main_window/start.py::StartMixin._apply_settings_changes` reports in the
  log (never a dialog). Same bucket on two p2p shares is allowed but a
  same-device hazard.
- **Delete** — `hsync_desktop/shares/store.py::ShareStore.delete` only drops the
  configuration (never files); the window offers the default-checked *clear local
  sync state* (`hsync_desktop/engine/cli.py::reset_sync_state`), run **before** the
  record is removed so a failed reset leaves the share retryable. The store
  activates the `next_active` neighbour the dialog passes (fallback: the first
  share in `hsync_desktop/shares/store.py::ShareStore.shares_sorted` order), so the
  window lands on the row the user is looking at instead of an arbitrary record.
