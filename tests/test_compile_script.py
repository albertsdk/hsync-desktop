"""Guard for the container build commands in ``../compile.sh``.

The ``build`` group (PyInstaller) must be requested with the syntax Poetry
honours. With Poetry 2.x — 2.3.2 is the version pinned in
``packaging/deb/Dockerfile.builder`` — ``--only`` prunes every group not named in
its list and a co-present ``--with`` is ignored, so
``poetry install --only main --with build`` left PyInstaller out of the
container venv and the cross-build targets (``rpi``, ``deb-all``) aborted.
A white-box guard on the script text is used because exercising the real
cross-build needs Docker, qemu and network access.

Consumers: hsync-desktop maintainers (regression guard).
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

COMPILE_SH = Path(__file__).resolve().parents[1] / "compile.sh"

# The historical regression: Poetry 2.x ignores `--with` next to `--only`.
_BROKEN = "poetry install --only main --with build"
_FIXED = "poetry install --only main,build"


def _script() -> str:
    return COMPILE_SH.read_text(encoding="utf-8")


def _poetry_install_lines() -> list[str]:
    return [line.strip() for line in _script().splitlines() if "poetry install" in line]


def _build_group_requested(line: str) -> bool:
    """True when ``line`` installs the ``build`` group under Poetry 2.x rules."""
    only = re.search(r"--only\s+([^\s;]+)", line)
    if only:
        # Inside --only the group list is exhaustive: --with cannot re-add it.
        return "build" in only.group(1).split(",")
    return "--without build" not in line and "--without=build" not in line


def test_guard_rejects_the_pruned_build_group() -> None:
    """The guard must fail on the pre-fix form and pass on the fixed one."""
    assert not _build_group_requested(_BROKEN)
    assert _build_group_requested(_FIXED)
    # The `;`-terminated form used inside the container retry loop.
    assert not _build_group_requested("if poetry install --only main --with build; then :; fi")
    assert _build_group_requested("if poetry install --only main,build; then :; fi")


def test_every_container_build_installs_the_build_group() -> None:
    lines = _poetry_install_lines()
    assert lines, "no 'poetry install' invocation found in compile.sh"
    for line in lines:
        assert _build_group_requested(line), f"build group not installed: {line}"


def test_container_workdir_is_the_poetry_project_root() -> None:
    """The relative artifact paths need the project to sit at the repo root.

    hsync-bootnode hit the opposite case: its Poetry project lives in ``python/``,
    so the container workdir was one level below the repository root and the
    relative ``build/deb-all/...`` distpath landed in ``python/build/``. If this
    project ever moves into a subdirectory, the container workdir must be
    remounted and the artifact paths made absolute.
    """
    assert "-w /repo/hsync-desktop" in _script()
    assert (COMPILE_SH.parent / "pyproject.toml").is_file()


def test_rpm_version_mapping_is_registered() -> None:
    """RPM >= 4.10 uses ``~`` for "sorts before everything"; ``_semver_to_rpm``
    must delegate to ``_semver_to_debian`` rather than re-encode the rule."""
    script = _script()
    assert "_semver_to_rpm()" in script
    assert '_semver_to_debian "$1"' in script


def test_rpm_arch_mapping_is_64_bit_only() -> None:
    """RHEL/Rocky is 64-bit only: only x86_64 and aarch64 are mapped."""
    script = _script()
    assert 'x86_64|amd64)   echo "x86_64"' in script
    assert 'aarch64|arm64)  echo "aarch64"' in script


def test_rpm_targets_are_registered_in_dispatch() -> None:
    """``rpm`` and ``rpm-all`` must be wired into main() and help."""
    script = _script()
    assert "rpm)" in script
    assert "rpm-all)" in script
    assert "Supported targets:" in script
    assert "rpm-all" in script


def test_appimage_target_is_registered() -> None:
    """The appimage target wraps the onefile binary with appimagetool."""
    script = _script()
    assert "appimage)" in script
    assert "build_appimage()" in script
    assert "appimagetool" in script
    assert "${APPIMAGE_OUTPUT_DIR}/${APP_NAME}-" in script


def test_appimage_is_x86_64_only() -> None:
    """The AppImage is produced only on Linux x86_64."""
    assert "The appimage target is supported only on Linux x86_64" in _script()


def _run_shell_fn(fn_name: str, args: list[str]) -> str:
    """Run a top-level ``fn_name`` from compile.sh in a fresh bash and return
    its stdout. Only used for pure helpers with no side effects."""
    match = re.search(rf"{fn_name}\(\) \{{.*?\n\}}", _script(), re.DOTALL)
    assert match, f"{fn_name} not found in compile.sh"
    result = subprocess.run(
        ["bash", "-c", f'{match.group(0)}\n{fn_name} "$@"', "_", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def test_macos_numeric_version_maps_semver_to_cfbundleversion() -> None:
    """CFBundleVersion must be a dotted numeric string: prerelease/build
    metadata stripped and padded to three components."""
    assert _run_shell_fn("_macos_numeric_version", ["1.2.0"]) == "1.2.0"
    assert _run_shell_fn("_macos_numeric_version", ["1.2.0-alpha.1"]) == "1.2.0"
    assert _run_shell_fn("_macos_numeric_version", ["1.2.0-rc.2"]) == "1.2.0"
    assert _run_shell_fn("_macos_numeric_version", ["1.2.0+build.5"]) == "1.2.0"
    assert _run_shell_fn("_macos_numeric_version", ["1.2"]) == "1.2.0"


def test_dmg_target_is_registered() -> None:
    script = _script()
    assert "dmg)" in script
    assert "build_dmg()" in script
    assert "packaging/macos/Info.plist" in script
    assert "hdiutil" in script


def test_dmg_is_darwin_only() -> None:
    assert "The dmg target is supported only on macOS" in _script()


def test_windows_installer_is_wired() -> None:
    """The Inno Setup installer must exist and be built by the release workflow."""
    repo = COMPILE_SH.parent
    assert (repo / "packaging" / "windows" / "hsync-desktop.iss").is_file()
    workflow = (repo / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "hsync-desktop.iss" in workflow
    assert "innosetup" in workflow


def test_docs_latest_download_names_are_created_by_the_release() -> None:
    """Every fixed-name asset the docs download from releases/latest/download must
    be created as an alias by the release workflow, so the link cannot 404. Names
    with the VERSION/ARCH placeholders are pinned examples, not aliases."""
    repo = COMPILE_SH.parent
    workflow = (repo / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    names: set[str] = set()
    for md in (repo / "docs").rglob("*.md"):
        for name in re.findall(
            r"releases/latest/download/([A-Za-z0-9._-]+)", md.read_text(encoding="utf-8")
        ):
            if name.startswith(repo.name) and "VERSION" not in name and "ARCH" not in name:
                names.add(name)
    names -= {"install.sh", "SHA256SUMS"}
    assert names, "expected at least one fixed latest/download asset in the docs"
    # The fixed-name targets are the `dst` half of the `src|dst` alias specs.
    aliases = set(re.findall(r'\|([A-Za-z0-9._-]+)"', workflow))
    missing = sorted(n for n in names if n not in aliases)
    assert not missing, f"docs reference latest aliases the workflow does not create: {missing}"


def test_pyinstaller_lookup_is_windows_aware() -> None:
    """Windows venvs put console scripts under ``Scripts/`` (with a ``.exe``
    suffix), not ``bin/``. A hardcoded ``bin/`` path makes the native Windows
    build abort with "PyInstaller not found" although Poetry installed it
    (the build runs ``poetry install`` then ``./compile.sh`` without activating
    the venv, so the PATH fallback misses too).
    """
    script = _script()
    assert 'if [[ "${OS_NAME}" == "windows" ]]; then' in script
    assert 'PYINSTALLER="${VENV_DIR}/Scripts/pyinstaller.exe"' in script
    assert 'PYINSTALLER="${VENV_DIR}/bin/pyinstaller"' in script


def test_run_script_console_path_is_windows_aware() -> None:
    """``run.sh`` must find the console script under ``Scripts/`` on Windows."""
    script = (COMPILE_SH.parent / "run.sh").read_text(encoding="utf-8")
    assert 'VENV_BIN_DIR="Scripts"' in script
    assert 'BIN_EXT=".exe"' in script
    assert 'readonly BIN="${SCRIPT_DIR}/.venv/${VENV_BIN_DIR}/hsync-desktop${BIN_EXT}"' in script


def test_dmg_staging_uses_an_apfs_clone_with_fallback() -> None:
    """The .dmg staging must not duplicate the .app physically on APFS: the
    macOS CI runners run out of space during hdiutil otherwise."""
    script = _script()
    assert 'cp -cR "${app}" "${stage}/" 2>/dev/null || cp -R "${app}" "${stage}/"' in script


def test_dmg_drops_the_pyinstaller_workpath_before_packaging() -> None:
    """The PyInstaller intermediates are freed before hdiutil needs room."""
    assert 'rm -rf "${work_dir}/pyinstaller"' in _script()


def test_release_frees_disk_space_before_packaging_the_dmg() -> None:
    workflow = (COMPILE_SH.parent / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    assert "CoreSimulator/Caches" in workflow
    assert "Library/Application Support/pyinstaller" in workflow


# ── Client/desktop version compatibility (build-time gate) ────────────────────

_VERIFY_RE = re.compile(r"^_verify_client_compatible\(\) \{.*?^\}", re.S | re.M)


def _verify_client_compatible_body() -> str:
    match = _VERIFY_RE.search(_script())
    assert match, "_verify_client_compatible() not found in compile.sh"
    return match.group(0)


def _run_verify(
    tmp_path: Path, expected: str, client_version: str | None
) -> subprocess.CompletedProcess[str]:
    """Run the extracted verifier against a fake client binary."""
    client = tmp_path / "hsync"
    body = "exit 1\n" if client_version is None else f'echo "hsync {client_version}"\n'
    client.write_text(f"#!/usr/bin/env bash\n{body}", encoding="utf-8")
    client.chmod(0o755)
    harness = "\n".join(
        [
            "log_info(){ :; }",
            'log_ok(){ echo "OK: $*" >&2; }',
            'log_warn(){ echo "WARN: $*" >&2; }',
            'log_error(){ echo "ERR: $*" >&2; }',
            '_expected_client_version(){ printf "%s" "$EXPECTED"; }',
            _verify_client_compatible_body(),
            '_verify_client_compatible "$CLIENT"',
        ]
    )
    return subprocess.run(
        ["bash", "-c", harness],
        env={"EXPECTED": expected, "CLIENT": str(client), "PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
    )


def test_verify_client_compatible_accepts_same_major(tmp_path: Path) -> None:
    proc = _run_verify(tmp_path, "1.0.3", "1.9.9")
    assert proc.returncode == 0, proc.stderr
    assert "matches HSYNC_VERSION" in proc.stderr


def test_verify_client_compatible_rejects_different_major(tmp_path: Path) -> None:
    proc = _run_verify(tmp_path, "1.0.3", "2.0.0")
    assert proc.returncode != 0
    assert "incompatible" in proc.stderr


def test_verify_client_compatible_skips_unrunnable_client(tmp_path: Path) -> None:
    proc = _run_verify(tmp_path, "1.0.3", None)
    assert proc.returncode == 0
    assert "skipping compatibility check" in proc.stderr


def test_bundling_verifies_the_client_and_skips_the_cross_arch_rpi() -> None:
    script = _script()
    assert "_verify_client_compatible" in script
    assert 'RPI_CLIENT_BINARY}" skip-verify' in script


class TestSelfContainedPackages:
    """deb/rpm bundle the client and drop the hsync-client dependency."""

    def test_host_deb_and_rpm_bundle_the_client(self):
        script = _script()
        # native + dmg + appimage + deb + rpm all bundle a client binary
        assert script.count('_collect_add_data_args "${CLIENT_BINARY}"') >= 3
        assert "_require_bundled_client" in script

    def test_deb_all_and_rpm_all_build_the_client_in_container(self):
        script = _script()
        assert script.count("poetry install --no-root --without dev") >= 2
        assert "./compile.sh -c" in script
        assert "hsync_desktop/bin/hsync" in script

    def test_deb_control_does_not_depend_on_hsync_client(self):
        control = (COMPILE_SH.parent / "packaging" / "deb" / "DEBIAN" / "control").read_text(
            encoding="utf-8"
        )
        assert "hsync-client" not in control

    def test_rpm_spec_does_not_require_hsync_client(self):
        spec = (COMPILE_SH.parent / "packaging" / "rpm" / "hsync-desktop.spec").read_text(
            encoding="utf-8"
        )
        assert "hsync-client" not in spec

    def test_deb_control_has_no_spurious_xinerama_dependency(self):
        """libxcb-xinerama0 is not linked or dlopened by the bundled Qt libs and
        blocked installation on hosts without it; it must not be declared."""
        control = (COMPILE_SH.parent / "packaging" / "deb" / "DEBIAN" / "control").read_text(
            encoding="utf-8"
        )
        assert "libxcb-xinerama0" not in control

    def test_deb_control_depends_is_computed_at_build_time(self):
        """The Depends line is computed from the payload, not hand-maintained."""
        control = (COMPILE_SH.parent / "packaging" / "deb" / "DEBIAN" / "control").read_text(
            encoding="utf-8"
        )
        assert "Depends: __DEPENDS__" in control
        script = _script()
        assert "_compute_runtime_depends" in script
        assert "_inject_shlib_depends" in script

    def test_rpm_requires_only_external_libraries(self):
        spec = (COMPILE_SH.parent / "packaging" / "rpm" / "hsync-desktop.spec").read_text(
            encoding="utf-8"
        )
        # Libraries that the bundled payload ships must not be declared.
        for pkg in ("libxkbcommon", "xcb-util-cursor", "fontconfig", "dbus-libs"):
            assert pkg not in spec
        # The libraries the payload needs from the system must be declared.
        for pkg in ("libxcb", "libdrm", "libwayland-client", "libwayland-egl"):
            assert pkg in spec

    def test_bundled_client_keeps_the_platform_extension(self):
        """find_hsync_binary() looks for hsync.exe on Windows, so the bundled
        client must keep the platform suffix (BIN_EXT)."""
        assert "hsync_desktop/bin/hsync${BIN_EXT}" in _script()
