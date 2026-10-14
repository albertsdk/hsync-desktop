# HSYNC Desktop — Settings, config & CLI args

How the GUI persists user config and turns it into the binary's command line.

## config.py — defaults + keys

Plain module of `DEFAULT_*` constants and app identity (`config.py`): app/org/id
(`config.py::SETTINGS_ORG`), server defaults (`config.py::DEFAULT_SERVER_TRUST`), sync defaults
(`config.py::DEFAULT_CONTINUOUS`), p2p defaults
(`config.py::DEFAULT_P2P_REQUIRE_PAIRING` and neighbours) and NTP servers
(`config.py::DEFAULT_NTP_HOSTS`). These seed `QSettings` and the dialog.
`DEFAULT_NO_COMPRESSION` (`config.py::DEFAULT_NO_COMPRESSION`) exists only to migrate the legacy key into
`DEFAULT_COMPRESSION_ENABLED` (`config.py::DEFAULT_COMPRESSION_ENABLED`).

## settings/dialog.py — the settings UI

| Symbol | Location | Role |
| ------ | -------- | ---- |
| `SettingsDialog` | `settings/dialog.py::SettingsDialog` | tabs for server/sync/p2p; load/save QSettings |
| `_replace_checkbox_with_toggle` | `settings/dialog.py::_replace_checkbox_with_toggle` | swap checkboxes for `ToggleSwitch` widgets |
| `_maybe_tip` | `settings/dialog.py::_maybe_tip` | attach capability/disabled tooltip |
| `ApiKeyDialog` | `settings/dialog.py::ApiKeyDialog` | enter/replace the server API key (secret) |
| `P2PKeyDialog` | `settings/dialog.py::P2PKeyDialog` | enter/replace the p2p key (secret) |
| `HsyncIgnoreEditorDialog` | `settings/dialog.py::HsyncIgnoreEditorDialog` | edit `.hsyncignore` patterns |

**Capability gating (§8)**: p2p toggles (`p2p_mode`, `force_master`,
`never_master`, `require_pairing`) are disabled + unchecked when the probed
`CapabilitiesDoc` (from `engine.get_binary_capabilities`) lacks the matching CLI
option; the unsupported widgets carry the `tip.capability_unsupported` tooltip.

**Force-master live gate**: `--force-master` is incompatible with a
non-bidirectional direction (it only applies to bidirectional syncs, and is
emitted solely in p2p mode). `SettingsDialog._force_master_conflict`
(`settings/dialog.py::_force_master_conflict`) is True only when all three hold:
direction combo != `bidirectional`, `p2p_mode` on, `force_master` on.
`SettingsDialog._maybe_warn_force_master` (`settings/dialog.py::_maybe_warn_force_master`)
shows a Yes/No prompt whose message depends on the trigger (`**fmt` fills the
localized message placeholders, e.g. the active direction label) and returns
True on "Yes". Three consumers:

* Save gate `SettingsDialog._on_accept` (`settings/dialog.py::_on_accept`):
  `warn.force_master_msg`, "Yes" resets the direction to `bidirectional` and
  continues saving.
* Live direction check `SettingsDialog._on_sync_direction_changed`
  (`settings/dialog.py::_on_sync_direction_changed`, connected in
  `_connect_signals` to `sync_direction_combo.currentIndexChanged` **after**
  `load()` runs, so restoring a saved conflicting state never warns):
  `warn.force_master_disable_msg` offers disabling force-master, "Yes"
  unchecks `force_master` and jumps to the p2p tab (`_P2P_TAB_INDEX`).
* Live toggle check `SettingsDialog._on_force_master_toggled`
  (`settings/dialog.py::_on_force_master_toggled`, fires only when force-master
  is switched **on**): `warn.force_master_sync_msg` names the active direction
  and offers returning to bidirectional, "Yes" resets the direction combo and
  jumps to the sync tab (`_SYNC_TAB_INDEX`).

On "No" from either live check the selection is kept and only the save gate can
prompt again.

