# Benchmarks

Startup-oriented benchmarks for `hsync-desktop`. Standalone scripts, not
collected by pytest, not run in CI; figures are comparative for the current
machine.

## Startup (`bench_startup.py`)

Measures the two costs that used to dominate GUI startup before the binary-probe
cache (see `hsync_desktop/engine.py`):

| Scenario | What it measures |
| --- | --- |
| `desktop_import_main` | Cold `import hsync_desktop.main` (PySide6 + app modules) |
| `desktop_version_probe` | Raw `<bundled-hsync> --version` subprocess wall-clock (`engine.get_binary_version`) |
| `desktop_capabilities_probe` | Raw `<bundled-hsync> --capabilities-json` subprocess wall-clock (`engine.get_binary_capabilities`) |

A QSettings cache hit is a settings read (no subprocess), so after the first
launch the probes are effectively free; only a launch right after the bundled
binary changes pays the figures measured here.

```bash
cd hsync-desktop
.venv/bin/python bench/bench_startup.py --count 30
.venv/bin/python bench/bench_startup.py --count 30 --binary hsync_desktop/bin/hsync
.venv/bin/python bench/bench_startup.py --count 30 --json-out /tmp/desktop-startup.json
```
