# Secrets and credentials

Your account key (Server Mode) and your shared group password (p2p Mode) are
secrets. The app treats them that way: you enter them through dedicated dialogs,
never on a command line, and they never appear in logs or process listings.

<img src="assets/screens/17-credentials.png" alt="The dialog for entering a password or account key, with masked fields" width="480">

## How they are stored and used

- Entered in a **dedicated dialog** (see the p2p and Server tabs in
  [Settings](configuration.md)).
- Stored **encrypted on disk**, with a key derived from your machine.
- Handed to the sync engine over a **private channel**, so they are not visible as
  command-line arguments or in the log.
- Masked by default, with a **show/hide (eye) toggle** on the right of every
  secret field: reveal the value only on demand to check or copy it. The field is
  masked again the next time you open Settings.
- Replaceable at any time: reopen the dialog and enter a new value.

## p2p Mode: the shared password

The p2p password is what authorises changes in a group. The same password on every
device yields the same group key, so **every device in the group must use the exact
same string**.

- A **shared password** must be at least **12 characters**.
- A **raw group key** (only if you already used one) must be at least
  **32 characters**.

To generate a strong one on the command line (the one case where a terminal
helps):

```bash
openssl rand -hex 16
```

Copy the result to every device in the group.

## Server Mode: the account key

The server account key looks like `hs_<id>_<secret>`; it is issued by your HSYNC
server. Enter it in the Server tab's **API key** dialog.

## Keyless p2p runs

If the p2p password is empty, devices are **not authenticated** and reads are open
to anyone who can reach this device. The app warns you before starting and asks
you to confirm; setting a password stops the prompt. See
[Warnings and notifications](warnings.md#warnings-before-a-sync).

## Related

- [Trust, fingerprints and identity checks](choose-trust.md) — how devices prove
  who they are, beyond the password.
- [Configuration Reference](configuration.md) — the p2p and Server tabs.
