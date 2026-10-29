# Set up HSYNC Desktop with the wizard

The **Setup wizard** configures HSYNC Desktop for one of four common use cases in
four steps. It is the easiest way to get running; the
[Configuration Reference](configuration.md) remains the full documentation of
every setting. If you are following the guided path instead, see
[Your first sync](first-sync.md).

## When it opens

On the very first launch (no folder configured yet) the wizard opens once after
the main window appears. You can always reopen it later:

- **Menu bar → Setup wizard**
- **Tray icon → Setup wizard…**
- Click the folder placeholder in the main window when no folder is set.

## The four steps

### 1. Purpose — what do you want to do?

<img src="assets/screens/10-wizard-purpose.png" alt="Purpose step with the four choices and the Help me choose button" width="640">

| Choice | Use it when |
| ------ | ----------- |
| Back up my files | You want a copy of your files on a server. |
| Sync devices on the same network | Your devices share a Wi-Fi/LAN and need no server. |
| Sync devices from anywhere | The devices are on different networks (needs a discovery server address). |
| Share a folder with my team | Several people edit the same folder on a server. |

Not sure? Use **Help me choose**: answer a few short questions (are you sharing
with a team? do you want only a copy or edits from both sides? are your devices on
the same network?) and the wizard selects the right option for you. Questions that
do not apply stay visible but are disabled, with a short explanation. The two
families are compared in
[Choose how your devices connect](choose-connection.md).

### 2. Folder — what do you want to protect or share?

<img src="assets/screens/11-wizard-folder.png" alt="Folder step with suggested locations and free space" width="640">

Pick the folder. The suggested locations use your own system folders (Documents,
Pictures, Music, Videos), the free space is shown, and a folder that does not
exist, a file, or a system root is refused.

### 3. Connection — how does this device reach the others?

<img src="assets/screens/12-wizard-connection.png" alt="Connection step with address, access key and Test connection" width="640">

The fields depend on the purpose:

- *Back up* / *Share* — server address, access key (the **API key** field in
  Settings), share name. **Test connection** sits next to these fields and becomes
  available once the address and key are entered; its result appears right below
  the button (grey while checking, green on success, red on error).
- *Same network* — a group name and a generated shared password.
- *From anywhere* — the group and password plus a discovery server address;
  **Test connection** becomes available once the address is entered and shows its
  fingerprint below the button.

For the two device-to-device setups, **This device should only receive files**
turns this device into a receiver. It is the same setting as **Sync Type →
Receive only (from other devices)** in Settings; the next step shows the resulting
type.

An optional block chooses whether sync runs in real time, starts with the app, and
launches HSYNC at system login; **Skip** keeps the defaults (its tooltip spells
that out).

### 4. Review — check and finish

<img src="assets/screens/13-wizard-review.png" alt="Review step and the Use these details panel with share, group and password" width="640">

Check the summary (secrets are masked) and the verification result, use **Edit**
to change any step, then **Finish setup**.

## After finishing

For network (p2p) setups the success screen shows the share name, group name and
shared password under *Use these details on another device to connect it to this
one*. Copy them to your other devices — the invite uses the same field names as
the Connection step; use the same values there. The invite can be selected
directly or copied with one click.

<img src="assets/screens/20-wizard-invite.png" alt="The wizard success screen with the invite details and the copy action" width="640">

If a discovery server's certificate was not saved during setup, the app asks for
confirmation the first time you connect (a one-time security check — see
[Trust, fingerprints and identity checks](choose-trust.md)). A discovery servers
that cannot be reached never blocks the sync: the app warns you and keeps working
on the local network, and you can pin the server later from **Manage trusted
servers & devices**.

## Changing things later

Reopen the wizard any time (it pre-fills your current configuration) or use
**Settings** for every advanced option. If you close the wizard before finishing,
it reopens at the step you had reached. **Do this later** is offered only while no
folder is configured yet, i.e. when the setup is still pending.
