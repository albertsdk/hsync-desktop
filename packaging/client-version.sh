#!/usr/bin/env bash
# Single source for the bundled-engine version gate used by every self-contained
# desktop package. Sourced by compile.sh (host builds) and by the deb-all / rpm-all
# container scripts, so the version format and the compatibility rule stay
# identical wherever a client is bundled.
#
# The desktop ships the engine, so the pairing should be the release the GUI was
# built against (HSYNC_VERSION). A drift confined to the patch number is tolerated
# with a warning; a major/minor drift is refused. The app's runtime check
# (engine/cli.py::is_binary_version_compatible) is deliberately looser and only
# warns.

# Print the full SemVer reported by `<binary> --version` (including any
# -prerelease / +build suffix), or nothing when the binary cannot run here.
# Always returns 0 so callers under `set -e` can test the (possibly empty) value.
_parse_client_version() {
    "$1" --version 2>/dev/null |
        grep -oE '[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.-]+)?' |
        head -1 || true
}

# Classify the engine version against the required one, printing one of:
#   match        - identical
#   patch        - same major and minor; only the patch (or a prerelease/build
#                  suffix) differs -> tolerated with a warning
#   incompatible - major or minor differ -> refused
# SemVer build metadata (+...) carries no precedence and the client never emits
# it, so it is ignored on both sides.
_client_version_relation() {
    local reported="${1%%+*}" expected="${2%%+*}"
    [[ "${reported}" == "${expected}" ]] && { printf 'match'; return 0; }

    local r_core="${reported%%-*}" e_core="${expected%%-*}"
    local r_major="${r_core%%.*}"   e_major="${e_core%%.*}"
    local r_minor="${r_core#*.}"; r_minor="${r_minor%%.*}"
    local e_minor="${e_core#*.}"; e_minor="${e_minor%%.*}"

    if [[ "${r_major}" == "${e_major}" && "${r_minor}" == "${e_minor}" ]]; then
        printf 'patch'
    else
        printf 'incompatible'
    fi
}
