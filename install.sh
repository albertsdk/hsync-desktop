#!/usr/bin/env bash

# HSYNC Desktop installer (no Docker).
#
# Downloads the self-contained desktop bundle for the host and installs it under
# the user's home, exposing a `hsync-desktop` command. The bundle already embeds
# the `hsync` client engine, so nothing else is required.
#
# For a system-wide package instead, use the Debian/Ubuntu `.deb`
# (docs/getting-started-deb.md).

set -euo pipefail

readonly DEFAULT_VERSION="v1.0.0"
readonly REPO="albertsdk/hsync-desktop"
readonly APP="hsync-desktop"

INSTALL_DIR="${HOME}/.local/share/${APP}"
BIN_DIR="${HOME}/.local/bin"
VERSION="${DEFAULT_VERSION}"
DRY_RUN=false

usage() {
    cat <<EOF
Install HSYNC Desktop (self-contained bundle, no Docker).

Usage: ./install.sh [options]

When installing from the release download, forward options to bash (not curl):
  curl -fsSL "https://github.com/${REPO}/releases/latest/download/install.sh" | bash -s -- [options]

Options:
  --version VERSION    Version to install, or 'latest' to resolve the latest
                       stable release automatically (default: ${DEFAULT_VERSION})
  --install-dir PATH   Directory the app is unpacked into
                       (default: ${INSTALL_DIR})
  --bin-dir PATH       Directory the '${APP}' command is linked into
                       (default: ${BIN_DIR})
  --dry-run            Show the planned download without changing anything
  -h, --help           Show this help

The installer never uses sudo and never touches system directories. On Windows,
download the .zip from the release page instead.
EOF
}

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

detect_os() {
    case "$(uname -s)" in
        Linux) printf 'linux' ;;
        Darwin) printf 'darwin' ;;
        *) fail "unsupported OS '$(uname -s)'; on Windows download the .zip from the release page" ;;
    esac
}

detect_arch() {
    case "$(uname -m)" in
        x86_64|amd64) printf 'amd64' ;;
        aarch64|arm64) printf 'arm64' ;;
        *) fail "unsupported architecture '$(uname -m)'" ;;
    esac
}

validate_version() {
    [[ "$1" =~ ^v[0-9]+\.[0-9]+\.[0-9]+([+-][0-9A-Za-z.-]+)?$ ]] ||
        fail "invalid version '$1'; expected vX.Y.Z or 'latest'"
}

resolve_latest_version() {
    local url effective tag
    url="https://github.com/${REPO}/releases/latest"
    effective="$(curl -fsSIL -o /dev/null -w '%{url_effective}' "${url}")" ||
        fail "could not resolve the latest release from ${url}"
    tag="${effective##*/}"
    validate_version "${tag}"
    printf '%s' "${tag}"
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --version)    [[ -n "${2:-}" ]] || fail "$1 requires a value"; VERSION="$2"; shift 2 ;;
            --install-dir) [[ -n "${2:-}" ]] || fail "$1 requires a value"; INSTALL_DIR="$2"; shift 2 ;;
            --bin-dir)    [[ -n "${2:-}" ]] || fail "$1 requires a value"; BIN_DIR="$2"; shift 2 ;;
            --dry-run)    DRY_RUN=true; shift ;;
            -h|--help)    usage; exit 0 ;;
            *) fail "unknown option: $1" ;;
        esac
    done
}

main() {
    parse_args "$@"

    local os arch base_url asset archive workdir
    os="$(detect_os)"
    arch="$(detect_arch)"

    if [[ "${VERSION}" == "latest" ]]; then
        require_command curl
        VERSION="$(resolve_latest_version)"
    fi
    validate_version "${VERSION}"
    # Release assets use the version without the leading 'v' (v1.0.0 -> 1.0.0).
    local asset_version="${VERSION#v}"

    base_url="https://github.com/${REPO}/releases/download/${VERSION}"
    asset="${APP}-${asset_version}-${os}-${arch}.tar.gz"

    printf 'Install directory: %s\n' "${INSTALL_DIR}"
    printf 'Command link: %s/%s\n' "${BIN_DIR}" "${APP}"
    printf 'Download: %s/%s\n' "${base_url}" "${asset}"

    if [[ "${DRY_RUN}" == true ]]; then
        printf 'Dry run: nothing was changed.\n'
        exit 0
    fi

    require_command curl
    require_command tar

    workdir="$(mktemp -d)"
    trap 'rm -rf "${workdir}"' EXIT

    printf 'Downloading %s...\n' "${asset}"
    curl -fL "${base_url}/${asset}" -o "${workdir}/${asset}"

    mkdir -p "${INSTALL_DIR}" "${BIN_DIR}"
    tar -xzf "${workdir}/${asset}" -C "${INSTALL_DIR}" --strip-components=1

    [[ -x "${INSTALL_DIR}/${APP}" ]] || chmod +x "${INSTALL_DIR}/${APP}"
    ln -sfn "${INSTALL_DIR}/${APP}" "${BIN_DIR}/${APP}"

    printf '\nInstalled: %s\n' "${INSTALL_DIR}/${APP}"
    if [[ ":${PATH}:" != *":${BIN_DIR}:"* ]]; then
        printf 'Add %s to your PATH to run `%s`.\n' "${BIN_DIR}" "${APP}"
    fi
    printf 'Launch it with: %s\n' "${APP}"
}

main "$@"
