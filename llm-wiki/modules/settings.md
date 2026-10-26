# HSYNC Desktop — Settings, config & CLI args

How the GUI persists user config and turns it into the binary's command line.

## config.py — defaults + keys

Plain module of `DEFAULT_*` constants and app identity (`config.py`): app/org/id
(`config.py::SETTINGS_ORG`), server defaults (`config.py::DEFAULT_SERVER_TRUST`), sync defaults
(`config.py::DEFAULT_CONTINUOUS`), p2p defaults
(`config.py::DEFAULT_P2P_REQUIRE_PAIRING` and neighbours) and NTP servers
(`config.py::DEFAULT_NTP_HOSTS`). These seed `QSettings` and the dialog.

Values the GUI shares with the CLI engine are **aliases** of
`hsync_common/defaults.py` (HTTP timeout, retry/stability delays, sync direction,
bandwidth bounds, mass-delete guard, free-space/inbound limits, peer-download
defaults); the delta floors are derived from the client's byte constants
(`hsync_common/constants.py::DELTA_MIN_FILE_SIZE` and
`hsync_common/constants.py::DELTA_MIN_FILE_SIZE_P2P`), since the dialog works in
KB. `tests/test_defaults_parity.py` fails if any of them is written back as a
literal.

`DEFAULT_NO_COMPRESSION` (`config.py::DEFAULT_NO_COMPRESSION`) is read only to
migrate a stored `sync/no_compression` value into
`DEFAULT_COMPRESSION_ENABLED` (`config.py::DEFAULT_COMPRESSION_ENABLED`).

`DEFAULT_P2P_ENABLED` (`config.py::DEFAULT_P2P_ENABLED`) is **True**: a fresh
install (no stored `p2p/enabled` yet) starts in p2p mode. Every read of the
`p2p/enabled` key passes it as the QSettings default — `build_hsync_args`
(`settings/cli_args.py::build_hsync_args`, picks the `p2p`/`server` subcommand),
`SettingsDialog.load` (`settings/dialog.py::SettingsDialog.load`) and the
`main_window/` gate reads — so the dialog toggle, the path display and the
emitted subcommand always agree.

## settings/ — the settings UI

| Symbol | Location | Role |
| ------ | -------- | ---- |
| `SettingsDialog` | `settings/dialog.py::SettingsDialog` | settings tabs (sync, p2p, server, log, appearance); load/save QSettings |
| tab builders | `settings/tab_builders.py::build_sync_tab`, `settings/tab_builders.py::build_server_tab`, `settings/tab_builders.py::build_p2p_tab`, `settings/tab_builders.py::build_advanced_tab`, `settings/tab_builders.py::build_general_tab`, `settings/tab_builders.py::setup_language_combo` (+ banner/icons/size helpers) | build each tab's widgets on the dialog; `_load_ui` only orchestrates them |
| tab indices | `settings/tab_indices.py::_P2P_TAB_INDEX`, `settings/tab_indices.py::_TAB_DESCRIPTION_KEYS` | sync/p2p/server tab positions and the per-tab purpose string keys (shared by dialog + builders + layout) |
| tab layout | `settings/tab_layout.py::reorganize_sync_tab`, `settings/tab_layout.py::reorganize_p2p_tab`, `settings/tab_layout.py::reorganize_server_tab`, `settings/tab_layout.py::_group_box`, `settings/tab_layout.py::_add_tab_description` | regroup the Sync/p2p/Server Mode tabs into `QGroupBox` sections and open each with its purpose line |
| tab translations | `settings/tab_translations.py::apply_translations` | apply the i18n strings to every widget, including the tab descriptions and group titles |
| form helpers | `settings/form_helpers.py::_replace_checkbox_with_toggle`, `settings/form_helpers.py::_maybe_tip`, `settings/form_helpers.py::_paired_label`, `settings/form_helpers.py::_set_field_tooltip`, `settings/form_helpers.py::_action_row`, `settings/form_helpers.py::_insert_row_after` | QFormLayout/QWidget construction helpers shared by the dialogs |
| `ApiKeyDialog` | `settings/credential_dialogs.py::ApiKeyDialog` | enter/replace the server API key (secret) |
| `P2PKeyDialog` | `settings/credential_dialogs.py::P2PKeyDialog` | enter/replace the p2p key (secret) |
| `HsyncIgnoreEditorDialog` | `settings/hsyncignore_dialog.py::HsyncIgnoreEditorDialog` | edit `.hsyncignore` patterns |
| reset sync state | `settings/dialog.py::SettingsDialog._on_reset_state` → `settings/reset_state_dialog.py::ResetStateDialog` → `SettingsDialog.reset_state_folder` → `main_window/start.py::StartMixin._reset_sync_state` | **Settings → Sync → Advanced options → "Reset sync state…"**: a custom dialog rather than `QMessageBox` — the Qt-owned details toggle has no bundled translation and the standard buttons carry no app icon — with a translated details toggle and themed Reset/Cancel icons. It only confirms and closes (setting `reset_state_folder`); the window runs `engine/cli.py::reset_sync_state` and logs the outcome. Cancel is the destructive default, so a stray Enter never resets. Gated on `supports_subcommand(doc, "state")` in `_apply_capabilities` and disabled while the sync runs (`set_connection_active`). Never touches files/settings/secrets/identity — see the client's `hsync state reset` |

