# Choosing a connection mode

HSYNC Desktop reaches your files in one of two ways. Pick the one that matches
where your devices are and who should hold the authoritative copy; the
[Setup wizard](setup-wizard.md) automates the choice for the four common cases.

| | Server mode | p2p mode |
|---|---|---|
| Needs an always-on server | Yes — an HSYNC server | No |
| Authoritative copy lives | On the server | On one of your devices (the *primary*) |
| Devices on the same network | Works | Works, without any server |
| Devices on different networks | Works | Needs a discovery server to find each other |
| Typical use | Backup, sharing a folder with a team | Keeping your own devices in sync |

## Which one?

- **One copy to protect, or several people editing the same folder** → server
  mode: the server is always reachable and holds the share.
- **Your own devices, mostly on the same Wi-Fi** → p2p mode: one device becomes
  the primary and serves the others.
- **Your own devices on different networks** → p2p mode plus a discovery server,
  which only helps the devices find each other and never stores your files.
- **Not sure yet** → the wizard's *Help me choose* asks the same questions and
  preselects the matching mode.

## Where to go next

- [Setup wizard](setup-wizard.md) — the four common cases, step by step.
- [Configuration reference](configuration.md) — every setting of both tabs.
- [Key concepts](concepts.md) — share, group, primary, discovery server, trust.
- [p2p mode](https://github.com/albertsdk/hsync-client/blob/main/docs/p2p-mode.md)
  — how the peer-to-peer transport works.
- [Server mode](https://github.com/albertsdk/hsync-client/blob/main/docs/server-mode.md)
  — how the server transport works.
