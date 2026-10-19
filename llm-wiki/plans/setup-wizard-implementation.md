# HSYNC Desktop — Setup Wizard Implementation Plan

**Status:** implemented (see [modules/wizard.md](../modules/wizard.md))
**Scope:** `hsync-desktop` only (no change to `hsync-client`, `hsync-server`, `hsync-common`, `hsync-android`, `hsync-bootnode`)
**Revision:** v6 (restructured to an ordered task list; decisions unchanged from v5 — see Appendix D)
**Canonical target:** `hsync-desktop/llm-wiki/plans/setup-wizard-implementation.md` (this file).

---

## 1. Goal and scope

Add a guided setup wizard to HSYNC Desktop (PySide6) so a non-technical user can
configure one of four use cases in **4 steps + a success screen**. It opens once
on first run and stays reachable from the menu, the tray, and the
unconfigured-folder placeholder. It writes only a subset of QSettings and never
changes protocol, CLI flags, env vars, or server API.

Out of scope: replacing Settings; scheduled backups; the Android wizard;
new dependencies; a "differences-only" review (deferred to v2).

---

## 2. Decisions (resolved)

### 2.1 Four modes

| ID | Title (EN / IT) | Mapping |
| -- | --------------- | ------- |
| `backup` | Back up my files / "Metto al sicuro i miei file" | server mode, `upload-only`, `ignore_delete=true` |
| `lan_sync` | Sync devices on the same network / "Sincronizzo i dispositivi sulla stessa rete" | p2p, mDNS, `bidirectional` (or `download-only`), no relay |
| `remote_sync` | Sync devices from anywhere / "Sincronizzo i dispositivi ovunque" | p2p + relay, `bidirectional` (or `download-only`) |
| `team_share` | Share a folder with my team / "Condivido una cartella con il mio team" | server mode, `bidirectional` \| `upload-only` \| `download-only` |

### 2.2 Smart defaults

| Mode | `p2p/enabled` | direction | `ignore_delete` | `continuous` | `auto_sync` | `start_at_login` | relay | trust |
| ---- | --- | --- | --- | --- | --- | --- | --- | --- |
| backup | false | `upload-only` | true | true | true | true | — | `chain` (or `ask`+pin if non-standard cert) |
| lan_sync | true | `bidirectional` | false | true | true | false | empty | — |
| remote_sync | true | `bidirectional` | false | true | true | false | required | `ask` |
| team_share | false | user choice | false | true | true | false | — | `chain` (or `ask`+pin if non-standard cert) |

Rules: first run applies these; re-run prefills current values; never touch keys
outside the mapping (Appendix A). Derived names are sanitized so they always pass
`is_valid_bucket_name` (share) / `_validate_group_name` (group); fallback
`hsync-<short-random>`. Generated shared password ≥ 20 chars, unambiguous
alphabet, regenerable.

### 2.3 Trust: unified TOFU + pin (relay and server)

- Policy `ask`; the pin lives in the client known-hosts store, **not** QSettings.
- "Trust … and save" → `add_bootnode_trust` / `add_server_trust` (store-hit
  short-circuits the later pre-flight); "Ask on first start" → policy `ask`, no
  pin (existing `TrustMixin._confirm_host_trust` prompts once).
- Never `strict` (unrecoverable on cert rotation) and never `accept-new` (silent
  first-use trust).
- A failed pin write (or missing binary) blocks **Finish setup** with an inline
  error and a "skip pinning" escape.

### 2.4 Mode inference (re-run preselect) — `infer_mode_from_settings`

| Condition | Mode |
| --------- | ---- |
| `p2p/enabled` false and `sync/direction` == `upload-only` | `backup` |
| `p2p/enabled` false otherwise | `team_share` |
| `p2p/enabled` true and `p2p/bootnode` non-empty | `remote_sync` |
| `p2p/enabled` true and `p2p/bootnode` empty | `lan_sync` |
| no `path/local` (first run) | none (user chooses) |

Preselection only; differing flags are shown as editable differences in the
review. Warn only on an incoherent state (e.g. server mode with empty
`connection/server_url`).

### 2.5 Server probe (mode-aware)

`GET /health` (all server modes) + `GET /api/v1/buckets/{bucket}` with
`Authorization: Bearer <key>` (the only non-admin authenticated call, so it also
verifies the key). Uses `urllib.request` + `build_probe_ssl_context`; timeout
`max(5, connection/http_timeout)`; async worker.