**Tab sections** (`_reorganize_sync_tab` / `_reorganize_p2p_tab` / `_reorganize_server_tab`):
the sync tab groups Path & Bucket, Sync Mode, Timing & Intervals, Advanced Options;
the p2p tab groups Mode & Group, Finding devices, Role & security, Advanced
Options; the Server Mode tab groups Server (URL, API key, server identity check and
the manage/test action row), Certificates (skip-certificate check, CA file) and
Advanced Options (request timeout), with the p2p-mode banner kept above the groups
(the user-facing group titles; the wiki below names the settings keys).
In the sync "Share & Path" group the remote bucket is shown **first** and
presented as **Share name** (`settings.bucket`; `tip.bucket` and the
`trusted_keys.bucket` column use the same share terminology, and `label.bucket`
shares the label though it is currently unused), followed by the local folder
(`settings.shared_path`), so
the user names the share before choosing where to materialize it. All group
titles are refreshed in `_apply_translations`, and both that refresh and the
`_group_box` constructor pass them through `widgets/text.py::escape_mnemonics`, so
the `&` of "Share & Path" / "Zeiten & Intervalle" is displayed instead of being
consumed as a keyboard mnemonic (see [ui.md](ui.md)).

**Tab descriptions** (`_add_tab_description`): the Sync, p2p and Server Mode tabs
open with one muted sentence stating what the tab is for, built from
`_TAB_DESCRIPTION_KEYS` (`settings.sync.description` /
`settings.p2p.description` / `settings.server_mode.description`). The label uses
`widgets/labels.py::muted_label` — the same `QLabel#mutedHint` rule as the wizard
helper text — so it does not introduce a second visual language. Its insets come
from `settings/tab_layout.py::_DESCRIPTION_MARGINS` (applied with
`setContentsMargins`, not QSS, which keeps owning only the muted colour), so the
sentence is inset from the tab edge, below the tab bar and above the first group
box. General and
Advanced are deliberately left undescribed (their group titles already read as an
index), so `_TAB_DESCRIPTION_KEYS` is the single place that decides which tabs get
one. Two constraints to keep:
* `SettingsDialog._set_tab_labels_enabled` skips
  `SettingsDialog._tab_descriptions`, so the sentence stays readable while p2p mode
  grays the Server Mode tab or a running sync grays the others.
* `_TAB_DESCRIPTION_MAX_WIDTH` caps the label: a wrapped `QLabel` reports its
  unwrapped text width as `sizeHint`, so a longer translation would widen the page
  instead of wrapping. Keep every locale within
  `tests/test_locales.py::TestTabDescriptions` (≤ 24 words, no
  master/bootnode/relay jargon, discovery-server wording in the p2p line).

**Tab order**: the tab widget order is sync (0), p2p (1), Server Mode (2),
General (3), Advanced (4), sourced from `ui/settings_dialog.ui` (the p2p page
precedes the Server Mode page, and Advanced is last, after the app preferences,
matching comparable tools). `_SYNC_TAB_INDEX` / `_P2P_TAB_INDEX` /
`_SERVER_TAB_INDEX` / `_GENERAL_TAB_INDEX` / `_ADVANCED_TAB_INDEX`
(`settings/tab_indices.py::_ADVANCED_TAB_INDEX`) name the positions; the
prefer-primary-role prompts' tab jumps and the per-tab enable/disable handlers use
them instead of literals. Advanced holds the engine tuning (performance, delta
transfer, deletion protection, bandwidth, logging); General holds the app
preferences (font size, language, theme, notifications, tooltips, log panel,
launch at login).