All the programmatic `setChecked` fixes above (and the mutual exclusion in
`_on_force_master_toggled` / `_on_never_master_toggled`, and the
ignore-delete restore) deliberately leave the toggle's signals connected:
`ToggleSwitch` paints from a thumb animation driven by `toggled`, so
swallowing the signal with `blockSignals` freezes the switch painted ON
while `checked` is False — the user's click then re-enables it and
re-triggers the prompt in a loop. Covered by
`tests/test_settings_dialog.py::TestForceMasterLiveWarning` and
`tests/test_settings_dialog.py::TestIgnoreDeleteWarning`.

**NTP hosts (ADR-0023)**: `ntp_hosts` (`settings/dialog.py::SettingsDialog`, dynamic widget injected
after the discovery-timeout row) + `_lbl_ntp_hosts`; save/load under the
`p2p/ntp_hosts` QSettings key (`settings/dialog.py::SettingsDialog`); the label comes from
`settings.ntp_hosts` and the tooltip from `tip.ntp_hosts` (all 5 locales). It is
an env-driven setting (no client CLI flag), so `cli_args.py` deliberately does
NOT handle it: the engine injects it as ``HSYNC_NTP_HOSTS`` via
`apply_settings_env` (`engine.py::apply_settings_env`, called from `engine.py::HsyncEngine.start`). Empty = the
client's built-in defaults.

