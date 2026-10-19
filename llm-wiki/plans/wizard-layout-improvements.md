# HSYNC Desktop — Setup wizard layout & UX improvements

**Status:** implemented (see [modules/wizard.md](../modules/wizard.md))
**Scope:** `hsync-desktop`, setup wizard UI only (`hsync_desktop/wizard/`, `themes.py`, `icons.py`)
**Plan file:** this file

## Goal

Raise the wizard from "functionally complete" to a polished, accessible,
i18n-safe assistant: honest status information, clear visual hierarchy, an
obvious selected state on the mode cards, predictable connection layouts, a
selectable invite, and consistent spacing — without changing the configuration
contract or adding dependencies.

## Non-goals

- No changes to the client/protocol or to the Settings dialog.
- No new UX flows or steps (still 4 steps + success).
- No new third-party dependency.

## Design principles (best practices applied)

1. **Honest state**: the review must never claim "Not verified" when a check
   succeeded (or vice versa).
2. **State is not colour-only**: selected cards/stepper show border, weight and
   (where useful) an icon, not just a tint.
3. **One visual hierarchy per screen**: progress → page title → fields →
   primary action; avoid competing headings.
4. **Consistent rhythm**: one spacing scale (4/8/12/16/24) and equal content
   margins on every page.
5. **i18n-safe**: no clipping at 640 px with de/ru/ja; labels wrap or elide,
   buttons keep their full text.
6. **Accessible**: real radio controls, keyboard order, accessible names for the
   stepper and status lines, default button set.
7. **Reuse**: theme placeholders, bundled SVG icons, existing `ToggleSwitch`
   and `SecretField`; no parallel widget set.

## Prioritised improvements

| # | Improvement | Impact | Effort |
| - | ----------- | ------ | ------ |
| 1 | Review "Checks" reflects the real probe result / time / fingerprint | High (honesty) | S |
| 2 | Mode cards: icon, hover and selected state | High (key screen) | M |
| 3 | Stepper: numbered, long-locale safe, no duplicate counter | Medium | M |
| 4 | Connection step: split Server / Network sub-pages instead of row show/hide | Medium | M |
| 5 | Success: success icon + selectable read-only invite | Medium | S |
| 6 | Spacing scale, page titles and dialog minimum size | Medium | S |
| 7 | Review: section dividers/cards + slightly taller default | Low | S |
| 8 | Accessibility pass (stepper/status accessible names, focus) | Medium | S |
| 9 | i18n/resize hardening tests (de/ru, long labels) | Medium | S |

## Ordered tasks

### Phase A — Honest review checks (highest priority)

1. `wizard/model.py::WizardDraft`: add
   `server_verified: bool = False`, `server_verified_at: str = ""`,
   `relay_verified: bool = False`, `relay_verified_at: str = ""` (ISO 8601 UTC).
   Bump `DRAFT_VERSION` to `2` (stale drafts are discarded automatically).
2. `wizard/pages/connection.py`:
   - On a server `ProbeOutcome.ok`, set `server_verified=True` and
     `server_verified_at = datetime.now(UTC).isoformat()`.
   - On a server error, clear both.
   - On relay success, set `relay_verified=True`/`relay_verified_at`; on relay
     error or on `_on_relay_edited`, clear them.
   - Include all four in `store()` (model persists them as bool/str).
3. `wizard/pages/review.py::ReviewPage.load`:
   - Server modes: verified → `wizard.review.verified_at` formatted through
     `QLocale`/`QDateTime` (localised short time); otherwise
     `wizard.review.not_verified`.
   - Remote sync: verified → reuse `wizard.connection.test_relay_ok` with the
     fingerprint; otherwise `not_verified`.
   - LAN sync: `wizard.connection.lan_no_test` (deliberately no pre-start test).
4. New key `wizard.review.verified_at` ("Verified at {time}") in all 11 locales.

**Acceptance:** the review always matches the last probe (and resets when the
relevant fields change).

### Phase B — Mode cards (visual hierarchy + selected state)

5. `wizard/widgets.py::RadioCard`:
   - `setObjectName("radioCard")` and expose `icon_name`, `set_selected_state`.
   - Add a 24 px icon on the left (`icons.icon(name)`), the title as the radio
     text, and the description below (wrapped).
   - Drive a dynamic property `selected` from `radio.toggled`; repolish.
   - Add `enterEvent`/`leaveEvent` hover feedback.
6. `themes.py`: add a `card_selected` placeholder and card rules:
   ```
   QFrame#radioCard { border: 1px solid {border}; border-radius: 8px; background: transparent; }
   QFrame#radioCard:hover { border-color: {accent}; }
   QFrame#radioCard[selected="true"] { border: 2px solid {accent}; background: {card_selected}; }
   ```
   (subtle accent tint, light/dark values).
7. `wizard/pages/mode.py::ModePage`: pass the mode icon (`network-cloud` for
   backup, `network-p2p` for LAN/remote, `folder-open` for team; add
   `network-relay.svg` only if a distinct remote icon is wanted).

**Acceptance:** the selected card is unmistakable in both themes; hover works;
keyboard/AT behaviour unchanged (still real `QRadioButton`s).