Statuses (from `hsync-server/hsync_server/api/buckets.py::get_bucket` and
`hsync-server/hsync_server/api/authz.py`):
200 ok; 400 bad name; 401 bad/missing key (403 empty credentials); 404 =
missing **or** no access (indistinguishable by design); 5xx error.

- `backup`: 404 is **benign** — the share is auto-created on first upload
  (`hsync-server/hsync_server/api/authz.py::ensure_bucket_access`, caller becomes owner).
- `team_share`: 404 **blocks Finish** (starting a team sync would auto-create a
  private empty share owned by this account).
- Other probe failures are advisory with an explicit "continue without
  verification".

Relay probe: `fetch_bootnode_fingerprint(binary, host, port or 443)`; if the
binary is missing, report it (no fake test). LAN: no pre-start test (honest
message).

### 2.6 Endpoints

The wizard stores normalized values (`https://host:9753` for the server;
`host`/`[v6]:port` for the relay). `SettingsDialog._on_accept` already normalizes
both fields before `save()`, so Settings stores canonical values today; the
shared refactor must preserve that (no behaviour change) and switch
`_on_test_connection` from the hardcoded `"/health"` to `REST_HEALTH_PATH`.

### 2.7 Persistence, first run, entry points

- Draft under `wizard/*` (Appendix A), debounced save, resume at `last_step`,
  secrets Fernet-encrypted, file kept `0600` by `secure_config_file`.
- Auto-open once when `wizard/auto_shown` is absent and `path/local` is empty;
  configured installs are treated as onboarded (no popup).
- Hook on the splash path only (`main.py::main`): a dedicated
  `_reveal_after_splash()` calls `activate_window()` then
  `window.maybe_show_setup_wizard()`. Never reuse the shared `activate_window`
  (also wired to `single_instance.activate_requested`). `--minimized` skips the
  splash, so the hook never fires.
- Menu action "Setup wizard…" next to Settings; matching tray entry; the
  unconfigured-folder placeholder opens the wizard when `self._local_path` is
  empty.

### 2.8 i18n

Add `wizard.*` and `menu.setup_wizard` to all 11 locales atomically
(`test_locales.py::TestTranslationConsistency` requires identical key sets).
Reuse generic keys (`action.cancel/close/yes/no`) and existing `settings.*`
labels. Extend `TestTerminologyConsistency`: no "master"/"bootnode", "relay
server", "shared password". Register a language-change callback for live
retranslation.

---

## 3. Verified code anchors

| Need | Anchor |
| ---- | ------ |
| Settings keys / app/org | `settings/cli_args.py::build_hsync_args`, `SETTINGS_APP`, `SETTINGS_ORG` |
| Env/secret channel | `engine/process.py::apply_settings_env` (`HSYNC_SERVER`, `HSYNC_BOOTNODE`, `HSYNC_SERVER_TRUST`, `HSYNC_BOOTNODE_TRUST`; secrets via pipe FDs) |
| Crypto / perms | `crypto.py::encrypt_value`/`decrypt_value`; `settings/cli_args.py::secure_config_file` |
| Server test (to extract) | `settings/dialog.py::SettingsDialog._on_test_connection`, `_test_connection_ssl_context`, `_unverified_ssl_context`, `_normalize_server_endpoint`, `_normalize_bootnode_endpoint` |
| Endpoint normalization on save | `settings/dialog.py::SettingsDialog._on_accept` (normalizes fields before `save()`) |
| Endpoint grammar / REST paths | `hsync_common.endpoint::parse_host_port`/`build_https_url`/`parse_https_url`/`format_authority`; `hsync_common.protocol.rest::REST_HEALTH_PATH` (`"/health"`), `REST_BUCKET_PATH_TEMPLATE` |
| Server default port | `engine/endpoints.py::SERVER_DEFAULT_PORT` = `9753` (also used in `main_window/trust.py`) |
| Relay probe / trust fns | `engine/cli.py::find_hsync_binary`, `fetch_bootnode_fingerprint`, `list_*_trust`, `add_*_trust`; `main_window/trust.py::TrustMixin._confirm_host_trust`, `_ensure_server_trust`, `_ensure_bootnode_trust` |
| Validators | `settings/validators.py::_validate_path`/`_validate_bucket`/`_validate_group_name`; `hsync_common.path_validation::is_valid_bucket_name` (`MAX_BUCKET_NAME_LENGTH=63`), `safe_resolve_path` |
| Masked secrets precedent | `settings/credential_dialogs.py::ApiKeyDialog`, `P2PKeyDialog` |
| Autostart | `autostart.py::is_supported`, `set_enabled` (raises `OSError`) |
| Server bucket semantics | `hsync-server/hsync_server/api/buckets.py::get_bucket`, `hsync-server/hsync_server/api/authz.py::check_bucket_access`/`ensure_bucket_access`, `hsync-server/hsync_server/api/files/upload.py::upload_file`, `hsync-server/hsync_server/auth.py::verify_api_key` |
| Startup / placeholder / menu | `main.py::main`; `main_window/start.py::StartMixin._open_settings`/`_on_path_clicked`/`_check_auto_sync`; `main_window/ui.py::UiBuildMixin._create_menu_bar`/`_load_ui`; `main_window/window.py::MainWindow.__init__` |
| Workers pattern | `file_panel/workers.py::DirectoryScanWorker`, `file_panel/panel.py` (QThread + moveToThread) |
| Theme | `themes.py::_COMMON_QSS` already styles `QPushButton#primaryButton` |

