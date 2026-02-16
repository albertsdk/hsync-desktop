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
#   -c, --clean    Clean build artifacts before building
#   -h, --help     Show this help message
#
# Requirements:
#   - Python virtual environment (.venv) with dependencies installed
#   - Run 'poetry install' before first build
#
# Output:
#   - dist/hsync-desktop   Standalone executable binary
#
# Author: Alberto Basso
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

readonly APP_NAME="hsync-desktop"
readonly ENTRY_POINT="hsync_desktop/main.py"
readonly OUTPUT_DIR="dist"
readonly BUILD_DIR="build"
readonly VENV_DIR=".venv"
readonly PYINSTALLER="${VENV_DIR}/bin/pyinstaller"
readonly CLIENT_BINARY="../hsync-client/dist/hsync"

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
# Logging Functions
# -----------------------------------------------------------------------------

log_info() { echo -e "${BLUE}ℹ${RESET} $*"; }
log_ok()   { echo -e "${GREEN}✓${RESET} $*"; }
log_warn() { echo -e "${YELLOW}⚠${RESET} $*"; }
log_error(){ echo -e "${RED}✕${RESET} $*" >&2; }
log_step() { echo -e "${CYAN}→${RESET} ${BOLD}$*${RESET}"; }

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

show_help() {
    cat << EOF
${BOLD}HSYNC Desktop - Build Script${RESET}

${BOLD}Usage:${RESET}
    ./compile.sh [options]

${BOLD}Options:${RESET}
    -c, --clean    Clean build artifacts before building
    -h, --help     Show this help message

${BOLD}Examples:${RESET}
    ./compile.sh           # Build the binary
    ./compile.sh --clean   # Clean and rebuild

${BOLD}Output:${RESET}
    ${OUTPUT_DIR}/${APP_NAME}   Standalone executable
EOF
}

clean_artifacts() {
    log_step "Cleaning build artifacts..."
    local cleaned=0
    for d in "${BUILD_DIR}" "${OUTPUT_DIR}"; do
        [[ -d "${d}" ]] && rm -rf "${d}" && ((cleaned++))
    done
    [[ -f "${APP_NAME}.spec" ]] && rm -f "${APP_NAME}.spec" && ((cleaned++))
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    if [[ ${cleaned} -gt 0 ]]; then log_ok "Cleaned ${cleaned} artifact(s)"
    else log_info "No artifacts to clean"; fi
}

check_prerequisites() {
    [[ -f "pyproject.toml" ]] || { log_error "pyproject.toml not found."; exit 1; }
    [[ -d ".venv" ]]          || { log_error "Virtual env not found. Run 'poetry install'."; exit 1; }
    [[ -f "${ENTRY_POINT}" ]] || { log_error "Entry point not found: ${ENTRY_POINT}"; exit 1; }
}

get_version() {
    grep -E '^version\s*=' pyproject.toml | head -1 | sed 's/.*"\(.*\)".*/\1/'
}

bundle_client() {
    if [[ -f "${CLIENT_BINARY}" ]]; then
        log_step "Bundling hsync-client binary..."
        mkdir -p hsync_desktop/bin
        cp "${CLIENT_BINARY}" hsync_desktop/bin/hsync
        chmod +x hsync_desktop/bin/hsync
        log_ok "Bundled hsync-client"
        echo "--add-data=hsync_desktop/bin/hsync:hsync_desktop/bin"
    else
        log_warn "hsync-client binary not found at ${CLIENT_BINARY}"
        log_info "Desktop will search PATH for 'hsync' at runtime"
        echo ""
    fi
}

build_binary() {
    local version
    version="$(get_version)"
    log_step "Building ${APP_NAME} v${version}..."

    [[ -x "${PYINSTALLER}" ]] || { log_error "PyInstaller not found. Run 'poetry install'."; exit 1; }

    local add_data
    add_data="$(bundle_client)"

    local extra_args=()
    [[ -n "${add_data}" ]] && extra_args+=("${add_data}")

    LC_ALL=C PYTHONWARNINGS=ignore "${PYINSTALLER}" \
        --clean --onefile --strip \
        --name "${APP_NAME}" \
        --log-level ERROR \
        --hidden-import "PySide6.QtCore" \
        --hidden-import "PySide6.QtGui" \
        --hidden-import "PySide6.QtWidgets" \
        --exclude-module "pytest" \
        --exclude-module "tkinter" \
        --exclude-module "unittest" \
        --exclude-module "pip" \
        --exclude-module "setuptools" \
        "${extra_args[@]}" \
        "${ENTRY_POINT}"

    if [[ -f "${OUTPUT_DIR}/${APP_NAME}" ]]; then
        local size
        size="$(du -h "${OUTPUT_DIR}/${APP_NAME}" | cut -f1)"

        # Clean up temp files
        rm -rf "${BUILD_DIR}" "${APP_NAME}.spec" 2>/dev/null || true

        echo
        log_ok "Build successful!"
        echo
        echo -e "  ${BOLD}Binary:${RESET}  ${OUTPUT_DIR}/${APP_NAME}"
        echo -e "  ${BOLD}Size:${RESET}    ${size}"
        echo -e "  ${BOLD}Version:${RESET} ${version}"
        echo
        echo -e "${DIM}Run with: ./${OUTPUT_DIR}/${APP_NAME}${RESET}"
    else
        log_error "Build failed: output binary not found"
        exit 1
    fi
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

main() {
    local do_clean=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            -c|--clean) do_clean=true; shift ;;
            -h|--help)  show_help; exit 0 ;;
            *)          log_error "Unknown option: $1"; exit 1 ;;
        esac
    done

    cd "${SCRIPT_DIR}"

    echo -e "${BOLD}HSYNC Desktop - Build${RESET}"
    echo -e "${DIM}─────────────────────${RESET}"
    echo

    check_prerequisites
    [[ "${do_clean}" == true ]] && { clean_artifacts; echo; }
    build_binary
}

main "$@"
