# Choose how your devices connect

HSYNC Desktop reaches your files in one of two ways, called **modes**. Pick the
one that matches where your devices are and who should hold the authoritative
copy. The two modes are compatible with each other only in the sense that a device
can be switched later; a given setup uses one or the other.

| | **Server Mode** | **p2p Mode** |
| --- | --- | --- |
| Needs an always-on server | Yes — an HSYNC server | No |
| Authoritative copy lives | On the server | On one of your own devices (the *primary*) |
| Devices on the same network | Works | Works, with no server at all |
| Devices on different networks | Works | Works with a discovery server to find each other |
| Typical use | Backup, sharing a folder with a team | Keeping your own devices in sync |

<img src="assets/screens/10-wizard-purpose.png" alt="The wizard's Purpose step, where the two families are chosen" width="640">

## Which one should I pick?

- **One copy to protect, or several people editing the same folder** → **Server
  Mode**. The server is always reachable and holds the share.
- **Your own devices, mostly on the same Wi-Fi** → **p2p Mode**. One device
  becomes the primary and serves the others; no server needed.
- **Your own devices on different networks** → **p2p Mode plus a discovery
  server**. The discovery server only helps the devices find each other; it never
  carries or stores your files.
- **Not sure yet** → in the [Setup wizard](setup-wizard.md), press **Help me
  choose**: it asks a few short questions and preselects the matching mode for
  you.

## The words you will meet

- **Server Mode** talks to a central **HSYNC server** using an account key.
- **p2p Mode** connects your devices directly. In a group, one device is the
  **primary** (it serves the files) and the others are **secondary**.
- A **discovery server** (an *HSYNC Bootnode*) is the optional helper that lets
  devices on different networks find each other.

See [Key concepts](concepts.md) for these terms in more detail.

## Where the mode is chosen

The mode is the first thing the [Setup wizard](setup-wizard.md) asks. To change it
later, use the wizard again or the **p2p Mode** / **Server Mode** tabs in
**Settings** — every field is documented in the
[Configuration Reference](configuration.md).

## Where to go next

- [Your first sync](first-sync.md) — the guided path, end to end.
- [Set up with the wizard](setup-wizard.md) — the four common cases, step by step.
- [Configuration Reference](configuration.md) — every setting of both tabs.
- [Trust, fingerprints and identity checks](choose-trust.md) — how devices prove
  who they are.