---

## 4. UX contract

- **Shell:** custom `QDialog` + `QStackedWidget`, stepper "Purpose, Folder,
  Connection, Review" with a visible "Step N of 4"; success screen is not a 5th
  step. Back/Continue/Finish, top-right X (keeps draft), Skip only where optional.
- **Step 1 Purpose:** four radio cards (icon/title/description/needs), a "Help me
  choose" mini-panel (same network? copy-only? → mode), Continue disabled until a
  card is picked.
- **Step 2 Folder:** path + Browse + suggestions (Documents, Pictures, create
  `~/HSYNC`) + free space; inline validation (empty, missing, file, permission,
  `/` block, home/system warning, low-space warning).
- **Step 3 Connection:** per-mode section (2.2/2.5) + optional automation block
  (real-time, auto-sync, launch-at-login; "Skip and use recommended values").
- **Step 4 Review:** mode, folder, connection (secrets masked), behaviour, checks;
  Edit links; apply only on "Finish setup".
- **Success:** confirmation, "Start syncing" / "Go to the main window", and a
  copyable p2p invite (group + password).
- **Accessibility:** keyboard-complete, real `QRadioButton` cards with accessible
  names, errors tied to fields, colour never the sole signal, light/dark + HiDPI.

---

## 5. Ordered task list

### Phase 1 — shared refactors (behaviour-preserving)

1. `engine/endpoints.py`: `SERVER_DEFAULT_PORT`, `normalize_server_endpoint`,
   `normalize_bootnode_endpoint`, `build_probe_ssl_context`.
2. `engine/probes.py`: `ServerProbeResult`, `probe_server_health`,
   `probe_server_bucket`, `probe_bootnode`.
3. Refactor `SettingsDialog` to use them; keep `_on_accept` normalize-before-save;
   use `REST_HEALTH_PATH`; delete the duplicated helpers.
4. `main_window/start.py::StartMixin`: extract `_apply_settings_changes()` from
   `_open_settings` (theme, icons, notifier, log visibility, reload path/files,
   path display).
5. `settings/validators.py::validate_sync_folder(path)`.
6. `themes.py`: inline-error style (reuse `#primaryButton`).
7. Update existing tests for the new patch targets; run the full suite + ruff +
   mypy → green.

### Phase 2 — model, defaults, validation, persistence

8. `wizard/model.py`: modes/profiles, `infer_mode_from_settings`,
   `should_auto_open`, `WizardDraft` + versioning.
9. `wizard/defaults.py`: sanitized `default_share_name`/`generate_group_name`,
   `generate_password`, folder suggestions.
10. `wizard/validation.py`: field validators + messages.
11. `wizard/apply.py`: QSettings mapping (Appendix A), encryption, autostart,
    `pin_host_trust` (structured result so the dialog can block/offer skip).
12. Unit tests for 8–11.

### Phase 3 — wizard UI

13. `wizard/widgets.py`, `wizard/stepper.py`.
14. `wizard/pages/{mode,folder,connection,review,success}.py`.
15. `wizard/dialog.py`: navigation, validation gating, draft autosave, language
    callback, `applied`/`start_requested` result.
16. `wizard/probes.py`: QThread worker (DirectoryScanWorker pattern), signature +
    generation counter, cancel, status states.
17. pytest-qt tests: navigation, branching, inline errors, resume, review masking,
    success.

### Phase 4 — MainWindow integration

