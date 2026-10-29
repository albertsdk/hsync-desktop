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

readonly DEFAULT_VERSION="v1.0.11"
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
    local name="$1"
    if ! command -v "${name}" >/dev/null 2>&1; then
        print_tool_hint "${name}"
        fail "required command not found: ${name}"
    fi
}

# --- Prerequisite guidance --------------------------------------------------
#
# The installer never installs packages and never runs sudo: when a required tool
# is missing it prints the commands for the user to run themselves, then fails
# with the same error line as before. Best-effort per platform.

# linux | macos | windows-shell | unknown
detect_platform_os() {
    case "$(uname -s)" in
        Linux) printf 'linux' ;;
        Darwin) printf 'macos' ;;
        MINGW* | MSYS* | CYGWIN* | Windows_NT) printf 'windows-shell' ;;
        *) printf 'unknown' ;;
    esac
}

# debian | rhel | arch | suse | alpine | unknown
detect_linux_family() {
    local id="" id_like="" key value
    if [[ -r /etc/os-release ]]; then
        while IFS='=' read -r key value; do
            value="${value%\"}"
            value="${value#\"}"
            case "${key}" in
                ID) id="${value}" ;;
                ID_LIKE) id_like="${value}" ;;
            esac
        done < /etc/os-release
    fi
    case " ${id} ${id_like} " in
        *" debian "* | *" ubuntu "*) printf 'debian' ;;
        *" rhel "* | *" fedora "* | *" centos "*) printf 'rhel' ;;
        *" arch "*) printf 'arch' ;;
        *" suse "* | *" opensuse "*) printf 'suse' ;;
        *" alpine "*) printf 'alpine' ;;
        *) printf 'unknown' ;;
    esac
}

print_package_hint() {
    local os family pkg
    os="$(detect_platform_os)"
    family="$(detect_linux_family)"
    pkg="$1"
    case "${os}" in
        macos) printf '  brew install %s\n' "${pkg}" >&2 ;;
        linux)
            case "${family}" in
                debian) printf '  sudo apt-get install -y %s\n' "${pkg}" >&2 ;;
                rhel) printf '  sudo dnf install -y %s\n' "${pkg}" >&2 ;;
                arch) printf '  sudo pacman -S --needed %s\n' "${pkg}" >&2 ;;
                suse) printf '  sudo zypper install %s\n' "${pkg}" >&2 ;;
                alpine) printf '  sudo apk add %s\n' "${pkg}" >&2 ;;
                *) printf '  Install %s with your package manager.\n' "${pkg}" >&2 ;;
            esac
            ;;
        *) printf '  Install %s with your package manager.\n' "${pkg}" >&2 ;;
    esac
}

print_tool_hint() {
    local tool="$1"
    case "${tool}" in
        curl)
            printf '\nThe installer downloads the release archive with "curl".\n' >&2
            print_package_hint "curl"
            ;;
        tar)
            printf '\nThe installer extracts the release archive with "tar".\n' >&2
            print_package_hint "tar"
            ;;
        *)
            printf '\nInstall "%s" with your package manager.\n' "${tool}" >&2
            ;;
    esac
    printf 'Then re-run:\n' >&2
    printf '  curl -fsSL "https://github.com/%s/releases/latest/download/install.sh" \\\n' \
        "${REPO}" >&2
    printf '    | bash\n' >&2
    printf '  # already downloaded: ./install.sh\n' >&2
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
