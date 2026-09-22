# HSYNC Desktop — Settings, config & CLI args

How the GUI persists user config and turns it into the binary's command line.

## config.py — defaults + keys

Plain module of `DEFAULT_*` constants and app identity (`config.py`): app/org/id
(`:17`–`:24`), server defaults (`:27`–`:35`), sync defaults (`:38`–`:52`), LAN
defaults (`:55`–`:63`, incl. `DEFAULT_LAN_REQUIRE_PAIRING:62` and
`DEFAULT_NTP_HOSTS:63`). These seed `QSettings` and the dialog.
`DEFAULT_NO_COMPRESSION` (`:46`) exists only to migrate the legacy key into
`DEFAULT_COMPRESSION_ENABLED` (`:47`).

## settings/dialog.py — the settings UI

| Symbol | Line | Role |
| ------ | ---- | ---- |
| `SettingsDialog` | `dialog.py:162` | tabs for server/sync/LAN; load/save QSettings |
| `_replace_checkbox_with_toggle` | `:104` | swap checkboxes for `ToggleSwitch` widgets |
| `_maybe_tip` | `:99` | attach capability/disabled tooltip |
| `ApiKeyDialog` | `:1201` | enter/replace the server API key (secret) |
| `P2pKeyDialog` | `:1270` | enter/replace the p2p key (secret) |
| `HsyncIgnoreEditorDialog` | `:1338` | edit `.hsyncignore` patterns |

**Capability gating (§8)**: p2p toggles (`p2p_mode`, `force_master`,
`never_master`, `require_pairing`) are disabled + unchecked when the probed
`CapabilitiesDoc` (from `engine.get_binary_capabilities`) lacks the matching CLI
option; the unsupported widgets carry the `tip.capability_unsupported` tooltip.

**NTP hosts (ADR-0023)**: `ntp_hosts` (`dialog.py:297`, dynamic widget injected
after the discovery-timeout row) + `_lbl_ntp_hosts`; save/load under the
`p2p/ntp_hosts` QSettings key (`:1024` / `:1107`); the label comes from
`settings.ntp_hosts` and the tooltip from `tip.ntp_hosts` (all 5 locales). It is
an env-driven setting (no client CLI flag), so `cli_args.py` deliberately does
NOT handle it: the engine injects it as ``HSYNC_NTP_HOSTS`` via
`apply_settings_env` (`engine.py:99`, called at `engine.py:328`). Empty = the
client's built-in defaults.

**Bootnode (C2)**: `p2p_bootnode` (dynamic `QLineEdit` injected right after the
group row via `_insert_row_after`) + `p2p_upnp` (`ToggleSwitch`), saved/loaded
under `p2p/bootnode` / `p2p/upnp_enabled`; labels from `settings.p2p_bootnode` /
`settings.p2p_upnp` (5 locales). Like NTP hosts this is env-driven (the client
positional exists, but `HSYNC_BOOTNODE` is the documented equivalent needing no
argument plumbing): `apply_settings_env` inserts `HSYNC_BOOTNODE` (bare host)
and `HSYNC_UPNP_ENABLED` (the user's explicit choice) only when a bootnode is
set. Empty bootnode = mDNS-only discovery.

Validators for dialog fields: `settings/validators.py` — `_validate_path` (`:21`),
`_validate_bucket` (`:34`), `_validate_url` (`:52`), `_validate_group_name`
(`:71`).

## settings/cli_args.py — config → flags (the contract)

| Symbol | Line | Role |
| ------ | ---- | ---- |
| `build_hsync_args` | `cli_args.py:62` | core translator: QSettings → arg list |
| `secure_config_file` | `:31` | restrict the on-disk settings file perms (0600) |
| `get_saved_theme` / `are_notifications_enabled` / `is_log_panel_visible` / `is_auto_sync_enabled` | `:247`–`:267` | desktop-only prefs |
| `get_bandwidth_limits` / `save_bandwidth_limits` | `:273` / `:310` | persisted bandwidth caps |

`build_hsync_args` always appends `--yes` (`:227`, non-interactive) and
`--no-color` (`:233`); emits `--once` when continuous is off (`:122`),
`--insecure` (`:105`),
`--ignore-delete` (`:152`), compression flags
(`:184`/`:186`), the advanced numeric caps (`--min-free-disk-space`,
`--max-inbound-size`), and the p2p block (the `p2p`/`server` subcommand is the
first token, then `--force-master`, `--never-master`, `--require-pairing`).
One-shot is
expressed only via the global `sync/continuous` setting, which maps to
`--once` (`:124`). Secrets are
**not** here — they go through engine pipe FDs.

> Any new flag here must mirror an option the client actually exposes
> (`hsync-client` [cli-config.md](../../../hsync-client/llm-wiki/modules/cli-config.md))
> and, if it is an `HSYNC_*`/behavior change, the `packaging/wd-os5` web UI.

## crypto.py — secrets at rest

Secrets stored in `QSettings` are Fernet-encrypted with a machine-derived key:
`encrypt_value` (`crypto.py:110`) / `decrypt_value` (`:118`); key derivation
`_derive_key` (`:86`) from `_get_machine_id` (`:40`) + `_APP_SALT` (`:33`);
stored values carry the `_ENC_PREFIX` (`:37`) marker. **Both** the API key
(`connection/api_key`) and the p2p key (`p2p/key`) go through encrypt/decrypt
on save/load (`dialog.py`). `decrypt_value` still accepts a legacy plaintext
value (no prefix) so an existing unencrypted p2p key is readable until the
next save. Plaintext secrets only ever leave via the engine's pipe FDs.

## i18n.py — localization

`tr` (`i18n.py:94`) looks up keys across 5 locales (`SUPPORTED_LANGUAGES:33`,
`en/it/de/es/fr`); `init_language` (`:57`) / `set_language` (`:68`) with
`register_language_callback` (`:88`) for live re-translation. Every user-facing
string **must** exist in all five `locales/*.py`.
