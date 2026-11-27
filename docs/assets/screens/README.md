# Screenshots

Pictures used across the user documentation live here. They are captures of the
real application, taken with an English interface (`appearance/language = en`) and
the Light theme, with **sample data only** (share `my-share`, group `my-group`,
server `my-nas:9753`, search servers `rdv.example.net`, a generic path
`/home/user/...`) so no personal information is published.

## Keeping them current

A screenshot is documentation: when a screen changes, update the picture in the
same change. A stale capture is treated as a documentation defect, like a broken
link.

When you re-capture, keep the **file name** the page already references, use the
Light theme and the English interface, size the window so no scrollbar cuts the
content, and **redact** anything private (user names, host names, local paths,
account ids, keys or passwords).

## Shot list

| File | What it shows |
| ---- | ------------- |
| `01-main-window.png` | The main window during a sync: toolbar, path bar, file list, log panel, status bar. |
| `02-status-bar.png` | Close-up of the status bar: role, `Shared: X / Y`, download/send counts, `Sent`/`Received`. |
| `03-menu-bar.png` | The menu bar: **Sync**, **File**, **Settings**, **Setup wizard**, **Help**. |
| `04-tray-menu.png` | The tray icon menu (Show, Start, Compare, Stop, Settings, Setup wizard, Quit). |
| `05-settings-sync.png` | **Settings → Sync**, the whole tab. |
| `06-settings-p2p.png` | **Settings → Connection → Direct mode**, the whole tab. |
| `07-settings-server.png` | **Settings → Connection → Server mode**, the whole tab. |
| `08-settings-general.png` | **Settings → General**, the whole tab. |
| `09-settings-advanced.png` | **Settings → Advanced**, the whole tab (the tab appears once *Show advanced options* is on). |

### Settings groups (the four tab guides)

One capture per `QGroupBox`, used by `docs/settings-{sync,connection,general,advanced}.md`
so the reader sees the group the paragraph talks about instead of hunting it in a
full-tab picture. Same rules as above (English UI, Light theme, sample data:
share `my-share`, group `my-group`, server `my-nas:9753`, search server
`rdv.example.net`, folder `/home/user/Documents`).

| File | What it shows |
| ---- | ------------- |
| `05a-sync-share-path.png` | **Sync → Share & Path**. |
| `05b-sync-mode.png` | **Sync → Sync Mode**. |
| `05c-sync-timing.png` | **Sync → Timing & Intervals** (needs *Show advanced options*). |
| `05d-sync-advanced.png` | **Sync → Transfers** (needs *Show advanced options*). |
| `05e-sync-what-to-sync.png` | **Sync → What to sync**. |
| `05f-sync-trash.png` | **Sync → Trash**. |
| `06a-connection-mode.png` | **Connection → Connection mode**. |
| `06b-connection-group.png` | **Connection → Direct mode → Group**. |
| `06c-connection-finding-devices.png` | **Connection → Direct mode → Finding devices**. |
| `06d-connection-role-security.png` | **Connection → Direct mode → Role & security** (needs *Show advanced options*). |
| `06e-connection-direct-advanced.png` | **Connection → Direct mode → Sharing with devices** (needs *Show advanced options*). |
| `07a-connection-server.png` | **Connection → Server mode → Server**. |
| `07b-connection-certificates.png` | **Connection → Server mode → Certificates** (needs *Show advanced options*). |
| `07c-connection-server-advanced.png` | **Connection → Server mode → Server** (the *Request timeout* advanced row). |
| `08a-general-appearance.png` | **General → Appearance**. |
| `08b-general-notifications.png` | **General → Notifications**. |
| `08c-general-window-startup.png` | **General → Window & Startup**. |
| `09a-advanced-performance.png` | **Advanced → Performance**. |
| `09b-advanced-changed-parts.png` | **Advanced → Changed parts only**. |
| `09c-advanced-deletion-protection.png` | **Advanced → Deletion protection**. |
| `09d-advanced-network.png` | **Advanced → Network**. |
| `09e-advanced-logging.png` | **Advanced → Logging**. |
| `09f-advanced-maintenance.png` | **Advanced → Maintenance**. |

These are `QWidget.grab()` renders of the real dialog on `QT_QPA_PLATFORM=offscreen`,
with `appearance/language = en`, `appearance/theme = light` and the sample values
above set on the widgets before grabbing, so they never contain real host data.
Re-capture them the same way and keep the file names.
| `10-wizard-purpose.png` | Wizard **Purpose** step, including **Help me choose**. |
| `11-wizard-folder.png` | Wizard **Folder** step. |
| `12-wizard-connection.png` | Wizard **Connection** step (group, password, when-to-run). |
| `13-wizard-review.png` | Wizard **Review** step. |
| `14-preview-summary.png` | The plan-confirmation dialog (deletions listed first). |
| `15-trusted-keys.png` | **Manage trusted servers & devices**. |
| `16-trust-prompt.png` | A trust prompt: *Pairing required*. |
| `17-credentials.png` | The password prompt after a p2p authentication failure. |
| `18-notifications.png` | A persistent warning banner in the main window. |
| `19-file-context-menu.png` | The right-click menu on a file row. |
| `20-wizard-invite.png` | The wizard success screen with the *Use these details …* invite. |