18. Menu action in `ui.py::_create_menu_bar`; `start.py::_open_setup_wizard`
    (single instance/re-raise; stop-prompt → `_on_stop()`; on applied
    `_apply_settings_changes()`; after close, if `start_requested` call
    `_on_start()`).
19. Splash hook `_reveal_after_splash()` in `main.py`; `maybe_show_setup_wizard`;
    auto-sync guard/reschedule in `window.py::MainWindow.__init__` +
    `start.py::_check_auto_sync`.
20. Placeholder routing in `_on_path_clicked` when `_local_path` is empty.
21. Tray entry (`system_tray.py::SystemTray` + `main.py` wiring).
22. Extend `tests/test_main_window.py`; full suite green.

### Phase 5 — i18n

23. Add wizard keys to the 11 locales; extend terminology tests; check long
    strings/wrap/scroll; `test_locales.py` green.

### Phase 6 — documentation

24. `llm-wiki/modules/wizard.md` + update index/architecture/data-models/
    decisions/settings/ui pages; `docs/setup-wizard.md` + getting-started/
    configuration/usage/README links. `CHANGELOG.md`: only if the user asks.

### Phase 7 — verification

25. Full suite, ruff, mypy, manual smoke test (4 modes, invalid inputs, resume,
    masking, refresh, start), themes/locales; review `git status`/`git diff`; one
    commit in `hsync-desktop`.

---

## 6. Test plan

| File | Focus |
| ---- | ----- |
| `tests/test_wizard_model.py` | modes, inference, defaults, `should_auto_open`, draft round-trip/version |
| `tests/test_wizard_validation.py` | folder, URL, key, bucket, group, password, direction |
| `tests/test_wizard_apply.py` | per-mode mapping, untouched keys, encryption, autostart fake, relay cleared for non-remote, trust pin (hit/write/fail→block+skip) |
| `tests/test_wizard_probes.py` | 200/400/401/403/404/5xx/timeout/SSL, no network; mode-aware 404; relay fingerprint |
| `tests/test_wizard_ui.py` | navigation, branch, inline errors, skip, resume, masked review, success, start |
| `tests/test_main_window.py` | menu, single instance, stop prompt, refresh, first-run splash path, no popup when configured, auto-sync, placeholder |

Infra: patch `hsync_desktop.wizard.apply.autostart` in `conftest.py::fake_autostart`;
add `_blank_settings` to `tests/_helpers.py`; inject `QSettings` into
`SetupWizard`; patch probes and `QFileDialog.getExistingDirectory`; no real
network/autostart/user config.

---

## 7. Validation commands

```bash
cd hsync-desktop && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_wizard_model.py tests/test_wizard_validation.py tests/test_wizard_apply.py tests/test_wizard_probes.py
cd hsync-desktop && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_wizard_ui.py tests/test_main_window.py
cd hsync-desktop && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
cd hsync-desktop && .venv/bin/python -m ruff check . && .venv/bin/python -m mypy hsync_desktop
```

Manual: clear `wizard/*` + `path/local` in an isolated QSettings, launch with a
display, exercise the four modes, invalid folder/server/key/bucket/relay, resume,
masking, refresh, start, light/dark, a long locale. No Android/Rust commands.

---

## 8. Risks

| Risk | Mitigation |
| ---- | ---------- |
| ~80–120 new strings × 11 locales | reuse existing keys; key-set equality test; long-string check |
| Draft secrets at rest | Fernet-encrypt; `0600`; clear on finish; blank if decrypt fails |
| Network probes / 404 ambiguity | async worker; mode-aware 404 (backup benign, team blocks); advisory + explicit continue; actionable messages |
| Trust pinning | TOFU+pin; never `strict`/`accept-new`; failed pin blocks Finish with "skip pinning"; reuse `_confirm_host_trust` |
| Autostart failure | reuse Settings handling; inline error; option can be disabled |
| Sync running while reconfiguring | stop prompt; never change live settings silently |
| Dangerous folders | hard block `/`; warn + confirm for home/system |
| Stale probe results | signature + generation counter |
| First-run popup / second-instance | `auto_shown` + path check; hook on `splash.finished` only |
| Long translations | wrap, scroll area, min widths |

---

## 9. Out of scope / deferred

- Settings refactor beyond the shared endpoint/probe helper extraction.
- Review showing only the diffs from current values (deferred to v2).
- Scheduled/one-shot backup, exclusions, bandwidth, advanced tuning (remain in
  Settings).
