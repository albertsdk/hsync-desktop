# Set up HSYNC Desktop with the wizard

The **Setup wizard** configures HSYNC Desktop for one of four common use cases in
four steps. It is the easiest way to get running; the
[Configuration Reference](configuration.md) remains the full documentation of
every setting.

## When it opens

On the very first launch (no folder configured yet) the wizard opens once after
the main window appears. You can always reopen it later:

- **Menu bar → Setup wizard**
- **Tray icon → Setup wizard…**
- Click the folder placeholder in the main window when no folder is set.

## The four steps

1. **Purpose** — choose what you want to do:

   | Choice | Use it when |
   | ------ | ----------- |
   | Back up my files | You want a copy of your files on a server. |
   | Sync devices on the same network | Your devices share a Wi-Fi/LAN and need no server. |
   | Sync devices from anywhere | The devices are on different networks (needs a relay server). |
   | Share a folder with my team | Several people edit the same folder on a server. |

   Not sure? Use **Help me choose**: answer a few short questions (are you
   sharing with a team? are your devices on the same network? do you want only a
   copy or edits from both sides?) and the wizard selects the right option for
   you. Questions that do not apply stay visible but are disabled, with a short
   explanation.

2. **Folder** — pick the folder to protect or share. The suggested locations use
   your own system folders (Documents, Pictures), the free space is shown, and a
   folder that does not exist, a file, or a system root is refused.

3. **Connection** — the fields depend on the purpose:
   - *Back up* / *Share*: server address, access key, share name. **Test
     connection** sits next to these fields and becomes available once the
     address and key are entered; its result appears right below the button
     (grey while checking, green on success, red on error).
   - *Same network*: a group name and a generated shared password.
   - *From anywhere*: the group and password plus a relay server address;
     **Test connection** becomes available once the relay address is entered and
     shows its fingerprint below the button.

   An optional block chooses whether sync runs in real time, starts with the app,
   and launches HSYNC at system login; **Skip and use recommended values** keeps
   the defaults. Hover a field to see a short explanation of what it means.

4. **Review** — check the summary (secrets are masked) and the verification
   result, use **Edit** to change any step, then **Finish setup**.

## After finishing

The success screen can **Start syncing** immediately or take you back to the main
window. For network (p2p) setups it shows the group and password to copy to your
other devices — use the same values there; the invite can be selected directly or
copied with one click.

If a relay's certificate was not saved during setup, the app asks for
confirmation the first time you connect (a one-time security check).

## Changing things later

Reopen the wizard any time (it pre-fills your current configuration) or use
**Settings** for every advanced option. If you close the wizard before finishing,
it remembers where you left off and offers to resume next time.

## Requirements

Nothing beyond HSYNC Desktop itself. No new software is installed and the wizard
never changes how the bundled sync engine works.
