#!/usr/bin/env bash
#
# HSYNC Desktop - Build Script
#
# Compiles the HSYNC Desktop GUI into a standalone binary using PyInstaller.
# Optionally bundles the hsync-client binary for self-contained distribution.
#
# Usage:
#   ./compile.sh [options]
#
# Options:
#   -c, --clean             Clean build artifacts before building
#   -t, --target TARGET     Build target (default: native)
#                           Supported:
#                               native    Host OS / arch PyInstaller onefile
#                               deb       Debian/Ubuntu .deb package for the
#                                         host arch
#                               deb-all   .deb for amd64 and arm64 (via Docker)
#                               rpm       RHEL-family .rpm package for the host
#                                         arch
#                               rpm-all   .rpm for x86_64 and aarch64 (via
#                                         Docker, Rocky Linux 9 baseline)
#                               appimage  Portable Linux x86_64 .AppImage
#                                         (self-contained, client bundled)
#                               dmg       macOS .app bundle wrapped in a .dmg
#                                         (darwin only, unsigned)
#                               rpi       Raspberry Pi OS 64-bit (arm64)
#                                         onefile binary via Docker
#   -v, --version VERSION   Override the version used for packages (default:
#                           the pyproject.toml version). Also settable via the
#                           HSYNC_VERSION environment variable. A prerelease
#                           (e.g. 1.2.0-alpha.1) is translated to the Debian
#                           form (1.2.0~alpha.1) for the .deb target.
#   -h, --help              Show this help message
#
# Requirements:
#   - native target: Python virtual environment (.venv) with dependencies
#     installed; run 'poetry install' before first build
#   - deb target: Python virtual environment (.venv) + dpkg-deb (available on
#     any Debian/Ubuntu system via dpkg-dev)
#   - rpm target: Python virtual environment (.venv) + rpmbuild (available on
#     any RHEL/Rocky/Fedora system via rpm-build)
#   - deb-all / rpm-all / rpi targets: Docker with qemu-user-static (binfmt)
#     configured (used for arm64 emulation on amd64 hosts)
#   - appimage target: Python virtual environment (.venv) + curl or wget (to
#     fetch appimagetool on first run); Linux x86_64 only
#   - dmg target: macOS only (sips/iconutil/hdiutil); PyInstaller cannot build a
#     .app elsewhere
#
# Raspberry Pi (rpi) target:
#   The rpi target builds the arm64 (64-bit) Raspberry Pi OS binary ONLY. The
#   Qt GUI cannot be built for 32-bit armhf because PySide6 publishes no armv7
#   Linux wheels; armhf is therefore not supported for the desktop GUI. This is
#   intentional and not an error: the script prints an informational note and
#   produces dist/rpi/arm64/hsync-desktop. The same restriction applies to the
#   deb-all target, which builds amd64 and arm64 only.
#
# Output:
#   native:
#     - dist/<os>-<arch>/hsync-desktop[.exe]   Standalone platform-aware
#       executable
#       e.g. dist/linux-amd64/hsync-desktop, dist/darwin-arm64/hsync-desktop
#   deb:
#     - dist/deb/hsync-desktop_<ver>_<arch>.deb   Installable with dpkg -i
#   deb-all:
#     - dist/deb/hsync-desktop_<ver>_amd64.deb
#     - dist/deb/hsync-desktop_<ver>_arm64.deb
#   rpm:
#     - dist/rpm/hsync-desktop-<ver>-1.<dist>.<arch>.rpm   Installable with dnf
#   rpm-all:
#     - dist/rpm/hsync-desktop-<ver>-1.el9.x86_64.rpm
#     - dist/rpm/hsync-desktop-<ver>-1.el9.aarch64.rpm
#   appimage:
#     - dist/appimage/hsync-desktop-<ver>-x86_64.AppImage
#   dmg:
#     - dist/macos/hsync-desktop-<ver>-darwin-<arch>.dmg
#   rpi:
#     - dist/rpi/arm64/hsync-desktop   Raspberry Pi OS 64-bit (aarch64)
#
# Author: Alberto Basso
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Platform detection (OS + architecture) — must match hsync-client/compile.sh
# Normalize OS name: linux | darwin | windows
case "$(uname -s)" in
    Linux*)               readonly OS_NAME="linux" ;;
    Darwin*)              readonly OS_NAME="darwin" ;;
    MINGW*|CYGWIN*|MSYS*) readonly OS_NAME="windows" ;;
    *)                    readonly OS_NAME="$(uname -s | tr '[:upper:]' '[:lower:]')" ;;
esac

# Normalize architecture: amd64 | arm64 | armv7 | x86 | ...
case "$(uname -m)" in
    x86_64|amd64)   readonly ARCH_NAME="amd64" ;;
    aarch64|arm64)  readonly ARCH_NAME="arm64" ;;
    armv7l|armv7)   readonly ARCH_NAME="armv7" ;;
    i386|i686)      readonly ARCH_NAME="x86" ;;
    *)              readonly ARCH_NAME="$(uname -m)" ;;
esac

readonly PLATFORM="${OS_NAME}-${ARCH_NAME}"

readonly APP_NAME="hsync-desktop"
readonly ENTRY_POINT="hsync_desktop/main.py"
readonly BIN_EXT="$([[ "${OS_NAME}" == "windows" ]] && echo ".exe" || echo "")"
readonly OUTPUT_BASE="dist"
readonly OUTPUT_DIR="${OUTPUT_BASE}/${PLATFORM}"
readonly BUILD_DIR="build"
readonly VENV_DIR=".venv"
# PyInstaller and the console python live under Scripts/ on Windows venvs and
# bin/ elsewhere.
if [[ "${OS_NAME}" == "windows" ]]; then
    readonly PYINSTALLER="${VENV_DIR}/Scripts/pyinstaller.exe"
    readonly VENV_PYTHON="${VENV_DIR}/Scripts/python.exe"
else
    readonly PYINSTALLER="${VENV_DIR}/bin/pyinstaller"
    readonly VENV_PYTHON="${VENV_DIR}/bin/python"
fi
# Client binary path is platform-specific (matches hsync-client/compile.sh output)
readonly CLIENT_BINARY="../hsync-client/dist/${PLATFORM}/hsync${BIN_EXT}"

# Raspberry Pi (rpi) target. The Qt GUI requires PySide6, which publishes no
# armv7 (armhf) Linux wheels: only the 64-bit (arm64) target is supported.
# The Raspberry Pi client binary, when built via 'hsync-client/compile.sh
# --target rpi', is the arm64 one at ../hsync-client/dist/rpi/arm64/hsync.
readonly RPI_DIR="packaging/rpi"
readonly RPI_DOCKERFILE="${RPI_DIR}/Dockerfile.builder"
readonly RPI_OUTPUT_DIR="${OUTPUT_BASE}/rpi"
readonly RPI_BUILDER_IMAGE_PREFIX="hsync-desktop-rpi-builder"
readonly RPI_CLIENT_BINARY="../hsync-client/dist/rpi/arm64/hsync"

# AppImage target (Linux x86_64 only). The AppImage wraps the self-contained
# PyInstaller onefile binary (client engine bundled) using appimagetool. Qt and
# Python are already inside the PyInstaller binary, so no linuxdeploy dependency
# scan or Qt plugin is needed — and bundling system libs (glibc) would be wrong.
readonly APPIMAGE_DIR="packaging/appimage"
readonly APPIMAGE_OUTPUT_DIR="${OUTPUT_BASE}/appimage"
readonly APPIMAGE_CACHE_DIR="${APPIMAGE_DIR}/.cache"
readonly APPIMAGE_TOOL="${APPIMAGE_CACHE_DIR}/appimagetool-x86_64.AppImage"
readonly APPIMAGE_TOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
# Desktop payload reused for the AppImage icon and .desktop entry.
readonly DEB_ICON_PNG="packaging/deb/usr/share/icons/hicolor/1024x1024/apps/${APP_NAME}.png"
readonly DEB_ICON_SVG="packaging/deb/usr/share/icons/hicolor/scalable/apps/${APP_NAME}.svg"
readonly DEB_DESKTOP_FILE="packaging/deb/usr/share/applications/${APP_NAME}.desktop"

# macOS .app + .dmg target (darwin only). PyInstaller --windowed produces a real
# .app bundle; the .dmg wraps it with the usual /Applications symlink. Artifacts
# are unsigned — signing/notarization are intentionally not performed (see
# docs/getting-started-macos.md for the Gatekeeper workaround).
readonly MACOS_DIR="packaging/macos"
readonly MACOS_OUTPUT_DIR="${OUTPUT_BASE}/macos"
readonly MACOS_INFO_TEMPLATE="${MACOS_DIR}/Info.plist"
readonly MACOS_BUNDLE_ID="io.hsync.desktop"
readonly MACOS_MIN_VERSION="11.0"

# -----------------------------------------------------------------------------
# Colors (disabled if not a terminal)
# -----------------------------------------------------------------------------

if [[ -t 1 ]]; then
    readonly RED=$'\033[0;31m'
    readonly GREEN=$'\033[0;32m'
    readonly YELLOW=$'\033[0;33m'
    readonly BLUE=$'\033[0;34m'
    readonly CYAN=$'\033[0;36m'
    readonly BOLD=$'\033[1m'
    readonly DIM=$'\033[2m'
    readonly RESET=$'\033[0m'
else
    readonly RED='' GREEN='' YELLOW='' BLUE='' CYAN='' BOLD='' DIM='' RESET=''
fi

# -----------------------------------------------------------------------------
# Logging Functions (all output to stderr)
# -----------------------------------------------------------------------------

log_info() { echo -e "${BLUE}ℹ${RESET} $*" >&2; }
log_ok()   { echo -e "${GREEN}✓${RESET} $*" >&2; }
log_warn() { echo -e "${YELLOW}⚠${RESET} $*" >&2; }
log_error(){ echo -e "${RED}✕${RESET} $*" >&2; }
log_step() { echo -e "${CYAN}→${RESET} ${BOLD}$*${RESET}" >&2; }

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

# Report whether a binfmt_misc handler exists and is enabled.
# $1 = handler name (e.g. qemu-arm, qemu-aarch64)
qemu_handler_active() {
    [[ -d "/proc/sys/fs/binfmt_misc" ]] || return 1
    local f="/proc/sys/fs/binfmt_misc/$1"
    [[ -f "${f}" ]] && grep -q '^enabled' "${f}"
}

