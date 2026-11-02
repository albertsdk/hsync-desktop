#!/usr/bin/env bash
# Single source for the bundled-engine version gate used by every self-contained
# desktop package. Sourced by compile.sh (host builds) and by the deb-all / rpm-all
# container scripts, so the version format and the exact-match rule stay identical
# wherever a client is bundled.
#
# The desktop ships the engine, so the pairing is immutable: the bundled binary
# must be the exact release the GUI was built against (HSYNC_VERSION). The app's
# runtime check (engine/cli.py::is_binary_version_compatible) is deliberately
# looser and only warns; the strict rule belongs to the build.

# Print the full SemVer reported by `<binary> --version` (including any
# -prerelease / +build suffix), or nothing when the binary cannot run here.
# Always returns 0 so callers under `set -e` can test the (possibly empty) value.
_parse_client_version() {
    "$1" --version 2>/dev/null |
        grep -oE '[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.-]+)?' |
        head -1 || true
}

# True when the engine version equals the required HSYNC_VERSION. SemVer build
# metadata (+...) carries no precedence and the client never emits it, so it is
# ignored on both sides.
_client_version_matches() {
    [[ "${1%%+*}" == "${2%%+*}" ]]
}
