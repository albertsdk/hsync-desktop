#!/usr/bin/env bash
#
# Runtime dependency computation for the hsync-desktop .deb payload.
#
# Sourced by compile.sh for the host `deb` target and mounted into the
# deb-all builder container, where it must run with the target distro's
# tooling: the runner's objdump has no aarch64 target, so it cannot read the
# arm64 payload at all, and ldconfig/dpkg -S must resolve the target distro's
# package names rather than the runner's.
#
# Expects APP_NAME and DEB_PKG_NAME in the environment, plus objdump,
# ldconfig, dpkg and dpkg-shlibdeps on PATH.
#
# Consumers: compile.sh::build_deb (host), compile.sh::build_deb_all (container).

# compile.sh defines these log helpers; when sourced into a bare container
# shell, fall back to plain lines.
if ! declare -F log_step >/dev/null 2>&1; then
    log_step() { printf '%s\n' "$*"; }
    log_warn() { printf '%s\n' "$*" >&2; }
fi

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
        # Canonicalise before dpkg -S: on a merged-/usr system (Debian) ldconfig
        # reports /lib/... which dpkg does not match, while Ubuntu reports the
        # /usr/lib/... form the package records.
        pkg="$(dpkg -S "$(readlink -f "${path}")" 2>/dev/null | cut -d: -f1)"
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