**Form rows** (`widgets/forms.py::add_row`): every option is a `QFormLayout`
row — caption in the label column, control (switch, combo box, spin box, line
edit) in the field column — added through one helper that gives each caption its
`setBuddy` target (mnemonic/focus) and keeps it on a single line. Captions carry
no trailing colon: the two columns separate them (the detail panel and the
status bar keep one because there it introduces a value). Label alignment, field
growth and row wrapping are left to the Qt style hints, so the dialog follows the
host OS (right-aligned captions on macOS, left on Windows/Linux) instead of
hard-coding one desktop's convention. Switches are plain form fields: they share
the one control column with the other controls instead of being pushed to the
window edge, which kept short captions hundreds of pixels away from their switch.

**Content column** (`settings/tab_layout.py::_CenteredColumn`): every tab hosts
its groups in one column capped at `_CONTENT_MAX_WIDTH` and centred in the page
(`_scrollable_page`); the tab description uses the same wrapper
(`_add_tab_description`). A wider window grows the empty margins, not the form,
so controls keep a readable width and the caption-to-control distance stays
bounded at any window size.

**Standard vs advanced**: the General tab's `show_advanced` toggle
(`settings.show_advanced`, persisted as `ui/show_advanced`, default **off**)
drives `SettingsDialog._apply_advanced_visibility`
(`settings/dialog.py::SettingsDialog._apply_advanced_visibility`): it hides the
Advanced tab (`setTabVisible`) and the Advanced Options groups in the Sync/p2p
tabs plus the Certificates and Advanced Options groups in the Server Mode tab.
`set_current_tab` (`settings/dialog.py::SettingsDialog.set_current_tab`) falls
back to the first visible tab so a hidden target never shows a blank page. The
advanced values themselves are preserved; the toggle only changes visibility.

**Notifications**: `settings/tab_builders.py::build_general_tab` creates the
master switch plus one `(toggle, label)` pair per entry of
`config.py::NOTIFICATION_CATEGORIES`, and
`settings/tab_layout.py::reorganize_general_tab` adds the heading
(`settings.notifications_categories`, a spanning row) and every category as a
form row of `SettingsDialog._grp_general_notifications`, so the whole block
shares the page's two columns. The master switch gates the rows through
`SettingsDialog._set_notification_categories_enabled` (it enables each caption
and toggle; there is no container widget any more), and the per-category choices
persist as `appearance/notifications/<category>`. Because a switch is custom-painted, the
disabled state must be drawn:
`widgets/toggle_switch.py::ToggleSwitch.paintEvent` fades track and thumb
(`_DISABLED_OPACITY`) and `themes.py` gives `QLabel#mutedHint:disabled` the
disabled tone, so a gated block looks greyed instead of merely inert. Labels
come from `settings.notifications_<category>`; the `peers` category reads
**Devices and role changes** ("Dispositivi e cambi di ruolo") because the UI
never says "peer".