### Phase C — Stepper (progress clarity + robustness)

8. `wizard/stepper.py::StepIndicator`:
   - Render numbered badges (`1…4`) + labels; current = accent bold, completed =
     muted with a check, future = muted.
   - Add `setAccessibleName`/`setAccessibleDescription` ("Step N of 4: …").
   - Elide labels with `QFontMetrics.elidedText` at the widget width; or switch to
     "number + current label only" below a width threshold.
9. `wizard/dialog.py::_build_ui`: remove the duplicate `self._step_counter` label
   or move it to a compact caption on the stepper row; keep one source of "N of 4".

**Acceptance:** fits 640 px with de/ru/ja; current step is obvious without
relying on bold alone; screen readers announce progress.

### Phase D — Connection step structure

10. `wizard/pages/connection.py`: replace per-row show/hide with deterministic
    mode-specific sections:
    - Keep the shared **Share name** (`bucket`) in a common area.
    - Add an inner `QStackedWidget` with a **Server** form (address, key,
      test+status, cert switch) and a **Network** form (group, password, relay,
      test+status, trust box, receive-only, direction).
    - `set_mode` selects the sub-page instead of hiding interleaved rows; keep
      `_update_test_enabled` and the per-test status logic unchanged.
    - Keep the automation block common below, with a lightweight section title
      instead of a heavy `QGroupBox` (or keep the group box but align its title
      style with the other sections).
11. Preserve values when switching modes (widgets keep their text; only
    visibility changes).

**Acceptance:** each mode shows fields in a logical order with no hidden-row
artefacts; no value is lost when switching modes.

### Phase E — Success screen

12. `wizard/pages/success.py`: add a large success icon at the top (new
    `resources/icons/dialog-ok.svg` in `currentColor`, registered in
    `icons.py::_FALLBACK_MAP`).
13. Replace the invite `QLabel` with a read-only, selectable
    `QLineEdit`/`QPlainTextEdit` (2 lines, framed) so the group/password can be
    selected manually; keep the Copy button.
14. Right-align the success buttons to match the footer convention (or centre the
    pair consistently).

**Acceptance:** invite is selectable/copyable; the icon renders in light/dark.

### Phase F — Spacing, titles, dialog size

15. `dialog.py`: content margins `24, 20, 24, 16`, layout spacing `12`,
    `setMinimumSize(560, 480)` and default `resize(680, 620)`.
16. Add a per-step page title (bold, one size up) at the top of the content area
    using the existing `wizard.step.*` labels, so orientation does not depend on
    the small stepper.
17. `review.py`: add a thin separator between sections (`QFrame.HLine`) and
    ensure the body labels keep their word wrap; keep the scroll area.
18. Folder suggestions: let the three buttons wrap (flow layout or grid fallback)
    so long localized labels do not overflow at 560 px.

**Acceptance:** consistent rhythm across steps; no clipping at the minimum size.

### Phase G — Accessibility polish

19. Set accessible names/descriptions:
    - stepper (progress + current step);
    - mode cards (title + description);
    - status lines (`server_status`/`relay_status`) mirror their text;
    - toggles already get their label as accessible name.
20. Keep one default button per page (`_primary.setDefault(True)` on non-success
    pages), and verify tab order (stepper is not focusable, content then footer).
21. Announce status changes with a `QAccessibleEvent` (NameChanged) on the status
    label where available (best-effort, no new dependency).

**Acceptance:** keyboard-only completion works; status changes are announced.

## Tests

| File | New coverage |
| ---- | ------------ |
| `tests/test_wizard_ui.py` | review checks verified/unverified from probe outcomes; editing resets them; card `selected` property; connection sub-page per mode; success invite read-only; stepper accessible name |
| `tests/test_wizard_model.py` | draft round-trip of the new verification fields; `DRAFT_VERSION` bump discards a v1 draft |
| `tests/test_locales.py` | new key present in all locales; wizard terminology stays clean |
| `tests/test_icons.py` / manual | `dialog-ok.svg` loads (24 px, non-null) |

Long-locale smoke: de/ru/ja at 560 px, light + dark, 125 % scaling.

## Verification

```bash
cd hsync-desktop && QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
.venv/bin/python -m ruff check . && .venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy hsync_desktop
python3 hsync-common/scripts/dev/check_doc_links.py .   # from the workspace root
```

Docs: update `llm-wiki/modules/wizard.md` (selected cards, numbered stepper,
connection sub-pages, review checks, invite field) and `docs/setup-wizard.md`
(review shows the verification result).

## Risks / notes

- The draft schema gains four fields: **bump `DRAFT_VERSION`** so a pre-upgrade
  draft is discarded instead of partially restored.
- Time display must be localised (`QLocale`), not a hardcoded format.
- Card/stepper styling must use theme placeholders (no hardcoded colours) so
  light/dark keep working.
- Keep the real `QRadioButton` as the accessible control; styling must not make
  the card a mouse-only target.
- Do not regress `test_main_window.py::test_menu_action_present` or the existing
  probe-status tests.

## Out of scope

- Restyling Settings or the main window.
- A wizard-wide illustration/branding redesign.
- New shortcuts or protocol changes.
