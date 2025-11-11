# Security Policy

## Supported Versions

Security fixes are applied to the latest released version on the `main` branch.

| Version | Supported |
|---------|-----------|
| 1.0.x   | ✅        |
| < 1.0   | ❌        |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, use GitHub's private vulnerability reporting:

1. Open the **Security** tab of this repository.
2. Click **Report a vulnerability** to start a private advisory.

Please include the affected version, steps to reproduce, the impact, and any
suggested mitigation. Allow a reasonable time for a fix before any public
disclosure. We aim to acknowledge reports within a few days and to keep you
informed of remediation progress.

## Security Model

`hsync-desktop` is a GUI front-end that drives the HSYNC sync engine. It shares
the client's security model:

- **Credentials** — the API key and connection settings entered in the UI are
  stored locally; treat the configuration directory as sensitive.
- **Transport security** — HTTPS/WSS supported, including trusting a self-signed
  server certificate via a CA file. Disabling verification is intended for
  testing only.
- **LAN mode (P2P)** — HTTPS/WSS only, with a persistent self-signed identity and
  connection-level fingerprint pinning (TOFU); optional shared-secret authentication.

## Hardening Recommendations

- Lock down the OS user account; the app stores connection secrets locally.
- Prefer verified HTTPS endpoints over disabling certificate checks.
