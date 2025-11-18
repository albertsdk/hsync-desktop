# Support

## How to get help

- **[Documentation](docs/README.md)** — usage guide and related project links.
- **[HSYNC Client issues](https://github.com/albertobasso/hsync-client/issues)** — for issues with the underlying sync engine.
- **[GitHub Issues](https://github.com/albertobasso/hsync-desktop/issues)** — bug reports and feature requests for the desktop GUI.
- **[Security Policy](SECURITY.md)** — how to report security vulnerabilities privately.

## Before asking for help

1. Check the [documentation](docs/README.md) and [usage guide](docs/usage.md).
2. Verify the `hsync` binary is correctly discovered (check Settings → Connection).
3. Try running the CLI client directly to isolate GUI vs. engine issues:
   ```bash
   hsync -s https://server:8765 -b mybucket -p /path -v