# Ensure the qemu-user-static binfmt handlers required for cross-arch Docker
# builds are registered and active. $@ = required handler names.
ensure_qemu_binfmt() {
    local handlers=("$@")
    [[ ${#handlers[@]} -eq 0 ]] && handlers=("qemu-arm")
    log_step "Ensuring qemu-user-static binfmt handlers are active: ${handlers[*]}"
    local missing=()
    local h
    for h in "${handlers[@]}"; do
        qemu_handler_active "${h}" || missing+=("${h}")
    done
    if [[ ${#missing[@]} -eq 0 ]]; then
        log_ok "binfmt handlers already active"
        return 0
    fi
    log_info "Registering qemu-user-static binfmt handlers..."
    # Image pinned by digest: this runs --privileged, so it must not move.
    if ! docker run --rm --privileged \
        multiarch/qemu-user-static@sha256:fe60359c92e86a43cc87b3d906006245f77bfc0565676b80004cc666e4feb9f0 \
        --reset -p yes >/dev/null 2>&1; then
        log_error "Failed to run multiarch/qemu-user-static (is the Docker daemon reachable?)."
        exit 1
    fi
    missing=()
    for h in "${handlers[@]}"; do
        qemu_handler_active "${h}" || missing+=("${h}")
    done
    if [[ ${#missing[@]} -ne 0 ]]; then
        log_error "binfmt handlers still inactive after registration: ${missing[*]}"
        log_error "Cross-arch emulation is unavailable; aborting now to avoid a"
        log_error "misleading 'exec format error' later in the build."
        exit 1
    fi
    log_ok "binfmt handlers registered and active"
}

# Display usage information
show_help() {
    cat << EOF
${BOLD}HSYNC Desktop - Build Script${RESET}

${BOLD}Usage:${RESET}
    ./compile.sh [options]

${BOLD}Options:${RESET}
    -c, --clean             Clean build artifacts before building
    -t, --target TARGET     Build target (default: native)
                            Supported: native, deb, deb-all, rpm, rpm-all, appimage, dmg, rpi
    -v, --version VERSION   Override the version used for packages
                            (default: pyproject.toml). Also settable via
                            HSYNC_VERSION.
    -h, --help              Show this help message

${BOLD}Targets:${RESET}
    native    Host OS / arch PyInstaller onefile binary.
    deb       Debian/Ubuntu .deb package for the host arch (self-contained:
              bundles the matching hsync-client binary).
    deb-all   .deb for amd64 and arm64 via Docker, each bundling a per-arch
              hsync-client built inside the same container. armhf is not
              built: the Qt GUI cannot be built for 32-bit armhf because
              PySide6 publishes no armv7 Linux wheels.
    rpm       RHEL-family .rpm package for the host arch (self-contained:
              bundles the matching hsync-client binary).
    rpm-all   .rpm for x86_64 and aarch64 via Docker (Rocky Linux 9), each
              bundling a per-arch hsync-client built inside the container.
    appimage  Portable self-contained .AppImage for Linux x86_64.
    dmg       macOS .app bundle wrapped in a .dmg (unsigned).
    rpi       Raspberry Pi OS 64-bit (arm64) onefile binary via Docker.

${BOLD}Examples:${RESET}
    ./compile.sh                    # Native host build
    ./compile.sh --clean            # Clean and rebuild
    ./compile.sh --target native    # Explicit native build
    ./compile.sh --target deb       # .deb for host arch
    ./compile.sh --target deb-all   # .deb for amd64 + arm64
    ./compile.sh --target rpm       # .rpm for host arch (RHEL-family)
    ./compile.sh --target rpm-all   # .rpm for x86_64 + aarch64
    ./compile.sh --target appimage  # Portable Linux x86_64 .AppImage
    ./compile.sh --target dmg       # macOS .app + .dmg (unsigned)
    ./compile.sh --target rpi       # Raspberry Pi OS 64-bit (arm64)

${BOLD}Output:${RESET}
    native:
        ${OUTPUT_DIR}/${APP_NAME}${BIN_EXT}   Standalone executable (platform: ${PLATFORM})
    deb:
        ${OUTPUT_BASE}/deb/${DEB_PKG_NAME}_<ver>_<arch>.deb
    deb-all:
        ${OUTPUT_BASE}/deb/${DEB_PKG_NAME}_<ver>_amd64.deb
        ${OUTPUT_BASE}/deb/${DEB_PKG_NAME}_<ver>_arm64.deb
    rpm:
        ${OUTPUT_BASE}/rpm/${DEB_PKG_NAME}-<ver>-1.<dist>.<arch>.rpm
    rpm-all:
        ${OUTPUT_BASE}/rpm/${DEB_PKG_NAME}-<ver>-1.el9.x86_64.rpm
        ${OUTPUT_BASE}/rpm/${DEB_PKG_NAME}-<ver>-1.el9.aarch64.rpm
    appimage:
        ${APPIMAGE_OUTPUT_DIR}/${APP_NAME}-<ver>-x86_64.AppImage
    dmg:
        ${MACOS_OUTPUT_DIR}/${APP_NAME}-<ver>-darwin-<arch>.dmg
    rpi:
        ${RPI_OUTPUT_DIR}/arm64/${APP_NAME}   Raspberry Pi OS 64-bit (aarch64)
EOF
}

# Clean build artifacts: the whole dist/ tree (so stale per-platform outputs do
# not accumulate), the PyInstaller build dir and the auto-generated spec file.
clean_artifacts() {
    log_step "Cleaning build artifacts..."
    local cleaned=0 d
    for d in "${BUILD_DIR}" "${OUTPUT_BASE}"; do
        if [[ -d "${d}" ]]; then
            rm -rf "${d}"
            cleaned=$((cleaned + 1))
        fi
    done
    if [[ -f "${APP_NAME}.spec" ]]; then
        rm -f "${APP_NAME}.spec"
        cleaned=$((cleaned + 1))
    fi
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    if [[ ${cleaned} -gt 0 ]]; then log_ok "Cleaned ${cleaned} artifact(s)"
    else log_info "No artifacts to clean"; fi
}

# Native target prerequisites (the rpi target installs dependencies inside the
# container, so it only needs pyproject.toml).
check_prerequisites() {
    [[ -f "pyproject.toml" ]] || { log_error "pyproject.toml not found."; exit 1; }
    [[ -d ".venv" ]]          || { log_error "Virtual env not found. Run 'poetry install'."; exit 1; }
    [[ -f "${ENTRY_POINT}" ]] || { log_error "Entry point not found: ${ENTRY_POINT}"; exit 1; }
}

# Version override, set by --version and/or the HSYNC_VERSION environment
# variable. Mutable (not readonly) so main() can assign it.
VERSION_OVERRIDE=""

# Get the version: --version flag > HSYNC_VERSION env > pyproject.toml.
get_version() {
    if [[ -n "${VERSION_OVERRIDE}" ]]; then
        printf '%s' "${VERSION_OVERRIDE}"
    elif [[ -n "${HSYNC_VERSION:-}" ]]; then
        printf '%s' "${HSYNC_VERSION}"
    else
        grep -E '^version\s*=' pyproject.toml | head -1 | sed 's/.*"\(.*\)".*/\1/'
    fi
}

# Translate a SemVer version into a Debian policy version so a prerelease sorts
# *before* the stable release (1.2.0-alpha.1 -> 1.2.0~alpha.1).
_semver_to_debian() {
    printf '%s' "$1" | sed 's/-/~/'
}

# Translate a SemVer version into an RPM Version: field (same '~' rule as
# Debian: 1.2.0-alpha.1 -> 1.2.0~alpha.1). The Release: field stays a plain
# number (`1%{?dist}`), so the prerelease marker lives in Version, not Release.
_semver_to_rpm() {
    _semver_to_debian "$1"
}

# Map uname -m to Debian architecture name.
_arch_to_deb() {
    case "$1" in
        x86_64|amd64)   echo "amd64" ;;
        aarch64|arm64)  echo "arm64" ;;
        armv7l|armv7)   echo "armhf" ;;
        *)              echo "$1" ;;
    esac
}

# Map uname -m to RPM architecture name. RHEL/Rocky is 64-bit only, so only
# x86_64 and aarch64 are supported (no armv7hl); anything else is echoed as-is.
_arch_to_rpm() {
    case "$1" in
        x86_64|amd64)   echo "x86_64" ;;
        aarch64|arm64)  echo "aarch64" ;;
        *)              echo "$1" ;;
    esac
}

# PyInstaller flags shared by the native (host) and rpi (container) onefile
# builds. --strip and --distpath are added by the caller; --workpath/--specpath
# are added by the rpi caller only. Backslash continuations (not embedded
# newlines) keep the expansion on a single line so it is safe to interpolate
# inside a ``bash -c`` string.
_onefile_pyi_flags() {
    printf '%s' "--clean --onefile \
        --name ${APP_NAME} \
        --log-level ERROR \
        --hidden-import PySide6.QtCore \
        --hidden-import PySide6.QtGui \
        --hidden-import PySide6.QtWidgets \
        --exclude-module pytest \
        --exclude-module tkinter \
        --exclude-module unittest \
        --exclude-module pip \
        --exclude-module setuptools"
}

# PyInstaller flags for the --onedir build used by the deb/deb-all targets.
# Same hidden imports as _onefile_pyi_flags, minus --onefile (the onedir
# layout is staged under /usr/lib/hsync-desktop inside the package).
_onedir_pyi_flags() {
    printf '%s' "--clean --onedir --noconfirm \
        --name ${APP_NAME} \
        --log-level ERROR \
        --hidden-import PySide6.QtCore \
        --hidden-import PySide6.QtGui \
        --hidden-import PySide6.QtWidgets \
        --exclude-module pytest \
        --exclude-module tkinter \
        --exclude-module unittest \
        --exclude-module pip \
        --exclude-module setuptools"
}

# Read the shared HSYNC_VERSION (SSOT) the desktop expects from its client.
_expected_client_version() {
    "${VENV_PYTHON}" -c \
        'from hsync_common.constants import HSYNC_VERSION; print(HSYNC_VERSION)' 2>/dev/null || true
}

# Refuse to bundle a client binary whose major version differs from the shared
# HSYNC_VERSION. The app also checks this at runtime but only warns, so a stale
# or mismatched pairing must be caught here. A binary that cannot run on this
# host (e.g. the cross-arch rpi client) is reported as unverifiable, not failed.
# $1 = client binary path
_verify_client_compatible() {
    local client_binary="$1"
    local expected reported

    expected="$(_expected_client_version)"
    if [[ -z "${expected}" ]]; then
        log_warn "Could not read HSYNC_VERSION; skipping client compatibility check"
        return 0
    fi

    reported="$("${client_binary}" --version 2>/dev/null |
        grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)" || true
    if [[ -z "${reported}" ]]; then
        log_warn "Cannot run ${client_binary} here; skipping compatibility check"
        return 0
    fi

    if [[ "${reported%%.*}" != "${expected%%.*}" ]]; then
        log_error "hsync-client ${reported} is incompatible with this build" \
            "(needs major ${expected%%.*}); refusing to bundle it"
        exit 1
    fi
    log_ok "hsync-client ${reported} matches HSYNC_VERSION ${expected}"
}

# Emit the PyInstaller --add-data arguments shared by the native and rpi builds.
# When the given client binary exists it is staged into hsync_desktop/bin/ and
# bundled; otherwise the build warns and the desktop falls back to searching
# PATH for 'hsync' at runtime. UI files and icons are always bundled.
# $1 = client binary path (empty to skip client bundling entirely)
# $2 = 'skip-verify' to skip the version compatibility check (cross-arch build)
_add_data_args() {
    local client_binary="${1:-}"
    local skip_verify="${2:-}"
    local add_data_args=()

    if [[ -n "${client_binary}" && -f "${client_binary}" ]]; then
        if [[ "${skip_verify}" == "skip-verify" ]]; then
            log_info "Skipping hsync-client compatibility check (cross-arch build)"
        else
            _verify_client_compatible "${client_binary}"
        fi
        log_step "Bundling hsync-client binary..."
        mkdir -p hsync_desktop/bin
        # Keep the platform suffix: find_hsync_binary() looks for hsync.exe on
        # Windows, so a bare "hsync" would never be found there.
        cp "${client_binary}" "hsync_desktop/bin/hsync${BIN_EXT}"
        chmod +x "hsync_desktop/bin/hsync${BIN_EXT}"
        log_ok "Bundled hsync-client"
        add_data_args+=("--add-data=hsync_desktop/bin/hsync${BIN_EXT}:hsync_desktop/bin")
    elif [[ -n "${client_binary}" ]]; then
        # Drop a stale copy from a previous target so a self-contained package
        # never bundles the wrong or orphaned client.
        rm -f "hsync_desktop/bin/hsync${BIN_EXT}"
        log_warn "hsync-client binary not found at ${client_binary}"
        log_info "Desktop will search PATH for 'hsync' at runtime"
    fi

    add_data_args+=("--add-data=hsync_desktop/ui:hsync_desktop/ui")
    add_data_args+=("--add-data=hsync_desktop/resources/icons:hsync_desktop/resources/icons")

    local arg
    for arg in "${add_data_args[@]}"; do
        echo "${arg}"
    done
}

# Read the newline-separated --add-data arguments emitted by _add_data_args
# into the ADD_DATA_ARGS global array. A global is used instead of a nameref
# (``local -n``) so the script stays compatible with the bash 3.2 shipped on
# stock macOS, where the native target also builds.
ADD_DATA_ARGS=()
_collect_add_data_args() {
    ADD_DATA_ARGS=()
    local line
    while IFS= read -r line; do
        [[ -n "${line}" ]] && ADD_DATA_ARGS+=("${line}")
    done < <(_add_data_args "${1:-}" "${2:-}")
}

# Fail a self-contained target when no client was staged: the package ships the
# engine itself and no longer depends on hsync-client, so a missing binary would
# leave the app unable to drive a sync.
_require_bundled_client() {
    if [[ ! -x "hsync_desktop/bin/hsync${BIN_EXT}" ]]; then
        log_error "A self-contained package requires the hsync-client binary, but none was staged"
        log_info "Build it first: ../hsync-client/compile.sh (arm64: --target rpi)"
        exit 1
    fi
}

# -----------------------------------------------------------------------------
# Native target (host OS/arch)
# -----------------------------------------------------------------------------

build_binary() {
    local version
    version="$(get_version)"
    log_step "Building ${APP_NAME} v${version} for ${PLATFORM}..."

    [[ -x "${PYINSTALLER}" ]] || { log_error "PyInstaller not found. Run 'poetry install'."; exit 1; }

    local -a add_data_args=()
    _collect_add_data_args "${CLIENT_BINARY}"
    _require_bundled_client
    add_data_args=("${ADD_DATA_ARGS[@]}")

    LC_ALL=C.UTF-8 LANG=C.UTF-8 PYTHONWARNINGS=ignore "${PYINSTALLER}" \
        --strip \
        --distpath "${OUTPUT_DIR}" \
        $(_onefile_pyi_flags) \
        "${add_data_args[@]}" \
        "${ENTRY_POINT}"

    local bin_path="${OUTPUT_DIR}/${APP_NAME}${BIN_EXT}"
    if [[ -f "${bin_path}" ]]; then
        local size
        size="$(du -h "${bin_path}" | cut -f1)"

        rm -rf "${BUILD_DIR}" "${APP_NAME}.spec" 2>/dev/null || true

        echo
        log_ok "Build successful!"
        echo
        echo -e "  ${BOLD}Binary:${RESET}   ${bin_path}"
        echo -e "  ${BOLD}Platform:${RESET} ${PLATFORM}"
        echo -e "  ${BOLD}Size:${RESET}     ${size}"
        echo -e "  ${BOLD}Version:${RESET}  ${version}"
        echo
        echo -e "${DIM}Run with: ./${bin_path}${RESET}"
    else
        log_error "Build failed: output binary not found at ${bin_path}"
        exit 1
    fi
}

# -----------------------------------------------------------------------------
# Raspberry Pi OS 64-bit (arm64) target — standalone executable via Docker
# -----------------------------------------------------------------------------

# PyInstaller cannot cross-compile, so the binary is produced by running it
# inside an emulated arm64 python:3.12-bookworm container (Raspberry Pi OS
# Bookworm is Debian 12 / glibc 2.36, matching the base image).
#
# Only arm64 is built: PySide6 publishes no armv7 Linux wheels, so the Qt GUI
# cannot be built for 32-bit armhf. armhf is intentionally unsupported and the
# function prints an informational note rather than failing.
#
# Output: dist/rpi/arm64/hsync-desktop
build_rpi() {
    local version
    version="$(get_version)"

    log_step "Building ${APP_NAME} v${version} for Raspberry Pi OS (arm64)..."

    log_info "Raspberry Pi OS 32-bit (armhf) is not supported for the GUI:"
    log_info "PySide6 publishes no armv7 Linux wheels. Building arm64 only."

    if ! command -v docker >/dev/null 2>&1; then
        log_error "docker is required for the rpi target."
        exit 1
    fi
    if [[ ! -f "${RPI_DOCKERFILE}" ]]; then
        log_error "Builder Dockerfile missing: ${RPI_DOCKERFILE}"
        exit 1
    fi

    # Monorepo root: mounts hsync-desktop AND hsync-common (the Poetry path
    # dependency) into the container at /repo.
    local repo_root
    repo_root="$(cd "${SCRIPT_DIR}/.." && pwd)"

    ensure_qemu_binfmt qemu-aarch64

    local out_dir="${RPI_OUTPUT_DIR}/arm64"
    mkdir -p "${out_dir}"
    local out_abs
    out_abs="$(cd "${out_dir}" && pwd)"
    local builder_tag="${RPI_BUILDER_IMAGE_PREFIX}:arm64"

    log_step "Building Docker image ${builder_tag}..."
    DOCKER_BUILDKIT=1 docker build \
        --platform linux/arm64 \
        --build-arg TARGET_PLATFORM=linux/arm64 \
        -t "${builder_tag}" \
        -f "${RPI_DOCKERFILE}" \
        "${RPI_DIR}"

    # Reuse the same PyInstaller flags and --add-data logic as the native build.
    local flags
    flags="$(_onefile_pyi_flags)"

    local -a add_data_args=()
    _collect_add_data_args "${RPI_CLIENT_BINARY}" skip-verify
    _require_bundled_client
    add_data_args=("${ADD_DATA_ARGS[@]}")
    local add_data=""
    if [[ ${#add_data_args[@]} -gt 0 ]]; then
        printf -v add_data '%s ' "${add_data_args[@]}"
        add_data="${add_data% }"
    fi

    # Dependencies are installed into a container-local venv (HOME=/tmp) so the
    # mounted source tree stays pristine; only the produced executable is
    # written back to the host under /out.
    log_step "Compiling arm64 binary inside container..."
    docker run --rm \
        --platform linux/arm64 \
        -u "$(id -u):$(id -g)" \
        -e HOME=/tmp -e XDG_CACHE_HOME=/tmp \
        -v "${repo_root}:/repo" \
        -v "${out_abs}:/out" \
        -w /repo/hsync-desktop \
        -e LC_ALL=C -e PYTHONWARNINGS=ignore \
        -e PIP_DEFAULT_TIMEOUT=300 -e PIP_RETRIES=10 \
        -e POETRY_REQUESTS_TIMEOUT=300 \
        -e HSYNC_VERSION="${version}" \
        "${builder_tag}" \
        bash -c "
            set -euo pipefail
            poetry install --only main,build
            HSYNC_PREFER_PATH_PYINSTALLER=1 poetry run pyinstaller \
                --strip \
                ${flags} \
                ${add_data} \
                --distpath /out \
                --workpath /tmp/work \
                --specpath /tmp/work \
                hsync_desktop/main.py
        "

    local bin_path="${out_dir}/${APP_NAME}"
    if [[ ! -f "${bin_path}" ]]; then
        log_error "arm64 executable not produced at ${bin_path}"
        exit 1
    fi

    local size
    size="$(du -h "${bin_path}" | cut -f1)"

    echo
    log_ok "Raspberry Pi executable built!"
    echo
    echo -e "  ${BOLD}Binary:${RESET}   ${bin_path}"
    echo -e "  ${BOLD}Platform:${RESET} rpi-arm64 (aarch64)"
    echo -e "  ${BOLD}Size:${RESET}     ${size}"
    echo -e "  ${BOLD}Version:${RESET}  ${version}"
    echo
    echo -e "${DIM}Note: 32-bit Raspberry Pi OS (armhf) is not supported for the GUI.${RESET}"
    echo -e "${DIM}Run with: ./${bin_path}${RESET}"
}

# -----------------------------------------------------------------------------
# Debian/Ubuntu .deb package build
# -----------------------------------------------------------------------------

# Configuration for the deb target.
readonly DEB_DIR="packaging/deb"
readonly DEB_SRC_CONTROL="${DEB_DIR}/DEBIAN"
readonly DEB_SRC_DATA="${DEB_DIR}"
readonly DEB_PKG_NAME="hsync-desktop"
readonly DEB_OUTPUT_DIR="${OUTPUT_BASE}/deb"
readonly DEB_BUILD_DIR="${BUILD_DIR}/deb"

# Restore the execute bit on the bundled hsync-client inside a staged payload.
# The stage finalisers below normalise every file under usr/ to 0644, but the
# client is the sync engine, not data: without +x find_hsync_binary() rejects
# it and the GUI cannot start any sync. Self-contained packages always ship the
# client, so a missing one is a build error.
# $1 = stage_dir
_restore_bundled_client_exec() {
    local stage_dir="$1"
    local client
    client="$(find "${stage_dir}/usr/lib/${APP_NAME}" -type f \
        -path "*/hsync_desktop/bin/hsync${BIN_EXT}" -print -quit 2>/dev/null)"
    if [[ -z "${client}" ]]; then
        log_error "Staged payload is missing the bundled hsync-client binary"
        exit 1
    fi
    chmod 0755 "${client}"
}

# Normalise a staged .deb payload so the resulting package is lintian-clean:
# directories 0755 / files 0644 under usr/, the executable bit preserved on the
# two programs (the GUI and the bundled hsync-client), and a man page (if
# present) gzip-compressed (-n => reproducible).
_finalize_deb_stage() {
    local stage_dir="$1"
    find "${stage_dir}/usr" -type d -exec chmod 0755 {} + 2>/dev/null || true
    find "${stage_dir}/usr" -type f -exec chmod 0644 {} + 2>/dev/null || true
    chmod 0755 "${stage_dir}/usr/lib/${APP_NAME}/${APP_NAME}"
    _restore_bundled_client_exec "${stage_dir}"
    local man="${stage_dir}/usr/share/man/man1/${APP_NAME}.1"
    if [[ -f "${man}" ]]; then
        gzip -n -9 -f "${man}"
    fi
}

# Compute the Debian packages the frozen payload needs from the system: every
# DT_NEEDED soname that is NOT shipped inside the payload, resolved to its owning
# package via ldconfig + dpkg -S. Replaces the old hand-maintained list, which
# drifted from reality (it declared bundled libraries and missed
# libxcb1/libdrm2/libwayland-*). Echoes a comma-separated list (empty when none).
# $1 = stage_dir
_compute_runtime_depends() {
    local stage_dir="$1"
    local payload="${stage_dir}/usr/lib/${APP_NAME}"
    [[ -d "${payload}" ]] || { echo ""; return 0; }

    # Soname stems shipped inside the payload (no system package needed).
    local -a shipped=()
    local f b
    while IFS= read -r -d '' f; do
        b="${f##*/}"
        shipped+=("${b%%.so*}")
    done < <(find "${payload}" -name '*.so*' -print0)

    # Distinct DT_NEEDED sonames across every ELF in the payload.
    local -a needed=()
    local lib
    while IFS= read -r -d '' f; do
        while IFS= read -r lib; do
            if [[ -n "${lib}" ]]; then
                needed+=("${lib}")
            fi
        done < <(objdump -p "${f}" 2>/dev/null | sed -n 's/^ *NEEDED *//p')
    done < <(find "${payload}" -type f \( -name '*.so*' -o -perm -111 \) -print0)

    local -a pkgs=()
    local stem i is_shipped path pkg
    while IFS= read -r lib; do
        [[ -n "${lib}" ]] || continue
        stem="${lib%%.so*}"
        is_shipped=0
        for i in "${shipped[@]}"; do
            if [[ "${i}" == "${stem}" ]]; then
                is_shipped=1
                break
            fi
        done
        if [[ "${is_shipped}" -eq 1 ]]; then
            continue
        fi
        path="$(ldconfig -p 2>/dev/null | sed -n 's/.*=> //p' | grep -F "/${lib}" | head -1)"
        [[ -n "${path}" ]] || continue
        pkg="$(dpkg -S "${path}" 2>/dev/null | cut -d: -f1)"
        if [[ -n "${pkg}" ]]; then
            pkgs+=("${pkg}")
        fi
    done < <(printf '%s\n' "${needed[@]}" | sort -u)

    local joined="" p
    while IFS= read -r p; do
        [[ -n "${p}" ]] || continue
        joined="${joined:+${joined}, }${p}"
    done < <(printf '%s\n' "${pkgs[@]}" | sort -u)
    echo "${joined}"
}

# Compute the shared-library dependency string for the staged main executable
# using dpkg-shlibdeps (libc6 and any system libs the binary links). Echoes the
# dependency list without the "shlibs:Depends=" prefix, or an empty string when
# dpkg-shlibdeps is unavailable or resolves nothing.
# $1 = stage_dir
_compute_shlib_depends() {
    local stage_dir="$1"
    local bin="${stage_dir}/usr/lib/${APP_NAME}/${APP_NAME}"
    command -v dpkg-shlibdeps >/dev/null 2>&1 || { echo ""; return 0; }
    [[ -f "${bin}" ]] || { echo ""; return 0; }
    # Resolve the binary to an absolute path so it still exists after we cd
    # into the temporary control dir.
    local bin_abs
    bin_abs="$(cd "$(dirname "${bin}")" && pwd)/${APP_NAME}"
    local tmp deps
    tmp="$(mktemp -d)"
    mkdir -p "${tmp}/debian"
    printf 'Source: %s\n\nPackage: %s\nArchitecture: any\n' \
        "${DEB_PKG_NAME}" "${DEB_PKG_NAME}" > "${tmp}/debian/control"
    deps="$(cd "${tmp}" && dpkg-shlibdeps -O --ignore-missing-info \
        "${bin_abs}" 2>/dev/null \
        | sed -n 's/^shlibs:Depends=//p')"
    rm -rf "${tmp}"
    echo "${deps}"
}

# Write the Depends: line of the staged DEBIAN/control from what the frozen
# payload actually needs at run time: the bootloader's shared-library deps
# (dpkg-shlibdeps, e.g. libc6/zlib1g, which carry version constraints) plus the
# external libraries the bundled payload links but does not ship. Replaces the
# previous hand-maintained list.
# $1 = stage_dir
_inject_shlib_depends() {
    local stage_dir="$1"
    local shlibs runtime entry
    shlibs="$(_compute_shlib_depends "${stage_dir}")"
    runtime="$(_compute_runtime_depends "${stage_dir}")"

    local -a names=()
    local -a parts=()
    local IFS=','
    if [[ -n "${shlibs}" ]]; then
        for entry in ${shlibs}; do
            entry="${entry#"${entry%%[![:space:]]*}"}"
            [[ -n "${entry}" ]] || continue
            names+=("${entry%% *}")
            parts+=("${entry}")
        done
    fi
    if [[ -n "${runtime}" ]]; then
        for entry in ${runtime}; do
            entry="${entry#"${entry%%[![:space:]]*}"}"
            [[ -n "${entry}" ]] || continue
            local dup=0 n
            for n in "${names[@]}"; do
                if [[ "${n}" == "${entry}" ]]; then
                    dup=1
                    break
                fi
            done
            if [[ "${dup}" -eq 0 ]]; then
                names+=("${entry}")
                parts+=("${entry}")
            fi
        done
    fi

    if [[ ${#parts[@]} -eq 0 ]]; then
        log_warn "Could not compute runtime dependencies; falling back to libc6"
        parts=("libc6")
    fi

    local joined="" p
    for p in "${parts[@]}"; do
        joined="${joined:+${joined}, }${p}"
    done
    log_step "Runtime dependencies: ${joined}"
    sed -i.bak "s|^Depends:.*$|Depends: ${joined}|" "${stage_dir}/DEBIAN/control"
    rm -f "${stage_dir}/DEBIAN/control.bak"
}

# Build a .deb package for the host architecture (native build, no Docker).
build_deb() {
    local version deb_version deb_arch
    version="$(get_version)"
    deb_version="$(_semver_to_debian "${version}")"
    deb_arch="$(_arch_to_deb "${ARCH_NAME}")"

    log_step "Building ${DEB_PKG_NAME} v${version} for ${deb_arch} (host build)..."

    # --- prerequisites ---------------------------------------------------
    check_prerequisites
    if ! command -v dpkg-deb >/dev/null 2>&1; then
        log_error "dpkg-deb is required for the deb target."
        log_info "Install it with: apt install dpkg-dev"
        exit 1
    fi
    mkdir -p "${DEB_OUTPUT_DIR}" "${DEB_BUILD_DIR}"

    # --- PyInstaller --onedir on host ------------------------------------
    local onedir_dist="${DEB_BUILD_DIR}/pyinstaller"
    mkdir -p "${onedir_dist}"

    # Self-contained: bundle the host-arch hsync-client so the .deb does not
    # depend on a separate hsync-client package. The binary is checked against
    # HSYNC_VERSION at build time (a mismatched major fails the build).
    local -a add_data_args=()
    _collect_add_data_args "${CLIENT_BINARY}"
    _require_bundled_client
    add_data_args=("${ADD_DATA_ARGS[@]}")

    log_step "Compiling ${APP_NAME} with PyInstaller (--onedir)..."
    LC_ALL=C.UTF-8 LANG=C.UTF-8 PYTHONWARNINGS=ignore "${PYINSTALLER}" \
        --distpath "${onedir_dist}" \
        --workpath "${DEB_BUILD_DIR}/work" \
        --strip \
        $(_onedir_pyi_flags) \
        "${add_data_args[@]}" \
        "${ENTRY_POINT}"

    local built_dir="${onedir_dist}/${APP_NAME}"
    if [[ ! -d "${built_dir}" ]]; then
        log_error "PyInstaller --onedir output not found at ${built_dir}"
        exit 1
    fi

    # --- stage .deb tree -------------------------------------------------
    local stage_dir="${DEB_BUILD_DIR}/${DEB_PKG_NAME}_${deb_version}_${deb_arch}"
    rm -rf "${stage_dir}"
    mkdir -p "${stage_dir}"

    log_step "Staging .deb tree at ${stage_dir}..."

    cp -a "${DEB_SRC_CONTROL}" "${stage_dir}/"
    chmod 0755 "${stage_dir}/DEBIAN"/*inst* "${stage_dir}/DEBIAN"/*rm* 2>/dev/null || true

    local item
    for item in "${DEB_SRC_DATA}"/*; do
        local bn
        bn="$(basename "${item}")"
        if [[ "${bn}" == "DEBIAN" || "${bn}" == "Dockerfile.builder" ]]; then
            continue
        fi
        cp -a "${item}" "${stage_dir}/"
    done

    # Place the PyInstaller --onedir output under /usr/lib/hsync-desktop/.
    mkdir -p "${stage_dir}/usr/lib"
    cp -a "${built_dir}" "${stage_dir}/usr/lib/${APP_NAME}"
    chmod 0755 "${stage_dir}/usr/lib/${APP_NAME}/${APP_NAME}"

    # Create a relative symlink: /usr/bin/hsync-desktop -> ../lib/hsync-desktop/hsync-desktop
    mkdir -p "${stage_dir}/usr/bin"
    ln -sf "../lib/${APP_NAME}/${APP_NAME}" "${stage_dir}/usr/bin/${APP_NAME}"

    _finalize_deb_stage "${stage_dir}"

    log_step "Injecting version ${deb_version} and arch ${deb_arch} into control..."
    sed -i.bak \
        -e "s/__VERSION__/${deb_version}/g" \
        -e "s/__ARCH__/${deb_arch}/g" \
        "${stage_dir}/DEBIAN/control"
    rm -f "${stage_dir}/DEBIAN/control.bak"

    _inject_shlib_depends "${stage_dir}"

    log_step "Building .deb package..."
    local deb_cmd
    if command -v fakeroot >/dev/null 2>&1; then
        deb_cmd="fakeroot"
    else
        deb_cmd=""
        log_warn "fakeroot not available — building .deb with current user ownership"
    fi
    ${deb_cmd} dpkg-deb --build "${stage_dir}" "${DEB_OUTPUT_DIR}"

    local deb_name="${DEB_PKG_NAME}_${deb_version}_${deb_arch}.deb"
    local deb_path="${DEB_OUTPUT_DIR}/${deb_name}"
    local size deb_abs
    size="$(du -h "${deb_path}" | cut -f1)"
    deb_abs="$(cd "$(dirname "${deb_path}")" && pwd)/$(basename "${deb_path}")"

    rm -rf "${DEB_BUILD_DIR}/work" "${DEB_BUILD_DIR}/pyinstaller" "${APP_NAME}.spec" 2>/dev/null || true

    echo
    log_ok "Debian package built!"
    echo
    echo -e "  ${BOLD}Package:${RESET}  ${deb_name}"
    echo -e "  ${BOLD}Arch:${RESET}     ${deb_arch}"
    echo -e "  ${BOLD}Size:${RESET}     ${size}"
    echo -e "  ${BOLD}Version:${RESET}  ${deb_version}"
    echo
    echo -e "${DIM}Install with:${RESET}"
    echo -e "${DIM}  sudo dpkg -i ${deb_abs}${RESET}"
    echo -e "${DIM}  sudo apt install -f  # to resolve any missing dependencies${RESET}"
    echo
    local sep="────────────────────────────────────────────────────────────"
    echo -e "${GREEN}${BOLD}${sep}${RESET}"
    echo -e "${GREEN}${BOLD}  📦  Installation package:${RESET}"
    echo -e "${GREEN}${BOLD}      ${deb_abs}${RESET}"
    echo -e "${GREEN}${BOLD}${sep}${RESET}"
}

# -----------------------------------------------------------------------------
# Debian/Ubuntu .deb — amd64 + arm64 (via Docker)
# -----------------------------------------------------------------------------

# Configuration for the deb-all target. Only amd64 and arm64 are built: the Qt
# GUI cannot be built for 32-bit armhf (PySide6 publishes no armv7 wheels).
readonly DEB_ALL_DIR="${DEB_DIR}"
readonly DEB_ALL_OUTPUT_DIR="${OUTPUT_BASE}/deb"
readonly DEB_ALL_BUILD_DIR="${BUILD_DIR}/deb-all"
readonly DEB_ALL_BUILDER_IMAGE_PREFIX="hsync-desktop-deb-builder"

build_deb_all() {
    local version deb_version
    version="$(get_version)"
    deb_version="$(_semver_to_debian "${version}")"

    log_step "Building ${DEB_PKG_NAME} v${version} for amd64 and arm64..."
    log_info "armhf is not supported for the GUI: PySide6 publishes no armv7 Linux wheels."

    if ! command -v docker >/dev/null 2>&1; then
        log_error "docker is required for the deb-all target."
        exit 1
    fi
    if [[ ! -d "${DEB_SRC_CONTROL}" ]]; then
        log_error "DEBIAN control directory missing: ${DEB_SRC_CONTROL}"
        exit 1
    fi

    mkdir -p "${DEB_ALL_OUTPUT_DIR}"

    local repo_root
    repo_root="$(cd "${SCRIPT_DIR}/.." && pwd)"

    ensure_qemu_binfmt qemu-aarch64

    local pyinstaller_flags="$(_onedir_pyi_flags) --strip"
    # UI files and icons; the client is built and staged inside each container
    # (same arch and distro, so the bundled engine shares the GUI's glibc).
    _collect_add_data_args ""

    local -A arch_docker_platform
    arch_docker_platform["amd64"]="linux/amd64"
    arch_docker_platform["arm64"]="linux/arm64"

    local -a deb_archs=("amd64" "arm64")
    local out_abs
    out_abs="$(cd "${DEB_ALL_OUTPUT_DIR}" && pwd)"

    for deb_arch in "${deb_archs[@]}"; do
        local docker_platform="${arch_docker_platform[${deb_arch}]}"
        local builder_tag="${DEB_ALL_BUILDER_IMAGE_PREFIX}:${deb_arch}"
        local arch_build_dir="${DEB_ALL_BUILD_DIR}/${deb_arch}"
        local bin_dir="${arch_build_dir}/pyinstaller"
        local work_dir="${arch_build_dir}/work"
        local stage_dir="${arch_build_dir}/${DEB_PKG_NAME}_${deb_version}_${deb_arch}"
        mkdir -p "${bin_dir}" "${work_dir}"

        # The container builds and stages this arch's client at
        # hsync_desktop/bin/hsync; bundle it alongside the UI/icon data.
        local client_platform="linux-${deb_arch}"
        local add_data="--add-data=hsync_desktop/bin/hsync:hsync_desktop/bin"
        local _arg
        for _arg in "${ADD_DATA_ARGS[@]}"; do
            add_data+=" ${_arg}"
        done

        echo
        log_step "─── ${deb_arch} build ───────────────────────────────────────"

        log_step "Building Docker image ${builder_tag}..."
        DOCKER_BUILDKIT=1 docker build \
            --platform "${docker_platform}" \
            --build-arg TARGET_PLATFORM="${docker_platform}" \
            -t "${builder_tag}" \
            -f "${DEB_ALL_DIR}/Dockerfile.builder" \
            "${DEB_ALL_DIR}"

        log_step "Compiling ${deb_arch} binary inside container..."
        docker run --rm \
            --platform "${docker_platform}" \
            -u "$(id -u):$(id -g)" \
            -e HOME=/tmp -e XDG_CACHE_HOME=/tmp \
            -v "${repo_root}:/repo" \
            -w /repo/hsync-desktop \
            -e LC_ALL=C -e PYTHONWARNINGS=ignore \
            -e PIP_DEFAULT_TIMEOUT=300 -e PIP_RETRIES=10 \
            -e POETRY_REQUESTS_TIMEOUT=300 \
            -e HSYNC_VERSION="${version}" \
            "${builder_tag}" \
            bash -c "
                set -euo pipefail
                poetry config virtualenvs.in-project true
                poetry config installer.max-workers 4

                # Build the matching-arch, matching-distro hsync-client from the
                # sibling checkout so the bundled engine shares the GUI's glibc.
                (
                    cd /repo/hsync-client
                    client_ok=0
                    for attempt in 1 2 3; do
                        if poetry install --no-root --without dev; then client_ok=1; break; fi
                        echo \"client poetry install attempt \${attempt}/3 failed, retrying in 10s...\" >&2
                        sleep 10
                    done
                    [ \"\${client_ok}\" -eq 1 ] || { echo 'client poetry install failed after 3 attempts' >&2; exit 1; }
                    ./compile.sh -c
                )
                mkdir -p hsync_desktop/bin
                cp \"/repo/hsync-client/dist/${client_platform}/hsync\" hsync_desktop/bin/hsync

                install_ok=0
                for attempt in 1 2 3; do
                    if poetry install --only main,build; then install_ok=1; break; fi
                    echo \"poetry install attempt \${attempt}/3 failed, retrying in 10s...\" >&2
                    sleep 10
                done
                [ \"\${install_ok}\" -eq 1 ] || { echo 'poetry install failed after 3 attempts' >&2; exit 1; }
                HSYNC_PREFER_PATH_PYINSTALLER=1 poetry run pyinstaller \
                    ${pyinstaller_flags} \
                    ${add_data} \
                    --distpath ${bin_dir} \
                    --workpath ${work_dir} \
                    hsync_desktop/main.py
            "

        # PyInstaller writes the spec to the container cwd (/repo/hsync-desktop),
        # i.e. the mounted host tree; remove it so it does not linger.
        rm -f "${APP_NAME}.spec" 2>/dev/null || true

        local built_dir="${bin_dir}/${APP_NAME}"
        if [[ ! -d "${built_dir}" ]]; then
            log_error "${deb_arch} build directory not produced at ${built_dir}"
            exit 1
        fi
        log_ok "${deb_arch} binary ready ($(du -sh "${built_dir}" | cut -f1))"

        log_step "Staging .deb tree for ${deb_arch}..."
        rm -rf "${stage_dir}"
        mkdir -p "${stage_dir}"
        stage_abs="$(cd "${stage_dir}" && pwd)"

        cp -a "${DEB_SRC_CONTROL}" "${stage_dir}/"
        chmod 0755 "${stage_dir}/DEBIAN"/*inst* "${stage_dir}/DEBIAN"/*rm* 2>/dev/null || true

        local item
        for item in "${DEB_SRC_DATA}"/*; do
            local bn
            bn="$(basename "${item}")"
            if [[ "${bn}" == "DEBIAN" || "${bn}" == "Dockerfile.builder" ]]; then
                continue
            fi
            cp -a "${item}" "${stage_dir}/"
        done

        mkdir -p "${stage_dir}/usr/lib"
        cp -a "${built_dir}" "${stage_dir}/usr/lib/${APP_NAME}"
        chmod 0755 "${stage_dir}/usr/lib/${APP_NAME}/${APP_NAME}"

        mkdir -p "${stage_dir}/usr/bin"
        ln -sf "../lib/${APP_NAME}/${APP_NAME}" "${stage_dir}/usr/bin/${APP_NAME}"

        _finalize_deb_stage "${stage_dir}"

        sed -i.bak \
            -e "s/__VERSION__/${deb_version}/g" \
            -e "s/__ARCH__/${deb_arch}/g" \
            "${stage_dir}/DEBIAN/control"
        rm -f "${stage_dir}/DEBIAN/control.bak"

        log_step "Building .deb for ${deb_arch}..."
        docker run --rm \
            --platform "${docker_platform}" \
            -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" \
            -v "${stage_abs}:/pkg" \
            -v "${out_abs}:/out" \
            -w /pkg \
            "${builder_tag}" \
            bash -c "
                set -e
                bin=/pkg/usr/lib/${APP_NAME}/${APP_NAME}
                tmp=\$(mktemp -d)
                mkdir -p \"\${tmp}/debian\"
                printf 'Source: %s\n\nPackage: %s\nArchitecture: any\n' '${DEB_PKG_NAME}' '${DEB_PKG_NAME}' > \"\${tmp}/debian/control\"
                deps=\$(cd \"\${tmp}\" && dpkg-shlibdeps -O --ignore-missing-info \"\${bin}\" 2>/dev/null | sed -n 's/^shlibs:Depends=//p')
                rm -rf \"\${tmp}\"
                if [ -n \"\${deps}\" ]; then
                    sed -i \"s/^Depends: \\(.*\\)\$/Depends: \\1, \${deps}/\" /pkg/DEBIAN/control
                    echo \"Added shared-library dependencies: \${deps}\"
                else
                    echo 'WARNING: dpkg-shlibdeps resolved no dependencies' >&2
                fi
                dpkg-deb --build /pkg /out
                chmod 0644 /out/${DEB_PKG_NAME}_${deb_version}_${deb_arch}.deb
                chown -R \"\${HOST_UID}:\${HOST_GID}\" /pkg \"/out/${DEB_PKG_NAME}_${deb_version}_${deb_arch}.deb\"
            "

        local deb_name="${DEB_PKG_NAME}_${deb_version}_${deb_arch}.deb"
        local deb_path="${out_abs}/${deb_name}"
        if [[ ! -f "${deb_path}" ]]; then
            log_error ".deb not produced for ${deb_arch} at ${deb_path}"
            exit 1
        fi
        local pkg_size
        pkg_size="$(du -h "${deb_path}" | cut -f1)"
        log_ok "  → ${deb_name} (${pkg_size})"
    done

    echo
    log_ok "Debian packages built!"
    echo
    echo -e "  ${BOLD}Version:${RESET}   ${deb_version}"
    echo -e "  ${BOLD}Output:${RESET}    ${out_abs}/"
    echo
    local sep="────────────────────────────────────────────────────────────"
    echo -e "${GREEN}${BOLD}${sep}${RESET}"
    echo -e "${GREEN}${BOLD}  📦  Installation packages:${RESET}"
    for deb_arch in "${deb_archs[@]}"; do
        local f="${out_abs}/${DEB_PKG_NAME}_${version}_${deb_arch}.deb"
        [[ -f "${f}" ]] && echo -e "${GREEN}${BOLD}      $(basename "${f}")${RESET}"
    done
    echo -e "${GREEN}${BOLD}${sep}${RESET}"
    echo
    echo -e "${DIM}Install with:  sudo dpkg -i ${out_abs}/${DEB_PKG_NAME}_${version}_<arch>.deb${RESET}"
}

# -----------------------------------------------------------------------------
# RPM package build (RHEL/Rocky/Alma/Fedora)
# -----------------------------------------------------------------------------

readonly RPM_DIR="packaging/rpm"
readonly RPM_SPEC="${RPM_DIR}/hsync-desktop.spec"
readonly RPM_PKG_NAME="hsync-desktop"
readonly RPM_OUTPUT_DIR="${OUTPUT_BASE}/rpm"
readonly RPM_BUILD_DIR="${BUILD_DIR}/rpm"
readonly RPM_ALL_BUILD_DIR="${BUILD_DIR}/rpm-all"
readonly RPM_BUILDER_IMAGE_PREFIX="hsync-desktop-rpm-builder"

# Stage a buildroot for rpmbuild: Debian payload (usr/share .desktop + icons) +
# the PyInstaller --onedir bundle under /usr/lib/hsync-desktop + /usr/bin
# symlink + gzipped man page. No systemd unit and no /etc conffile.
# $1 = stage_dir   $2 = built onedir dir
_stage_rpm_buildroot() {
    local stage_dir="$1" built_dir="$2"
    rm -rf "${stage_dir}"
    mkdir -p "${stage_dir}"

    local item
    for item in "${DEB_SRC_DATA}"/*; do
        local bn
        bn="$(basename "${item}")"
        if [[ "${bn}" == "DEBIAN" || "${bn}" == "Dockerfile.builder" ]]; then
            continue
        fi
        cp -a "${item}" "${stage_dir}/"
    done

    mkdir -p "${stage_dir}/usr/lib"
    cp -a "${built_dir}" "${stage_dir}/usr/lib/${APP_NAME}"
    chmod 0755 "${stage_dir}/usr/lib/${APP_NAME}/${APP_NAME}"

    mkdir -p "${stage_dir}/usr/bin"
    ln -sf "../lib/${APP_NAME}/${APP_NAME}" "${stage_dir}/usr/bin/${APP_NAME}"

    find "${stage_dir}/usr" -type d -exec chmod 0755 {} + 2>/dev/null || true
    find "${stage_dir}/usr" -type f -exec chmod 0644 {} + 2>/dev/null || true
    chmod 0755 "${stage_dir}/usr/lib/${APP_NAME}/${APP_NAME}"
    _restore_bundled_client_exec "${stage_dir}"
    local man="${stage_dir}/usr/share/man/man1/${APP_NAME}.1"
    if [[ -f "${man}" ]]; then
        gzip -n -9 -f "${man}"
    fi
}

# Render the spec with the resolved RPM version and echo its path.
# $1 = version (SemVer)   $2 = work dir
_render_rpm_spec() {
    local version="$1" work_dir="$2"
    local rpm_version rendered
    rpm_version="$(_semver_to_rpm "${version}")"
    rendered="${work_dir}/hsync-desktop.spec"
    sed "s/__VERSION__/${rpm_version}/g" "${RPM_SPEC}" > "${rendered}"
    printf '%s' "${rendered}"
}

# Build a .rpm package for the host architecture (native build, no Docker).
build_rpm() {
    local version rpm_arch
    version="$(get_version)"
    rpm_arch="$(_arch_to_rpm "${ARCH_NAME}")"

    log_step "Building ${RPM_PKG_NAME} v${version} for ${rpm_arch} (host build)..."

    check_prerequisites
    if ! command -v rpmbuild >/dev/null 2>&1; then
        log_error "rpmbuild is required for the rpm target."
        log_info "Install it with: dnf install rpm-build (RHEL/Rocky/Fedora)."
        exit 1
    fi
    mkdir -p "${RPM_OUTPUT_DIR}" "${RPM_BUILD_DIR}"

    local onedir_dist="${RPM_BUILD_DIR}/pyinstaller"
    mkdir -p "${onedir_dist}"

    # Self-contained: bundle the host-arch hsync-client so the .rpm does not
    # depend on a separate hsync-client package (verified against HSYNC_VERSION).
    local -a add_data_args=()
    _collect_add_data_args "${CLIENT_BINARY}"
    _require_bundled_client
    add_data_args=("${ADD_DATA_ARGS[@]}")

    log_step "Compiling ${APP_NAME} with PyInstaller (--onedir)..."
    LC_ALL=C.UTF-8 LANG=C.UTF-8 PYTHONWARNINGS=ignore "${PYINSTALLER}" \
        --distpath "${onedir_dist}" \
        --workpath "${RPM_BUILD_DIR}/work" \
        --strip \
        $(_onedir_pyi_flags) \
        "${add_data_args[@]}" \
        "${ENTRY_POINT}"

    local built_dir="${onedir_dist}/${APP_NAME}"
    [[ -d "${built_dir}" ]] || { log_error "PyInstaller --onedir output not found at ${built_dir}"; exit 1; }

    _stage_rpm_buildroot "${RPM_BUILD_DIR}/pkg" "${built_dir}"
    local stage_dir
    stage_dir="$(cd "${RPM_BUILD_DIR}/pkg" && pwd)"
    local spec_path
    spec_path="$(_render_rpm_spec "${version}" "${RPM_BUILD_DIR}")"

    log_step "Building .rpm with rpmbuild..."
    local spec_abs topdir_abs dbpath_abs
    spec_abs="$(cd "$(dirname "${spec_path}")" && pwd)/$(basename "${spec_path}")"
    mkdir -p "${RPM_BUILD_DIR}/rpmbuild" "${RPM_BUILD_DIR}/rpmdb"
    topdir_abs="$(cd "${RPM_BUILD_DIR}/rpmbuild" && pwd)"
    dbpath_abs="$(cd "${RPM_BUILD_DIR}/rpmdb" && pwd)"
    rpmbuild -bb "${spec_abs}" \
        --define "pkgdir ${stage_dir}" \
        --define "_topdir ${topdir_abs}" \
        --define "_dbpath ${dbpath_abs}"

    local rpm_file
    rpm_file="$(ls "${RPM_BUILD_DIR}/rpmbuild/RPMS"/*/*.rpm 2>/dev/null | head -1)"
    [[ -n "${rpm_file}" ]] || { log_error "rpmbuild produced no package"; exit 1; }
    mv -f "${rpm_file}" "${RPM_OUTPUT_DIR}/"

    rm -rf "${RPM_BUILD_DIR}/work" "${RPM_BUILD_DIR}/pyinstaller" "${APP_NAME}.spec" 2>/dev/null || true

    local rpm_name rpm_path size
    rpm_name="$(basename "$(ls "${RPM_OUTPUT_DIR}"/*.rpm 2>/dev/null | head -1)")"
    rpm_path="${RPM_OUTPUT_DIR}/${rpm_name}"
    size="$(du -h "${rpm_path}" | cut -f1)"
    echo
    log_ok "RPM package built!"
    echo
    echo -e "  ${BOLD}Package:${RESET}  ${rpm_name}"
    echo -e "  ${BOLD}Arch:${RESET}     ${rpm_arch}"
    echo -e "  ${BOLD}Size:${RESET}     ${size}"
    echo
    echo -e "${DIM}Install with:${RESET}"
    echo -e "${DIM}  sudo dnf install ${rpm_path}${RESET}"
}

# Build .rpm packages for x86_64 and aarch64 via Docker + qemu on the Rocky 9
# baseline (separate binary build from the Debian one).
build_rpm_all() {
    local version
    version="$(get_version)"

    log_step "Building ${RPM_PKG_NAME} v${version} for x86_64 and aarch64..."

    if ! command -v docker >/dev/null 2>&1; then
        log_error "docker is required for the rpm-all target."
        exit 1
    fi
    mkdir -p "${RPM_OUTPUT_DIR}"

    local repo_root
    repo_root="$(cd "${SCRIPT_DIR}/.." && pwd)"
    local out_abs
    out_abs="$(cd "${RPM_OUTPUT_DIR}" && pwd)"

    ensure_qemu_binfmt qemu-aarch64

    local -A arch_docker_platform
    arch_docker_platform["x86_64"]="linux/amd64"
    arch_docker_platform["aarch64"]="linux/arm64"

    local -a rpm_archs=("x86_64" "aarch64")

    local pyinstaller_flags="$(_onedir_pyi_flags) --strip"
    # UI files and icons; the client is built and staged inside each container
    # (same arch and distro, so the bundled engine shares the GUI's glibc).
    _collect_add_data_args ""

    for rpm_arch in "${rpm_archs[@]}"; do
        local docker_platform="${arch_docker_platform[${rpm_arch}]}"
        local builder_tag="${RPM_BUILDER_IMAGE_PREFIX}:${rpm_arch}"
        local arch_build_dir="${RPM_ALL_BUILD_DIR}/${rpm_arch}"
        local bin_dir="${arch_build_dir}/pyinstaller"
        local work_dir="${arch_build_dir}/work"
        mkdir -p "${bin_dir}" "${work_dir}"

        # The container builds and stages this arch's client; map the rpm arch to
        # the client's Linux platform directory.
        local client_platform
        case "${rpm_arch}" in
            x86_64) client_platform="linux-amd64" ;;
            aarch64) client_platform="linux-arm64" ;;
            *) log_error "unsupported rpm arch: ${rpm_arch}"; exit 1 ;;
        esac
        local add_data="--add-data=hsync_desktop/bin/hsync:hsync_desktop/bin"
        local _arg
        for _arg in "${ADD_DATA_ARGS[@]}"; do
            add_data+=" ${_arg}"
        done

        echo
        log_step "─── ${rpm_arch} build ───────────────────────────────────────"

        log_step "Building Docker image ${builder_tag}..."
        DOCKER_BUILDKIT=1 docker build \
            --platform "${docker_platform}" \
            --build-arg TARGET_PLATFORM="${docker_platform}" \
            -t "${builder_tag}" \
            -f "${RPM_DIR}/Dockerfile.builder" \
            "${RPM_DIR}"

        log_step "Compiling ${rpm_arch} binary inside container..."
        docker run --rm \
            --platform "${docker_platform}" \
            -u "$(id -u):$(id -g)" \
            -e HOME=/tmp -e XDG_CACHE_HOME=/tmp \
            -v "${repo_root}:/repo" \
            -w /repo/hsync-desktop \
            -e LC_ALL=C -e PYTHONWARNINGS=ignore \
            -e PIP_DEFAULT_TIMEOUT=300 -e PIP_RETRIES=10 \
            -e POETRY_REQUESTS_TIMEOUT=300 \
            -e HSYNC_VERSION="${version}" \
            "${builder_tag}" \
            bash -c "
                set -euo pipefail
                poetry config virtualenvs.in-project true
                poetry config installer.max-workers 4

                # Build the matching-arch, matching-distro hsync-client from the
                # sibling checkout so the bundled engine shares the GUI's glibc.
                (
                    cd /repo/hsync-client
                    client_ok=0
                    for attempt in 1 2 3; do
                        if poetry install --no-root --without dev; then client_ok=1; break; fi
                        echo \"client poetry install attempt \${attempt}/3 failed, retrying in 10s...\" >&2
                        sleep 10
                    done
                    [ \"\${client_ok}\" -eq 1 ] || { echo 'client poetry install failed after 3 attempts' >&2; exit 1; }
                    ./compile.sh -c
                )
                mkdir -p hsync_desktop/bin
                cp \"/repo/hsync-client/dist/${client_platform}/hsync\" hsync_desktop/bin/hsync

                install_ok=0
                for attempt in 1 2 3; do
                    if poetry install --only main,build; then install_ok=1; break; fi
                    echo \"poetry install attempt \${attempt}/3 failed, retrying in 10s...\" >&2
                    sleep 10
                done
                [ \"\${install_ok}\" -eq 1 ] || { echo 'poetry install failed after 3 attempts' >&2; exit 1; }
                HSYNC_PREFER_PATH_PYINSTALLER=1 poetry run pyinstaller \
                    ${pyinstaller_flags} \
                    ${add_data} \
                    --distpath ${bin_dir} \
                    --workpath ${work_dir} \
                    ${ENTRY_POINT}
            "

        rm -f "${APP_NAME}.spec" 2>/dev/null || true

        local built_dir="${bin_dir}/${APP_NAME}"
        [[ -d "${built_dir}" ]] || { log_error "${rpm_arch} build directory not produced at ${built_dir}"; exit 1; }
        log_ok "${rpm_arch} binary ready ($(du -sh "${built_dir}" | cut -f1))"

        local stage_dir="${arch_build_dir}/pkg"
        local spec_path
        spec_path="$(_render_rpm_spec "${version}" "${arch_build_dir}")"
        _stage_rpm_buildroot "${stage_dir}" "${built_dir}"
        stage_dir="$(cd "${stage_dir}" && pwd)"
        local spec_abs
        spec_abs="$(cd "$(dirname "${spec_path}")" && pwd)/$(basename "${spec_path}")"

        log_step "Building .rpm for ${rpm_arch}..."
        docker run --rm \
            --platform "${docker_platform}" \
            -u "$(id -u):$(id -g)" \
            -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" \
            -v "${stage_dir}:/pkg:ro" \
            -v "${spec_abs}:/hsync.spec:ro" \
            -v "${out_abs}:/out" \
            -w /tmp \
            "${builder_tag}" \
            bash -c "
                set -euo pipefail
                topdir=/tmp/rpmbuild-\$\$
                mkdir -p \"\${topdir}/db\"
                rpmbuild -bb /hsync.spec \
                    --define 'pkgdir /pkg' \
                    --define \"_topdir \${topdir}\" \
                    --define \"_dbpath \${topdir}/db\"
                out_rpm=\$(ls \${topdir}/RPMS/*/*.rpm | head -1)
                cp \"\${out_rpm}\" /out/
                chmod 0644 \"/out/\$(basename \"\${out_rpm}\")\"
                chown \"\${HOST_UID}:\${HOST_GID}\" \"/out/\$(basename \"\${out_rpm}\")\"
                rm -rf \"\${topdir}\"
            "

        local rpm_file
        rpm_file="$(ls "${out_abs}/${RPM_PKG_NAME}-"*".${rpm_arch}.rpm" 2>/dev/null | head -1)"
        [[ -n "${rpm_file}" ]] || { log_error ".rpm not produced for ${rpm_arch}"; exit 1; }
        log_ok "  → $(basename "${rpm_file}") ($(du -h "${rpm_file}" | cut -f1))"
    done

    echo
    log_ok "RPM packages built!"
    echo
    echo -e "  ${BOLD}Version:${RESET}   ${version}"
    echo -e "  ${BOLD}Output:${RESET}    ${out_abs}/"
    echo
    echo -e "${DIM}Install with:  sudo dnf install ${out_abs}/${RPM_PKG_NAME}-${version}-1.el9.<arch>.rpm${RESET}"
}

# -----------------------------------------------------------------------------
# AppImage target (portable Linux x86_64)
# -----------------------------------------------------------------------------

# Download appimagetool once and cache it under packaging/appimage/.cache/.
_appimage_ensure_appimagetool() {
    if [[ -x "${APPIMAGE_TOOL}" ]]; then
        return 0
    fi
    mkdir -p "${APPIMAGE_CACHE_DIR}"
    log_step "Downloading appimagetool (cached after first run)..."
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL -o "${APPIMAGE_TOOL}" "${APPIMAGE_TOOL_URL}"
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O "${APPIMAGE_TOOL}" "${APPIMAGE_TOOL_URL}"
    else
        log_error "curl or wget is required to download appimagetool."
        exit 1
    fi
    chmod +x "${APPIMAGE_TOOL}"
}

# Build a self-contained .AppImage for Linux x86_64.
#
# The AppImage wraps the PyInstaller onefile binary (with the client engine
# bundled) in an AppDir and runs appimagetool. PyInstaller already bundles Qt
# and Python, so linuxdeploy's dependency scan (and its Qt plugin) is not used:
# it would try to bundle the system glibc, which is exactly what an AppImage
# must NOT do.
#
# Output: dist/appimage/hsync-desktop-<ver>-x86_64.AppImage
build_appimage() {
    local version
    version="$(get_version)"

    if [[ "${OS_NAME}" != "linux" || "${ARCH_NAME}" != "amd64" ]]; then
        log_error "The appimage target is supported only on Linux x86_64 (got ${PLATFORM})."
        log_info "On other platforms use the native binary, the .deb/.rpm package, or the rpi binary."
        exit 1
    fi

    log_step "Building ${APP_NAME} v${version} AppImage (x86_64)..."

    [[ -x "${PYINSTALLER}" ]] || { log_error "PyInstaller not found. Run 'poetry install'."; exit 1; }

    local work_dir="${BUILD_DIR}/appimage"
    local bin_dir="${work_dir}/bin"
    local appdir="${work_dir}/${APP_NAME}.AppDir"
    rm -rf "${work_dir}"
    mkdir -p "${bin_dir}" "${appdir}"

    # --- 1. onefile binary with the client engine bundled --------------------
    local -a add_data_args=()
    _collect_add_data_args "${CLIENT_BINARY}"
    _require_bundled_client
    add_data_args=("${ADD_DATA_ARGS[@]}")

    LC_ALL=C.UTF-8 LANG=C.UTF-8 PYTHONWARNINGS=ignore "${PYINSTALLER}" \
        --strip \
        --distpath "${bin_dir}" \
        $(_onefile_pyi_flags) \
        "${add_data_args[@]}" \
        "${ENTRY_POINT}"
    # PyInstaller writes the generated .spec to the CWD; remove it (the add-data
    # paths above are resolved against the CWD, so --specpath cannot be used).
    rm -f "${APP_NAME}.spec"

    local bin="${bin_dir}/${APP_NAME}"
    [[ -f "${bin}" ]] || { log_error "AppImage payload not found at ${bin}"; exit 1; }

    # --- 2. AppDir layout (appimagetool conventions) -------------------------
    mkdir -p "${appdir}/usr/bin" \
        "${appdir}/usr/share/applications" \
        "${appdir}/usr/share/icons/hicolor/1024x1024/apps" \
        "${appdir}/usr/share/icons/hicolor/scalable/apps"
    install -m 0755 "${bin}" "${appdir}/usr/bin/${APP_NAME}"
    install -m 0644 "${DEB_ICON_PNG}" "${appdir}/usr/share/icons/hicolor/1024x1024/apps/${APP_NAME}.png"
    install -m 0644 "${DEB_ICON_SVG}" "${appdir}/usr/share/icons/hicolor/scalable/apps/${APP_NAME}.svg"
    # appimagetool requires the .desktop and a matching icon at the AppDir root.
    install -m 0644 "${DEB_ICON_PNG}" "${appdir}/${APP_NAME}.png"
    sed -e "s|^Exec=.*|Exec=${APP_NAME}|" "${DEB_DESKTOP_FILE}" > "${appdir}/${APP_NAME}.desktop"
    install -m 0644 "${appdir}/${APP_NAME}.desktop" "${appdir}/usr/share/applications/${APP_NAME}.desktop"
    # AppRun (AppImage entry point) execs the bundled application.
    ln -sf "usr/bin/${APP_NAME}" "${appdir}/AppRun"

    # --- 3. appimagetool -----------------------------------------------------
    _appimage_ensure_appimagetool
    mkdir -p "${APPIMAGE_OUTPUT_DIR}"
    local out_abs image
    out_abs="$(cd "${APPIMAGE_OUTPUT_DIR}" && pwd)"
    image="${out_abs}/${APP_NAME}-${version}-x86_64.AppImage"

    log_step "Packaging AppImage with appimagetool..."
    # APPIMAGE_EXTRACT_AND_RUN avoids a hard FUSE dependency (CI, containers).
    APPIMAGE_EXTRACT_AND_RUN=1 ARCH=x86_64 \
        "${APPIMAGE_TOOL}" --no-appstream "${appdir}" "${image}"

    [[ -f "${image}" ]] || { log_error "appimagetool produced no AppImage"; exit 1; }
    rm -rf "${work_dir}"

    local size
    size="$(du -h "${image}" | cut -f1)"
    echo
    log_ok "AppImage built!"
    echo
    echo -e "  ${BOLD}Image:${RESET}    $(basename "${image}")"
    echo -e "  ${BOLD}Platform:${RESET} linux-x86_64"
    echo -e "  ${BOLD}Size:${RESET}     ${size}"
    echo -e "  ${BOLD}Version:${RESET}  ${version}"
    echo
    echo -e "${DIM}Run with:${RESET}"
    echo -e "${DIM}  chmod +x ${image} && ${image}${RESET}"
    echo -e "${DIM}  # without FUSE: ${image} --appimage-extract-and-run${RESET}"
}

# -----------------------------------------------------------------------------
# macOS .app + .dmg target
# -----------------------------------------------------------------------------

# SemVer -> CFBundleVersion: a dotted numeric string (prerelease and build
# metadata stripped, padded to three components).
_macos_numeric_version() {
    local v="${1%%-*}"
    v="${v%%+*}"
    local major minor patch
    IFS='.' read -r major minor patch <<< "${v}"
    printf '%s.%s.%s' "${major:-0}" "${minor:-0}" "${patch:-0}"
}

# Build a .icns from the 1024x1024 PNG using sips + iconutil (macOS only).
# $1 = output .icns  $2 = source PNG  $3 = iconset working dir
_macos_build_icns() {
    local out="$1" src="$2" iconset="$3"
    rm -rf "${iconset}"
    mkdir -p "${iconset}"
    local size double
    for size in 16 32 128 256 512; do
        sips -z "${size}" "${size}" "${src}" --out "${iconset}/icon_${size}x${size}.png" >/dev/null
        double=$((size * 2))
        sips -z "${double}" "${double}" "${src}" --out "${iconset}/icon_${size}x${size}@2x.png" >/dev/null
    done
    iconutil -c icns "${iconset}" -o "${out}"
}

# Merge packaging/macos/Info.plist (placeholders substituted) into the .app's
# generated Info.plist, preserving every other key PyInstaller wrote.
# $1 = .app path  $2 = rendered template path
_macos_apply_info_plist() {
    local app="$1" rendered="$2"
    "${VENV_DIR}/bin/python" - "${app}/Contents/Info.plist" "${rendered}" <<'PY'
import plistlib
import sys

target, template = sys.argv[1], sys.argv[2]
with open(target, "rb") as fh:
    base = plistlib.load(fh)
with open(template, "rb") as fh:
    base.update(plistlib.load(fh))
with open(target, "wb") as fh:
    plistlib.dump(base, fh)
PY
}

# Wrap a .app in a .dmg with the conventional /Applications symlink.
# $1 = .app path  $2 = output .dmg  $3 = staging dir
_macos_create_dmg() {
    local app="$1" image="$2" stage="$3"
    rm -rf "${stage}"
    mkdir -p "${stage}"
    # APFS clone (macOS 'cp -c') keeps the staged copy almost space-free; the
    # hdiutil temp image is the only real duplicate left. Fall back to a plain
    # copy on filesystems that do not support cloning.
    cp -cR "${app}" "${stage}/" 2>/dev/null || cp -R "${app}" "${stage}/"
    ln -s /Applications "${stage}/Applications"
    hdiutil create -volname "HSYNC" -srcfolder "${stage}" -ov -format UDZO "${image}" >/dev/null
}

# Build the macOS .app bundle and wrap it in a .dmg.
#
# macOS only: PyInstaller cannot produce a .app on another OS. One .app per host
# architecture (the bundled client engine is the matching per-arch binary); a
# universal2 .app would require a universal `lipo`-merged client, so per-arch
# dmgs are the supported form.
#
# The .app is unsigned: Gatekeeper needs the documented right-click / `xattr`
# workaround (docs/getting-started-macos.md).
# Output: dist/macos/hsync-desktop-<ver>-darwin-<arch>.dmg
build_dmg() {
    local version
    version="$(get_version)"

    if [[ "${OS_NAME}" != "darwin" ]]; then
        log_error "The dmg target is supported only on macOS (got ${PLATFORM})."
        log_info "PyInstaller cannot build a macOS .app on ${OS_NAME}."
        exit 1
    fi

    log_step "Building ${APP_NAME} v${version} macOS .app + .dmg (${ARCH_NAME})..."

    [[ -x "${PYINSTALLER}" ]] || { log_error "PyInstaller not found. Run 'poetry install'."; exit 1; }
    local tool
    for tool in sips iconutil hdiutil; do
        command -v "${tool}" >/dev/null 2>&1 || { log_error "${tool} not found (macOS only)"; exit 1; }
    done

    local work_dir="${BUILD_DIR}/macos"
    local dist_dir="${work_dir}/dist"
    rm -rf "${work_dir}"
    mkdir -p "${dist_dir}"

    # --- 1. icon + rendered Info.plist ---------------------------------------
    local icns="${work_dir}/${APP_NAME}.icns"
    _macos_build_icns "${icns}" "${DEB_ICON_PNG}" "${work_dir}/${APP_NAME}.iconset"

    local rendered_plist="${work_dir}/Info.plist"
    sed -e "s|__BUNDLE_ID__|${MACOS_BUNDLE_ID}|g" \
        -e "s|__VERSION__|${version}|g" \
        -e "s|__BUILD__|$(_macos_numeric_version "${version}")|g" \
        -e "s|__MIN_MACOS__|${MACOS_MIN_VERSION}|g" \
        "${MACOS_INFO_TEMPLATE}" > "${rendered_plist}"

    # --- 2. .app via PyInstaller (--windowed) --------------------------------
    local -a add_data_args=()
    _collect_add_data_args "${CLIENT_BINARY}"
    _require_bundled_client
    add_data_args=("${ADD_DATA_ARGS[@]}")

    LC_ALL=C.UTF-8 LANG=C.UTF-8 PYTHONWARNINGS=ignore "${PYINSTALLER}" \
        --windowed \
        --osx-bundle-identifier "${MACOS_BUNDLE_ID}" \
        --icon "${icns}" \
        --distpath "${dist_dir}" \
        --workpath "${work_dir}/pyinstaller" \
        $(_onefile_pyi_flags) \
        "${add_data_args[@]}" \
        "${ENTRY_POINT}"
    rm -f "${APP_NAME}.spec"

    local app="${dist_dir}/${APP_NAME}.app"
    [[ -d "${app}" ]] || { log_error "macOS .app not produced at ${app}"; exit 1; }

    _macos_apply_info_plist "${app}" "${rendered_plist}"

    # The PyInstaller workpath is no longer needed once the .app exists; drop it
    # before packaging so hdiutil has room for its temp image (the CI runners are
    # space-constrained and can otherwise hit ENOSPC).
    rm -rf "${work_dir}/pyinstaller"

    # --- 3. dmg --------------------------------------------------------------
    mkdir -p "${MACOS_OUTPUT_DIR}"
    local out_abs image
    out_abs="$(cd "${MACOS_OUTPUT_DIR}" && pwd)"
    image="${out_abs}/${APP_NAME}-${version}-darwin-${ARCH_NAME}.dmg"

    log_step "Packaging .dmg..."
    _macos_create_dmg "${app}" "${image}" "${work_dir}/dmg"
    [[ -f "${image}" ]] || { log_error "dmg not produced"; exit 1; }
    rm -rf "${work_dir}"

    local size
    size="$(du -h "${image}" | cut -f1)"
    echo
    log_ok "macOS .dmg built!"
    echo
    echo -e "  ${BOLD}Image:${RESET}    $(basename "${image}")"
    echo -e "  ${BOLD}Platform:${RESET} darwin-${ARCH_NAME}"
    echo -e "  ${BOLD}Size:${RESET}     ${size}"
    echo -e "  ${BOLD}Version:${RESET}  ${version}"
    echo
    echo -e "${DIM}The .app is unsigned: open the dmg, drag HSYNC to Applications, then${RESET}"
    echo -e "${DIM}right-click → Open the first time (or: xattr -dr com.apple.quarantine /Applications/HSYNC.app).${RESET}"
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

main() {
    local do_clean=false
    local target="native"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            -c|--clean)
                do_clean=true
                shift
                ;;
            -t|--target)
                [[ $# -ge 2 ]] || { log_error "--target requires a value"; exit 1; }
                target="$2"
                shift 2
                ;;
            -v|--version)
                [[ $# -ge 2 ]] || { log_error "--version requires a value"; exit 1; }
                VERSION_OVERRIDE="$2"
                shift 2
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                echo "Use --help for usage information."
                exit 1
                ;;
        esac
    done

    cd "${SCRIPT_DIR}"

    echo -e "${BOLD}HSYNC Desktop - Build${RESET}"
    echo -e "${DIM}─────────────────────${RESET}"
    echo

    case "${target}" in
        native)
            check_prerequisites
            if [[ "${do_clean}" == true ]]; then
                clean_artifacts
                echo
            fi
            build_binary
            ;;
        rpi)
            # Only pyproject.toml is required (poetry runs inside the container).
            if [[ ! -f "pyproject.toml" ]]; then
                log_error "pyproject.toml not found. Run from the project root."
                exit 1
            fi
            if [[ "${do_clean}" == true ]]; then
                log_step "Cleaning rpi artifacts..."
                rm -rf "${RPI_OUTPUT_DIR}"
                docker image rm -f "${RPI_BUILDER_IMAGE_PREFIX}:arm64" >/dev/null 2>&1 || true
                echo
            fi
            build_rpi
            ;;
        deb)
            check_prerequisites
            if [[ "${do_clean}" == true ]]; then
                log_step "Cleaning deb artifacts..."
                rm -rf "${DEB_OUTPUT_DIR}" "${DEB_BUILD_DIR}"
                echo
            fi
            build_deb
            ;;
        deb-all)
            # Only pyproject.toml is required (poetry runs inside the container).
            if [[ ! -f "pyproject.toml" ]]; then
                log_error "pyproject.toml not found. Run from the project root."
                exit 1
            fi
            if [[ "${do_clean}" == true ]]; then
                log_step "Cleaning deb-all artifacts..."
                rm -rf "${DEB_ALL_OUTPUT_DIR}" "${DEB_ALL_BUILD_DIR}"
                docker image rm -f \
                    "${DEB_ALL_BUILDER_IMAGE_PREFIX}:amd64" \
                    "${DEB_ALL_BUILDER_IMAGE_PREFIX}:arm64" >/dev/null 2>&1 || true
                echo
            fi
            build_deb_all
            ;;
        rpm)
            check_prerequisites
            if [[ "${do_clean}" == true ]]; then
                log_step "Cleaning rpm artifacts..."
                rm -rf "${RPM_OUTPUT_DIR}" "${RPM_BUILD_DIR}"
                echo
            fi
            build_rpm
            ;;
        rpm-all)
            if [[ ! -f "pyproject.toml" ]]; then
                log_error "pyproject.toml not found. Run from the project root."
                exit 1
            fi
            if [[ "${do_clean}" == true ]]; then
                log_step "Cleaning rpm-all artifacts..."
                rm -rf "${RPM_OUTPUT_DIR}" "${RPM_ALL_BUILD_DIR}"
                docker image rm -f \
                    "${RPM_BUILDER_IMAGE_PREFIX}:x86_64" \
                    "${RPM_BUILDER_IMAGE_PREFIX}:aarch64" >/dev/null 2>&1 || true
                echo
            fi
            build_rpm_all
            ;;
        appimage)
            check_prerequisites
            if [[ "${do_clean}" == true ]]; then
                log_step "Cleaning appimage artifacts..."
                rm -rf "${APPIMAGE_OUTPUT_DIR}" "${BUILD_DIR}/appimage"
                echo
            fi
            build_appimage
            ;;
        dmg)
            check_prerequisites
            if [[ "${do_clean}" == true ]]; then
                log_step "Cleaning dmg artifacts..."
                rm -rf "${MACOS_OUTPUT_DIR}" "${BUILD_DIR}/macos"
                echo
            fi
            build_dmg
            ;;
        *)
            log_error "Unknown target: ${target}"
            echo "Supported targets: native, deb, deb-all, rpm, rpm-all, appimage, dmg, rpi"
            exit 1
            ;;
    esac
}

main "$@"