- Android wizard alignment.

---

## Appendix A — QSettings mapping

| Wizard field | Key | Notes |
| ------------ | --- | ----- |
| Local folder | `path/local` | validated |
| Share name | `sync/bucket` | `is_valid_bucket_name` |
| Server address | `connection/server_url` | normalized HTTPS URL (env `HSYNC_SERVER`) |
| API key | `connection/api_key` | encrypted; pipe FD |
| Accept server cert | `connection/server_trust` | `ask` only if opted in (pin via `add_server_trust`); else untouched (`chain`) |
| p2p enabled | `p2p/enabled` | derived from mode |
| Group | `p2p/group` | p2p modes only |
| Shared password | `p2p/key` | encrypted; pipe FD |
| Relay | `p2p/bootnode` | `remote_sync` only; cleared for every other mode |
| Relay trust | `p2p/bootnode_trust` | `ask`; pin via `add_bootnode_trust` |
| Direction | `sync/direction` | `bidirectional`/`upload-only`/`download-only` |
| Keep deleted | `sync/ignore_delete` | backup only |
| Real-time | `sync/continuous` | default true; false → `--once` |
| Auto-sync | `sync/auto_sync` | default true in the wizard |
| Launch at login | `appearance/start_at_login` | + `autostart.set_enabled` |
| Draft / state | `wizard/auto_shown`, `wizard/completed`, `wizard/version`, `wizard/in_progress`, `wizard/last_step`, `wizard/mode`, `wizard/draft/*` | draft secrets encrypted |

Never touched: `advanced/*`, `sync/resync`, `connection/ca_cert`,
`connection/insecure`, `output/*`, `ui/show_advanced`, `p2p/upnp_enabled`,
`p2p/ntp_hosts`, `p2p/port`, `p2p/prefer_master`, `p2p/never_master`,
`p2p/require_pairing`, `p2p/peer_*`.

## Appendix B — i18n groups

`wizard.title/subtitle`, `wizard.step.{mode,folder,connection,review}`,
`wizard.step_counter`, `wizard.mode.<id>.{title,description,needs}`,
`wizard.why.*`, `wizard.folder.*`, `wizard.connection.*`, `wizard.automation.*`,
`wizard.review.*`, `wizard.success.*`, `wizard.action.{later,start_over,continue,back,finish,skip}`,
`menu.setup_wizard`.

## Appendix C — file inventory

**New:** `hsync_desktop/wizard/` (model, defaults, validation, apply, probes,
stepper, widgets, pages/*, dialog); `hsync_desktop/engine/endpoints.py`,
`hsync_desktop/engine/probes.py`; `tests/test_wizard_{model,validation,apply,probes,ui}.py`;
`llm-wiki/modules/wizard.md`; `docs/setup-wizard.md`; optional
`resources/icons/network-relay.svg`.

**Modified:** `settings/dialog.py`, `settings/validators.py`, `main_window/ui.py`,
`main_window/start.py`, `main_window/window.py`, `main.py`, `system_tray.py`,
`themes.py`, `locales/*.py` (11), `tests/conftest.py`, `tests/_helpers.py`,
`tests/test_locales.py`, `tests/test_main_window.py`, and the `llm-wiki/`/`docs/`
pages listed in task 24.

## Appendix D — verification notes (corrections applied across revisions)

- Wizard MainWindow methods live in `main_window/start.py::StartMixin`, not
  `actions.py`.
- First-run hook on `splash.finished` via `_reveal_after_splash`; never the shared
  `activate_window`.
- `themes.py` already styles `#primaryButton`; only inline-error is new.
- "Unconfigured" = empty `self._local_path`.
- Trust unified on TOFU+pin with policy `ask` (no `strict`/`accept-new`).
- `SettingsDialog._on_accept` already normalizes endpoints before `save()`, so no
  Settings save change; the refactor must preserve it.
- Server semantics confirmed by code: `ensure_bucket_access` **auto-creates** the
  bucket on first upload; `get_bucket` returns 404 for missing **or** no-access,
  400 bad name, 401 bad key (no 403 for missing permission). Probe is mode-aware.
- Mode inference is a deterministic preselection on distinctive traits.
- `p2p/bootnode` cleared for all non-remote modes.
- Docs: plan target is `llm-wiki/plans/setup-wizard-implementation.md`; a stray
  duplicate exists at `/home/albertobasso/Projects/mastervoice/piano implementazione`.