**Bootnode**: `p2p_bootnode` (dynamic `QLineEdit` injected right after the
group row via `_insert_row_after`) + `p2p_bootnode_trust` (`QComboBox`, filled
by `_populate_bootnode_trust`) + `btn_manage_trusted_keys` (`QPushButton`,
opens `TrustedKeysDialog` on the bootnodes tab) + `btn_test_bootnode`
(`QPushButton`, probes the bootnode via `fetch_bootnode_fingerprint`) +
`p2p_upnp` (`ToggleSwitch`), saved/loaded under
`p2p/bootnode` / `p2p/bootnode_trust` / `p2p/upnp_enabled`; labels from
`settings.p2p_bootnode` / `settings.manage_trusted_keys` /
`settings.p2p_bootnode_trust` (+ the four `*_ask`/`*_accept_new`/`*_strict`/
`*_none` option labels) / `settings.p2p_upnp` (5 locales); tips from
`tip.p2p_bootnode` (what a bootnode is/does) / `tip.p2p_bootnode_trust` /
`tip.manage_trusted_keys` / `tip.p2p_upnp` / `tip.test_bootnode`, shown per the
`tooltips` preference.
Like NTP hosts this is
env-driven (the client positional exists, but `HSYNC_BOOTNODE` is the documented
equivalent needing no argument plumbing): `apply_settings_env` inserts
`HSYNC_BOOTNODE` (a `HOST[:PORT]` endpoint: `host`, `host:port`, `[IPv6]`,
`[IPv6]:port`), `HSYNC_UPNP_ENABLED` (the user's explicit choice),
and — when a bootnode is set — `HSYNC_BOOTNODE_TRUST` (`ask` / `accept-new` /
`strict` / `none`) for the ADR-0035 trust policy. The bootnode pin itself is not
a GUI setting: it lives in the client's known-hosts store, edited through the
`TrustedKeysDialog` (`trusted_keys.py`) or the pre-flight in `main_window.py`
(`_ensure_bootnode_trust`, which now uses the endpoint's real port). The GUI
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

**Server**: `server_trust` (`QComboBox`, filled by `_populate_server_trust`,
inserted after the `http_timeout` row), saved/loaded under
`connection/server_trust`; labels from `settings.server_trust` (+ the five
`*_chain`/`*_ask`/`*_accept_new`/`*_strict`/`*_none` option labels), tip from
`tip.server_trust` (5 locales). The old `connection/server_cert_fingerprint`
field was **removed** (ADR-0036): the pin lives in the client's server
known-hosts store, not in a setting. Like the bootnode policy, the combo is
env-driven: `apply_settings_env` always inserts `HSYNC_SERVER_TRUST` (`chain`
default), and `build_hsync_args` emits no server-trust flag. The server pin is
edited through the `TrustedKeysDialog` Servers tab, the
`_ensure_server_trust` pre-flight in `main_window.py`, or the panel's
`btn_manage_trusted_keys_server` (`QPushButton`, opens the dialog on the servers
tab). Like the other Server fields, the combo and the button are disabled when
p2p mode is active and while a sync is running.

**Log**: `show_log_panel` (toggle), `verbose` (toggle), `logfile` (`QLineEdit`
with a `LblLogfile` label) render in that order; `quiet` is built but hidden
(the desktop parses stdout, so suppressing output is unsupported). Labels from
`settings.show_log_panel` / `settings.verbose` / `settings.logfile` (5 locales).

Validators for dialog fields: `settings/validators.py` — `_validate_path` (`settings/validators.py::_validate_path`),
`_validate_bucket` (`settings/validators.py::_validate_bucket`), `_validate_group_name`
(`settings/validators.py::_validate_group_name`).

## settings/cli_args.py — config → flags (the contract)

| Symbol | Location | Role |
| ------ | -------- | ---- |
| `build_hsync_args` | `settings/cli_args.py::build_hsync_args` | core translator: QSettings → arg list |
| `secure_config_file` | `settings/cli_args.py::secure_config_file` | restrict the on-disk settings file perms (0600) |
| `get_saved_theme` / `are_notifications_enabled` / `is_log_panel_visible` / `is_auto_sync_enabled` | `settings/cli_args.py::get_saved_theme` / `settings/cli_args.py::are_notifications_enabled` / `settings/cli_args.py::is_log_panel_visible` / `settings/cli_args.py::is_auto_sync_enabled` | desktop-only prefs |
| `get_bandwidth_limits` / `save_bandwidth_limits` | `settings/cli_args.py::get_bandwidth_limits` / `settings/cli_args.py::save_bandwidth_limits` | persisted bandwidth caps |

`build_hsync_args` (`settings/cli_args.py::build_hsync_args`) always appends `--allow-deletions` (non-interactive) and
`--no-color`; the engine appends `--allow-unauthenticated-p2p` for a
keyless p2p run after its own confirmation dialog; emits `--once` when continuous
is off, `--insecure`, `--ignore-delete`, compression flags, the advanced numeric caps (`--min-free-disk-space`,
`--max-inbound-size`), and the p2p block (the `p2p`/`server` subcommand is the
first token, then `--force-master`, `--never-master`, `--require-pairing`).
The UPnP toggle is gated on the client's `--upnp` flag (opt-in since 1.0.3;
the old `--no-upnp` no longer exists). A capability-parity test
(`tests/test_cli_args_p2p.py::TestClientCapabilitiesParity`) asserts every
emitted long flag is advertised by the client help output.
One-shot is
expressed only via the global `sync/continuous` setting, which maps to
`--once`. Secrets are
**not** here — they go through engine pipe FDs.

> Any new flag here must mirror an option the client actually exposes
> (`hsync-client` [cli-config.md](../../../hsync-client/llm-wiki/modules/cli-config.md))
> and, if it is an `HSYNC_*`/behavior change, the `packaging/wd-os5` web UI.

## crypto.py — secrets at rest

Secrets stored in `QSettings` are Fernet-encrypted with a machine-derived key:
`encrypt_value` (`crypto.py::encrypt_value`) / `decrypt_value` (`crypto.py::decrypt_value`); key derivation
`_derive_key` (`crypto.py::_derive_key`) from `_get_machine_id` (`crypto.py::_get_machine_id`) + `_APP_SALT` (`crypto.py::_APP_SALT`);
stored values carry the `_ENC_PREFIX` (`crypto.py::_ENC_PREFIX`) marker. **Both** the API key
(`connection/api_key`) and the p2p key (`p2p/key`) go through encrypt/decrypt
on save/load (`dialog.py`). `decrypt_value` still accepts a legacy plaintext
value (no prefix) so an existing unencrypted p2p key is readable until the
next save. Plaintext secrets only ever leave via the engine's pipe FDs.

## i18n.py — localization

`tr` (`i18n.py::tr`) looks up keys across 5 locales (`SUPPORTED_LANGUAGES`, `i18n.py::SUPPORTED_LANGUAGES`,
`en/it/de/es/fr`); `init_language` (`i18n.py::init_language`) / `set_language` (`i18n.py::set_language`) with
`register_language_callback` (`i18n.py::register_language_callback`) for live re-translation. Every user-facing
string **must** exist in all five `locales/*.py`.