**Dialog sizing & scrolling** (`settings/tab_layout.py::_scrollable_page`,
`settings/tab_builders.py::finalize_size`): every tab page hosts its content in a
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
(`settings/tab_layout.py::reorganize_general_tab`, wired as
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
(`settings/tab_builders.py::fit_current_tab`) grows the dialog for the current
tab when its content fits on screen, so a fitting page shows no vertical
scrollbar; a tab switch re-checks, while a maximized or user-resized window is
never shrunk. `SettingsDialog.showEvent` schedules the first fit so the wrapped
content is measured at its final width.

**Theme**: `appearance/theme` stores `system`/`light`/`dark`.
`get_theme_setting` (`settings/cli_args.py::get_theme_setting`) returns the raw
preference and `get_saved_theme` (`settings/cli_args.py::get_saved_theme`)
resolves `system` through `themes.py::detect_system_theme`. Qt's
`styleHints().colorScheme()` is the primary source; on Linux the app forces
`QT_QPA_PLATFORMTHEME=generic`, so Qt usually reports `Unknown` and detection
falls back to the host settings (`GTK_THEME`, GNOME `gsettings`,
KDE `kdeglobals`, GTK `settings.ini`) and finally the host palette. The General
combo carries stable item data (Light=0, Dark=1, System=2);
`main_window/window.py::MainWindow._on_system_color_scheme_changed` follows
`QGuiApplication.styleHints().colorSchemeChanged` and re-applies the theme and
icons live **only** while the preference is `system` (with the generic Linux
platform theme that signal may not fire; launch/settings-apply re-detection is
the reliable path there).

**Font size**: `appearance/font_scale` (General tab) stores `standard` (default)
or `compact` — labelled `Standard` / `Slightly reduced` in the UI
(`locales/en.py` keys `settings.font_size_standard` / `settings.font_size_compact`).
`settings/cli_args.py::get_saved_font_scale` reads it;
`fonts.py::resolve_system_fonts` scales the resolved UI and monospace bases once
(compact = one point smaller, floor 8 pt), so every derived font follows;
`main_window/start.py::StartMixin._apply_settings_changes` re-applies the app font and the explicit
log/table fonts live (`FileTransferTable.refresh_fonts`).

**Timing floors**: the Sync tab enforces the client contract. The periodic full
check is `0` (disabled) or `>= 20 s`;
`SettingsDialog._normalize_resync` snaps 1..19 to 20, and
`engine/process.py::apply_settings_env` inserts `HSYNC_RESYNC=0` when disabled
(the client's CLI > env > default precedence makes that authoritative; an
enabled value still travels as `-i`). The retry delay is `>= 5 s`, the maximum
wait uses the shared default
(`hsync_common/defaults.py::MAX_WAIT_TIMEOUT_DEFAULT`) and its spin box spans
`GUI_MAX_WAIT_MIN`..`MAX_WAIT_MAX` (`hsync_desktop/config.py`), and the
HTTP/discovery timeouts are `>= 5 s`; `build_hsync_args` clamps stored values to
the same shared bounds (`hsync_common/defaults.py`), so the GUI never emits a
value the CLI rejects.

**Server address**: `settings.server_url` accepts `host`, `host:port`, IPv6 and a
full URL; `_normalize_server_endpoint`
(`settings/dialog.py::SettingsDialog._normalize_server_endpoint`) implies
`https://` and the default port (`_SERVER_DEFAULT_PORT`), so the field is labelled
"Server address", not "URL". There is no separate port field.

**Capability gating (§8)**: p2p toggles (`p2p_mode`, `prefer_master`,
`never_master`, `require_pairing`, `peer_download` and its caps) are disabled +
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
(`settings/dialog.py::SettingsDialog.set_connection_active`) shows the warning banner
(`settings.connection_active_warning`) and disables the connection, sync, p2p and
Advanced fields while a sync runs (the General tab stays live: theme, language
and the log panel change without a restart). `_set_tab_labels_enabled`
(`settings/dialog.py::SettingsDialog._set_tab_labels_enabled`) also grays each tab's
field labels — the same visual the Server Mode tab uses when p2p mode is active
(`_on_p2p_mode_toggled`, sharing the helper) — so a disabled panel reads as
disabled; banner labels and capability-unsupported labels are skipped.

**Prefer-master live gate**: `--prefer-master` is incompatible with a
non-bidirectional direction (it only applies to bidirectional syncs, and is
emitted solely in p2p mode). `SettingsDialog._prefer_master_conflict`
(`settings/dialog.py::SettingsDialog._prefer_master_conflict`) is True only when all three hold:
direction combo != `bidirectional`, `p2p_mode` on, `prefer_master` on.
`SettingsDialog._maybe_warn_prefer_master` (`settings/dialog.py::SettingsDialog._maybe_warn_prefer_master`)
shows a Yes/No prompt whose message depends on the trigger (`**fmt` fills the
localized message placeholders, e.g. the active direction label) and returns
True on "Yes". Three consumers:

* Save gate `SettingsDialog._on_accept` (`settings/dialog.py::SettingsDialog._on_accept`):
  `warn.prefer_master_msg`, "Yes" resets the direction to `bidirectional` and
  continues saving.
* Live direction check `SettingsDialog._on_sync_direction_changed`
  (`settings/dialog.py::SettingsDialog._on_sync_direction_changed`, connected in
  `_connect_signals` to `sync_direction_combo.currentIndexChanged` **after**
  `load()` runs, so restoring a saved conflicting state never warns):
  `warn.prefer_master_disable_msg` offers disabling prefer-master, "Yes"
  unchecks `prefer_master` and jumps to the p2p tab (`_P2P_TAB_INDEX`).
* Live toggle check `SettingsDialog._on_prefer_master_toggled`
  (`settings/dialog.py::SettingsDialog._on_prefer_master_toggled`, fires only when prefer-master
  is switched **on**): `warn.prefer_master_sync_msg` names the active direction
  and offers returning to bidirectional, "Yes" resets the direction combo and
  jumps to the sync tab (`_SYNC_TAB_INDEX`).

On "No" from either live check the selection is kept and only the save gate can
prompt again.

All the programmatic `setChecked` fixes above (and the mutual exclusion in
`_on_prefer_master_toggled` / `_on_never_master_toggled`, and the
ignore-delete restore) deliberately leave the toggle's signals connected:
`ToggleSwitch` paints from a thumb animation driven by `toggled`, so
swallowing the signal with `blockSignals` freezes the switch painted ON
while `checked` is False — the user's click then re-enables it and
re-triggers the prompt in a loop. Covered by
`tests/test_settings_dialog_warnings.py::TestPreferMasterLiveWarning` and
`tests/test_settings_dialog_warnings.py::TestIgnoreDeleteWarning`.

**NTP hosts (ADR-0023)**: `ntp_hosts` (`settings/dialog.py::SettingsDialog`, dynamic widget injected
after the discovery-timeout row) + `_lbl_ntp_hosts`; save/load under the
`p2p/ntp_hosts` QSettings key (`settings/dialog.py::SettingsDialog`); the label comes from
`settings.ntp_hosts` and the tooltip from `tip.ntp_hosts` (all locales). It is
an env-driven setting (no client CLI flag), so `cli_args.py` deliberately does
NOT handle it: the engine injects it as ``HSYNC_NTP_HOSTS`` via
`apply_settings_env` (`engine/process.py::apply_settings_env`, called from `engine/process.py::HsyncEngine.start`). Empty = the
client's built-in defaults.

**Bootnode** (user-facing label **Discovery server**, translated in every
locale — `Server di individuazione`, `Erkennungsserver`, `Serveur de
découverte`, … — `settings.p2p_bootnode`):
`p2p_bootnode` (dynamic `QLineEdit` injected right after the
group row via `_insert_row_after`) + `p2p_bootnode_trust` (`QComboBox`, filled
by `_populate_bootnode_trust`) + `btn_manage_trusted_keys` (`QPushButton`,
opens `TrustedKeysDialog` on the bootnodes tab) + `btn_test_bootnode`
(`QPushButton`, probes the bootnode via `fetch_bootnode_fingerprint`) +
`p2p_upnp` (`ToggleSwitch`), saved/loaded under
`p2p/bootnode` / `p2p/bootnode_trust` / `p2p/upnp_enabled`; labels from
`settings.p2p_bootnode` / `settings.manage_trusted_keys` /
`settings.p2p_bootnode_trust` (+ the four `*_ask`/`*_accept_new`/`*_strict`/
`*_none` option labels) / `settings.p2p_upnp` (all locales); tips from
`tip.p2p_bootnode` (what a bootnode is/does) / `tip.p2p_bootnode_trust` /
`tip.manage_trusted_keys` / `tip.p2p_upnp` / `tip.test_bootnode`, shown per the
`tooltips` preference. The tab is grouped (like the sync tab) into four
`QGroupBox` sections by `_reorganize_p2p_tab`: Mode & Group
(`settings.group.p2p_mode`), Finding devices (`settings.group.p2p_discovery`),
Role & Pairing (`settings.group.p2p_role`) and Advanced Options
(`settings.group.advanced`, shared with the sync tab).
Like NTP hosts this is
env-driven (the client positional exists, but `HSYNC_BOOTNODE` is the documented
equivalent needing no argument plumbing): `apply_settings_env` inserts
`HSYNC_BOOTNODE` (a `HOST[:PORT]` endpoint: `host`, `host:port`, `[IPv6]`,
`[IPv6]:port`), `HSYNC_UPNP_ENABLED` (the user's explicit choice),
and — when a bootnode is set — `HSYNC_BOOTNODE_TRUST` (`ask` / `accept-new` /
`strict` / `none`) for the ADR-0035 trust policy. The bootnode pin itself is not
a GUI setting: it lives in the client's known-hosts store, edited through the
`TrustedKeysDialog` (`trusted_keys.py`) or the pre-flight in
`main_window/trust.py::TrustMixin._ensure_bootnode_trust` (using the
endpoint's real port). The GUI
cannot answer the client's terminal prompt,
so it always sends an explicit policy. Empty bootnode = mDNS-only discovery.
The trust combo and `btn_manage_trusted_keys` follow the panel's gating: both are
disabled when p2p mode is off (server mode) and while a sync is running. The
button opens the dialog on the bootnodes tab; the server panel has its own twin
(`btn_manage_trusted_keys_server`) opening the servers tab, so the two buttons
gate independently. `btn_test_bootnode` (`_on_test_bootnode`) is gated like the
other p2p fields (disabled in server mode and while syncing); it reuses the
`settings.test_connection` label and the existing `settings.invalid_bootnode_endpoint`
key, and reports the bootnode's certificate fingerprint on success.

**Action rows**: each mode panel pairs its two related secondary actions in one
left-aligned horizontal row via `_action_row` (`settings/form_helpers.py::_action_row`) —
the p2p *Manage trusted keys* + *Test connection* (`btn_test_bootnode`), and the
Server twin `btn_manage_trusted_keys_server` + `btn_test_connection`. One row reads
as a group and uses less vertical space than two stacked form rows; the trailing
stretch keeps them left-aligned. Both test buttons carry the
`settings.test_connection` label (set in `_apply_translations`).

**Server**: `server_trust` (`QComboBox`, filled by `_populate_server_trust`,
inserted after the `http_timeout` row), saved/loaded under
`connection/server_trust`; labels from `settings.server_trust` (+ the five
`*_chain`/`*_ask`/`*_accept_new`/`*_strict`/`*_none` option labels), tip from
`tip.server_trust` (all locales). The server pin is not a setting (ADR-0036):
it lives in the client's server known-hosts store. Like the bootnode policy,
the combo is env-driven: `apply_settings_env` always inserts
`HSYNC_SERVER_TRUST` (`chain` default), and `build_hsync_args` emits no
server-trust flag. The server pin is
edited through the `TrustedKeysDialog` Servers tab, the
`_ensure_server_trust` pre-flight in `main_window/trust.py`, or the panel's
`btn_manage_trusted_keys_server` (`QPushButton`, opens the dialog on the servers
tab). Like the other Server fields, the combo and the button are disabled when
p2p mode is active and while a sync is running.

**Log**: `show_log_panel` (toggle), `verbose` (toggle), `logfile` (`QLineEdit`
with a `LblLogfile` label) render in that order; `quiet` is built but hidden
(the desktop parses stdout, so suppressing output is unsupported). Labels from
`settings.show_log_panel` / `settings.verbose` / `settings.logfile` (all locales).
Enabling `verbose` while the log panel is hidden **and** no log file is set
(`settings/dialog.py::SettingsDialog._on_verbose_toggled`) shows a non-blocking
prompt offering to show the panel; "Yes" also checks `show_log_panel`. The option
is not disabled, because a configured log file still captures verbose output. The
signal is connected after `load()`, so a restored `output/verbose=true` never
prompts.

`verbose` maps to the client's `-v` (`settings/cli_args.py::_append_output_args`),
i.e. DEBUG level. `output/logfile` adds `--log-file`: the client mirrors the log
there and keeps its stdout sink, so the panel stays the live view while the file
records the same lines.

Validators for dialog fields: `settings/validators.py` — `_validate_path` (`settings/validators.py::_validate_path`),
`_validate_bucket` (`settings/validators.py::_validate_bucket`), `_validate_group_name`
(`settings/validators.py::_validate_group_name`).

## autostart.py — launch at login (desktop-only)

`appearance/start_at_login` is the General-tab toggle `start_at_login` (built by
`settings/tab_builders.py::build_general_tab`, placed in the General form,
label `settings.start_at_login`, tip `tip.start_at_login`), a desktop-only
preference (no client CLI flag, so `cli_args.py` is not involved). On accept,
`SettingsDialog._apply_start_at_login` (`settings/dialog.py::SettingsDialog._apply_start_at_login`)
reconciles the OS login item through `autostart.py` — `autostart.is_supported`,
`autostart.is_enabled`, `autostart.set_enabled`: a freedesktop XDG entry
(`~/.config/autostart/hsync-desktop.desktop`), a macOS LaunchAgent
(`~/Library/LaunchAgents/io.hsync.desktop.plist`), or the Windows
`HKCU\...\Run` value, each launching `hsync-desktop --minimized`. The command
is resolved by `autostart.py::_launch_command` (`$APPIMAGE` → frozen
`sys.executable` → installed launcher on `PATH` → `python -m hsync_desktop`)
and validated by `autostart.py::_autostart_command` (absolute path, no control
characters); a relative `XDG_CONFIG_HOME` is ignored per spec. On supported
platforms `load()` seeds the toggle from `autostart.is_enabled()` (the on-disk
entry is the source of truth, the QSettings value is a mirror); on `OSError`
the dialog warns (`warn.start_at_login_failed`), restores the toggle to the
real state, and stays open without persisting. On a platform without a
mechanism the toggle is disabled (`tip.start_at_login_unsupported`). The
`--minimized` flag (`config.py::MINIMIZED_FLAG`) is handled at startup by
`main.py::_should_start_minimized` (start hidden only when a tray is
available).

## settings/cli_args.py — config → flags (the contract)

| Symbol | Location | Role |
| ------ | -------- | ---- |
| `build_hsync_args` | `settings/cli_args.py::build_hsync_args` | core translator: QSettings → arg list |
| `secure_config_file` | `settings/cli_args.py::secure_config_file` | restrict the on-disk settings file perms (0600) |
| `get_saved_theme` / `get_theme_setting` / `are_notifications_enabled` / `is_log_panel_visible` / `is_auto_sync_enabled` | `settings/cli_args.py::get_saved_theme` / `settings/cli_args.py::get_theme_setting` / `settings/cli_args.py::are_notifications_enabled` / `settings/cli_args.py::is_log_panel_visible` / `settings/cli_args.py::is_auto_sync_enabled` | desktop-only prefs |
| `get_bandwidth_limits` / `save_bandwidth_limits` | `settings/cli_args.py::get_bandwidth_limits` / `settings/cli_args.py::save_bandwidth_limits` | persisted bandwidth caps (bytes/s in, MB/s out) |

**Bandwidth limits** have two entry points that share one set of values
(`sync/bandwidth_upload` / `sync/bandwidth_download`): the Advanced tab's Network
section and `bandwidth_dialog.py::BandwidthDialog` opened from the status-bar
sent/received labels (`main_window/actions.py::ActionsMixin._show_bandwidth_dialog`).
Both use the same strategy — a `0` field means unlimited (no enable checkbox) —
and the dialog additionally applies the change live through
`engine/process.py::HsyncEngine.set_bandwidth` while a sync runs.

`build_hsync_args` (`settings/cli_args.py::build_hsync_args`) always appends `--allow-deletions` (non-interactive) and
`--color=always` (the client's own palette over the pipe, rendered by the log
panel); the engine appends `--allow-unauthenticated-p2p` for a
keyless p2p run after its own confirmation dialog; emits `--once` when continuous
is off, `--insecure`, `--ignore-delete`, compression flags, the advanced numeric caps (`--min-free-disk-space`,
emitted as a size string such as `500MB`; `--max-inbound-size`), the
Advanced-tab engine knobs (`--no-autotune`,
`--max-concurrent-transfers`, `--no-delta`, `--delta-min-file-size[-p2p]`,
`--no-mass-delete-guard`, `--mass-delete-threshold`, `--mass-delete-percent`),
and the p2p block (the `p2p`/`server` subcommand is the
first token, then `--prefer-master`, `--never-master`, `--require-pairing`,
`--no-peer-download`). Values matching the client default are omitted so the
engine keeps its own default/auto behaviour; the deletion thresholds are always
clamped and emitted.
The peer-download caps (`p2p/peer_read_cap`, `p2p/peer_sources_max`) are env-only
(no CLI flag) and exported by
`engine/process.py::apply_settings_env` as `HSYNC_P2P_PEER_READ_CAP` /
`HSYNC_P2P_PEER_SOURCES_MAX` in p2p mode.
The UPnP toggle is gated on the client's `--upnp` flag (opt-in, enabled by
`--upnp` / `HSYNC_UPNP_ENABLED`; no `--no-upnp` flag exists). A capability-parity test
(`tests/test_cli_args_p2p.py::TestClientCapabilitiesParity`) asserts every
emitted long flag is advertised by the client help output.
One-shot is
expressed via the global `sync/continuous` setting, which maps to
`--once`; **Simulation Mode** (`sync/dry_run`, read through
`cli_args.py::is_simulation_mode`) also forces `--once` alongside `-n`, so the
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
(`settings/dialog.py::SettingsDialog.save`).

> Any new flag here must mirror an option the client actually exposes
> (`hsync-client` [cli-config.md](../../../hsync-client/llm-wiki/modules/cli-config.md))
> and, if it is an `HSYNC_*`/behavior change, the `hsync-client/packaging/wd-os5` web UI.

## crypto.py — secrets at rest

Secrets stored in `QSettings` are Fernet-encrypted with a machine-derived key:
`encrypt_value` (`crypto.py::encrypt_value`) / `decrypt_value` (`crypto.py::decrypt_value`); key derivation
`_derive_key` (`crypto.py::_derive_key`) from `_get_machine_id` (`crypto.py::_get_machine_id`) + `_APP_SALT` (`crypto.py::_APP_SALT`);
stored values carry the `_ENC_PREFIX` (`crypto.py::_ENC_PREFIX`) marker. **Both** the API key
(`connection/api_key`) and the p2p key (`p2p/key`) go through encrypt/decrypt
on save/load (`settings/dialog.py`). `decrypt_value` accepts a plaintext
value (no prefix), so an unencrypted stored p2p key stays readable until the
next save. Plaintext secrets only ever leave via the engine's pipe FDs.

The stored p2p secret is either a shared password (the client derives the group
key) or a raw group key, recorded in `p2p/key_mode`. The dialog persists the
mode it resolves for the current field value (`settings/dialog.py::SettingsDialog._effective_p2p_key_mode`):
an edited field is a password, an untouched one keeps its stored mode normalised
by `engine/process.py::p2p_secret_mode` — a secret shorter than
`hsync_common.protocol.boot_tokens::MIN_GROUP_KEY_CHARS` cannot be a raw key, so
it is stored as `passphrase`. That normalisation is the same one the engine
applies at start, so a legacy short secret stored as `raw` is both repaired on
the next save and accepted by the running engine.

## i18n.py — localization

`tr` (`i18n.py::tr`) looks up keys across all locales (`SUPPORTED_LANGUAGES`, `i18n.py::SUPPORTED_LANGUAGES`,
`en/it/de/es/fr/pt/zh/ru/nl/pl/ja`); `init_language` (`i18n.py::init_language`) / `set_language` (`i18n.py::set_language`) with
`register_language_callback` (`i18n.py::register_language_callback`) for live re-translation. The stored
`appearance/language` preference may be `AUTO_LANGUAGE` (`i18n.py::AUTO_LANGUAGE` = `"auto"`, the
default, shown as **System default** in the General tab): it follows the system locale at
every launch; a supported code pins that language; an absent/unsupported value also
follows the system locale. Every user-facing
string **must** exist in all `hsync_desktop/locales/*.py`.

## Shared endpoint/probe helpers (Settings + wizard)

The server/discovery-server reachability logic is shared so the Settings dialog
and the setup wizard agree:

- `engine/endpoints.py::normalize_server_endpoint` / `normalize_bootnode_endpoint`
  (the GUI default port `SERVER_DEFAULT_PORT` = 9753; the bootnode variant is a
  thin wrapper over the shared `hsync_common.endpoint.normalize_bare_endpoint`,
  the same rule the client's `HSYNC_BOOTNODE` validator applies) and
  `build_probe_ssl_context`; `SettingsDialog._normalize_server_endpoint` /
  `_normalize_bootnode_endpoint` / `_test_connection_ssl_context` delegate to them.
  `_on_accept` still normalizes the fields before `save()`.
- `engine/probes.py::probe_server_health` / `probe_server_bucket` /
  `ServerProbeResult`; the Settings "Test connection" action and the wizard both
  use them (`GET /health`, `GET /api/v1/buckets/{bucket}`).
- `settings/validators.py::validate_sync_folder` / `FolderCheck` back the wizard's
  folder check (existence/type/permission/root error, home/system/low-space
  warning); `FolderCheck.free_bytes` feeds the human-readable free-space display
  (`hsync_common.format.format_bytes`).

The setup wizard writes only a subset of keys; see
[wizard.md](wizard.md) for the mapping and the `wizard/*` draft/draft-encryption.
