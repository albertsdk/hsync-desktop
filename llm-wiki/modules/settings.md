# hsync-desktop — Settings, config & CLI args

How the GUI persists user config and turns it into the binary's command line.

## config.py — defaults + keys

Plain module of `DEFAULT_*` constants and app identity (`config.py`): app/org/id
(`:17`–`:24`), server defaults (`:27`–`:35`), sync defaults (`:38`–`:52`), LAN
defaults (`:55`–`:62`, incl. `DEFAULT_LAN_REQUIRE_PAIRING:62`). These seed
`QSettings` and the dialog. `DEFAULT_NO_COMPRESSION` (`:46`) exists only to
migrate the legacy key into `DEFAULT_COMPRESSION_ENABLED` (`:47`).

## settings/dialog.py — the settings UI

| Symbol | Line | Role |
| ------ | ---- | ---- |
| `SettingsDialog` | `dialog.py:162` | tabs for server/sync/LAN; load/save QSettings |
| `_replace_checkbox_with_toggle` | `:104` | swap checkboxes for `ToggleSwitch` widgets |
| `_maybe_tip` | `:99` | attach capability/disabled tooltip |
| `ApiKeyDialog` | `:1201` | enter/replace the server API key (secret) |
| `LanKeyDialog` | `:1270` | enter/replace the LAN key (secret) |
| `HsyncIgnoreEditorDialog` | `:1338` | edit `.hsyncignore` patterns |

**Capability gating (§8)**: LAN toggles (`lan_mode`, `force_master`,
`never_master`, `require_pairing`) are disabled + unchecked when the probed
`CapabilitiesDoc` (from `engine.get_binary_capabilities`) lacks the matching CLI
option; the unsupported widgets carry the `tip.capability_unsupported` tooltip.

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
`--no-color` (`:233`); emits `-w` watch (`:122`), `--insecure` (`:105`),
`--ignore-delete` (`:152`), compression flags
(`:184`/`:186`), the advanced numeric caps (`--min-free-disk-space`,
`--max-inbound-size`), and the LAN block (`--lan-mode:190`,
`--no-lan-persistent:210`, `--force-master:212`, `--never-master:214`,
`--require-pairing:216`). Secrets are
**not** here — they go through engine pipe FDs.

> Any new flag here must mirror an option the client actually exposes
> (`hsync-client` [cli-config.md](../../../hsync-client/llm-wiki/modules/cli-config.md))
> and, if it is an `HSYNC_*`/behavior change, the `packaging/wd-os5` web UI.

## crypto.py — secrets at rest

Secrets stored in `QSettings` are Fernet-encrypted with a machine-derived key:
`encrypt_value` (`crypto.py:110`) / `decrypt_value` (`:118`); key derivation
`_derive_key` (`:86`) from `_get_machine_id` (`:40`) + `_APP_SALT` (`:33`);
stored values carry the `_ENC_PREFIX` (`:37`) marker. Plaintext secrets only ever
leave via the engine's pipe FDs.

## i18n.py — localization

`tr` (`i18n.py:94`) looks up keys across 5 locales (`SUPPORTED_LANGUAGES:33`,
`en/it/de/es/fr`); `init_language` (`:57`) / `set_language` (`:68`) with
`register_language_callback` (`:88`) for live re-translation. Every user-facing
string **must** exist in all five `locales/*.py`.
