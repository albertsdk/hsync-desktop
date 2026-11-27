# Configuration

Every HSYNC Desktop setting lives in the **Settings** dialog and is persisted
with Qt `QSettings`. This page is the map of that dialog: which tabs exist, how a
change is applied, and where the values are kept. **The fields themselves are
documented once, in the guide of their tab:**

| Tab | The guide |
| --- | --------- |
| **Sync** | [The Sync settings](settings-sync.md) — share and folder, direction, deletions, timings, limits |
| **Connection** | [The Connection settings](settings-connection.md) — Direct mode and Server mode, identity checks, certificates |
| **General** | [The General settings](settings-general.md) — language, theme, notifications, startup |
| **Advanced** | [The Advanced settings](settings-advanced.md) — performance, changed parts, deletion guard, bandwidth, logs |

Deciding rather than filling? The dedicated guides explain the choice:
[Choose how your devices connect](choose-connection.md),
[Choose your sync direction](choose-sync-direction.md),
[Choose what happens to deleted files](choose-deletion-policy.md) and
[Trust, fingerprints and identity checks](choose-trust.md).

## How the dialog works

Open **Settings** from the menu bar or the tray menu. The dialog has four tabs.
**Direct mode** and **Server mode** are not tabs of their own: they are the two
halves of **Connection**, where one is selected and the other stays one line
away at the top of the tab.

- **Show advanced options** (in **General**) hides the **Advanced** tab and the
  advanced rows and groups of the other tabs until it is on, so the standard view
  stays uncluttered. The advanced options are shown *in place*, inside the
  section they belong to.
- **Apply** saves the changes and closes the dialog (with **Cancel** next to it).
  An editor or a credential prompt keeps its **Save** label instead.
- Settings are read when a sync starts. While a run is in progress the
  connection-critical controls are disabled, and a change takes effect at the
  next start.
- Controls for a feature the installed sync engine does not support are
  disabled, with a tooltip saying why.
- Every field has a tooltip; **Show tooltips** in **General** turns them off.

On a fresh install (no saved settings yet) the app starts in **Direct mode**.

## Secrets

The API key (Server mode) and the shared password (Direct mode) are the two
secrets. They are entered through dedicated dialogs, stored encrypted with a key
derived from the machine, and handed to the engine over a private channel —
never on the command line. See [Secrets](secrets.md).

## Updates

**Help → Check for Updates…** asks the release page for the newest published
version and answers with either the version you are running or the release you
can download. **Check for updates at startup** (in **General**) does the same
once a day, and is off by default.

The request needs no account, carries no identifier and is the only outbound
request the app makes to a host other than your own sync server or peers. The app
never downloads or installs the update itself: **Download** opens the release
page, and the upgrade stays with the process your installation already uses —
`snap refresh`, the Windows installer, `apt`/`dnf`, or a manual replace of the
portable bundle. The startup reminder appears once per release; choosing not to
be reminded again for that version silences it until the next one.

## Where settings are stored

Settings are persisted by Qt `QSettings`; secrets are stored encrypted (see
[Secrets](secrets.md)). The settings live in the per-user Qt location:

- Linux: `~/.config/HSYNC/HSYNCDesktop.conf`
- macOS: `~/Library/Preferences/com.HSYNC.HSYNCDesktop.plist`
- Windows: the `HSYNC\HSYNCDesktop` key under the current user in the registry

To start from scratch, quit the app and remove that entry: the next launch opens
the setup wizard again and asks for the keys. Your files, the `.hsyncignore`
rules and the folder's sync state are not touched (see
[FAQ — Where is the sync state stored](faq.md#where-is-the-sync-state-stored-and-can-i-delete-it-manually)).
