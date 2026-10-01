#!/usr/bin/env bash

# HSYNC Desktop — run from a fresh clone.
#
# Requires the hsync-common repository checked out as a sibling (the project
# declares it as a Poetry path dependency). This script is the uniform
# "run after clone" entry point, mirroring hsync-server/run.sh and
# hsync-bootnode/run.sh: it creates (or reuses) the in-project virtualenv,
# installs the main dependencies once, and launches the GUI.
#
# The GUI drives the `hsync` client binary; at runtime it looks for it bundled
# in the build, on PATH, or in the sibling ../hsync-client checkout.

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SIBLING="${SCRIPT_DIR}/../hsync-common"
readonly CLIENT_BINARY="${SCRIPT_DIR}/../hsync-client/dist"
readonly BIN="${SCRIPT_DIR}/.venv/bin/hsync-desktop"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    cat <<'EOF'
Run HSYNC Desktop from a fresh clone.

Creates the in-project virtualenv on first use (Poetry) and launches the GUI.
It accepts no arguments beyond this help.

  ./run.sh

The GUI needs the `hsync` client binary: build it with
`cd ../hsync-client && ./compile.sh` (it is then found in the sibling checkout),
or install it so it is on PATH.
EOF
    exit 0
fi

if [[ ! -d "${SIBLING}" ]]; then
    printf 'Error: hsync-common must be checked out as a sibling of hsync-desktop.\n' >&2
    printf '  git clone <hsync-common-url> %s\n' "${SIBLING}" >&2
    exit 1
fi

if [[ ! -x "${BIN}" ]]; then
    command -v poetry >/dev/null 2>&1 || {
        printf 'Error: poetry is required to create the virtualenv.\n' >&2
        printf '  Install it (https://python-poetry.org/docs/#installation) or build the\n' >&2
        printf '  in-project venv yourself: poetry install --only main\n' >&2
        exit 1
    }
    printf 'Creating the in-project virtualenv (first run)…\n'
    cd "${SCRIPT_DIR}"
    poetry config virtualenvs.in-project true
    poetry install --only main --no-interaction
fi

if ! command -v hsync >/dev/null 2>&1 && ! compgen -G "${CLIENT_BINARY}/*/hsync*" >/dev/null 2>&1; then
    printf 'Note: no `hsync` client binary found on PATH or in ../hsync-client/dist.\n' >&2
    printf 'Build it with: (cd ../hsync-client && ./compile.sh)\n' >&2
fi

exec "${BIN}"
