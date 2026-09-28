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
#                               rpi       Raspberry Pi OS 64-bit (arm64)
#                                         onefile binary via Docker
#   -v, --version VERSION   Override the version reported for the build
#                           (default: the pyproject.toml version). Also
#                           settable via the HSYNC_VERSION environment
#                           variable.
#   -h, --help              Show this help message
#
# Requirements:
#   - native target: Python virtual environment (.venv) with dependencies
#     installed; run 'poetry install' before first build
#   - rpi target: Docker with qemu-user-static (binfmt) configured (used for
#     arm64 emulation on amd64 hosts)
#
# Raspberry Pi (rpi) target:
#   The rpi target builds the arm64 (64-bit) Raspberry Pi OS binary ONLY. The
#   Qt GUI cannot be built for 32-bit armhf because PySide6 publishes no armv7
#   Linux wheels; armhf is therefore not supported for the desktop GUI. This is
#   intentional and not an error: the script prints an informational note and
#   produces dist/rpi/arm64/hsync-desktop.
#
# Output:
#   native:
#     - dist/<os>-<arch>/hsync-desktop[.exe]   Standalone platform-aware
#       executable
#       e.g. dist/linux-amd64/hsync-desktop, dist/darwin-arm64/hsync-desktop
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
readonly PYINSTALLER="${VENV_DIR}/bin/pyinstaller"
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

# -----------------------------------------------------------------------------
# Colors (disabled if not a terminal)
# -----------------------------------------------------------------------------

if [[ -t 1 ]]; then
    readonly RED='\033[0;31m'
    readonly GREEN='\033[0;32m'
    readonly YELLOW='\033[0;33m'
    readonly BLUE='\033[0;34m'
    readonly CYAN='\033[0;36m'
    readonly BOLD='\033[1m'
    readonly DIM='\033[2m'
    readonly RESET='\033[0m'
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
                            Supported: native, rpi
    -v, --version VERSION   Override the version reported for the build
                            (default: pyproject.toml). Also settable via
                            HSYNC_VERSION.
    -h, --help              Show this help message

${BOLD}Targets:${RESET}
    native    Host OS / arch PyInstaller onefile binary.
    rpi       Raspberry Pi OS 64-bit (arm64) onefile binary via Docker.
              Only arm64 is built: the Qt GUI cannot be built for 32-bit
              armhf because PySide6 publishes no armv7 Linux wheels.

${BOLD}Examples:${RESET}
    ./compile.sh                    # Native host build
    ./compile.sh --clean            # Clean and rebuild
    ./compile.sh --target native    # Explicit native build
    ./compile.sh --target rpi       # Raspberry Pi OS 64-bit (arm64)

${BOLD}Output:${RESET}
    native:
        ${OUTPUT_DIR}/${APP_NAME}${BIN_EXT}   Standalone executable (platform: ${PLATFORM})
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

# Emit the PyInstaller --add-data arguments shared by the native and rpi builds.
# When the given client binary exists it is staged into hsync_desktop/bin/ and
# bundled; otherwise the build warns and the desktop falls back to searching
# PATH for 'hsync' at runtime. UI files and icons are always bundled.
# $1 = client binary path (empty to skip client bundling entirely)
_add_data_args() {
    local client_binary="${1:-}"
    local add_data_args=()

    if [[ -n "${client_binary}" && -f "${client_binary}" ]]; then
        log_step "Bundling hsync-client binary..."
        mkdir -p hsync_desktop/bin
        cp "${client_binary}" hsync_desktop/bin/hsync
        chmod +x hsync_desktop/bin/hsync
        log_ok "Bundled hsync-client"
        add_data_args+=("--add-data=hsync_desktop/bin/hsync:hsync_desktop/bin")
    elif [[ -n "${client_binary}" ]]; then
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
    done < <(_add_data_args "${1:-}")
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
    _collect_add_data_args "${RPI_CLIENT_BINARY}"
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
            poetry install --only main --with build
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
        *)
            log_error "Unknown target: ${target}"
            echo "Supported targets: native, rpi"
            exit 1
            ;;
    esac
}

main "$@"
