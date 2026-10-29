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

    hsync-rendezvous hit the opposite case: its Poetry project lives in ``python/``,
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
    """The Inno Setup installer is built by the ``windows`` compile.sh target,
    which the release workflow invokes for the Windows matrix entry."""
    repo = COMPILE_SH.parent
    assert (repo / "packaging" / "windows" / "hsync-desktop.iss").is_file()
    script = _script()
    assert "build_windows()" in script
    assert "WINDOWS_ISS=" in script
    assert "packaging/windows" in script
    assert "ISCC" in script
    workflow = (repo / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "--target windows" in workflow
    assert "innosetup" in workflow


def test_windows_target_is_registered_in_dispatch() -> None:
    """``windows`` must be wired into main() and help like the other targets."""
    script = _script()
    assert "windows)" in script
    assert "build_windows()" in script
    assert "Supported targets:" in script


def test_windows_is_windows_x64_only() -> None:
    """Inno Setup/ImageMagick/the .ico run on the host and the installer is x64:
    the target must refuse other hosts and architectures."""
    script = _script()
    assert "The windows target is supported only on Windows" in script
    assert "The windows target is supported only on Windows x64" in script


def test_windows_numeric_version_strips_prerelease() -> None:
    """VersionInfoVersion must be numeric: prerelease/build metadata is stripped."""
    assert _run_shell_fn("_windows_numeric_version", ["1.2.0"]) == "1.2.0"
    assert _run_shell_fn("_windows_numeric_version", ["1.2.0-alpha.1"]) == "1.2.0"
    assert _run_shell_fn("_windows_numeric_version", ["1.2.0+build.5"]) == "1.2.0"


def test_windows_target_builds_installer_and_portable_zip() -> None:
    """The target bundles the client, renders the .ico, runs ISCC and assembles a
    portable zip without assuming an external ``zip``/``7z`` binary."""
    body = _shell_fn_body("build_windows")
    assert "_require_bundled_client" in body
    assert "_windows_build_ico" in body
    assert "_onefile_pyi_flags" in body
    assert "make_archive" in body
    assert _shell_fn_body("_windows_build_ico")


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

    def test_license_is_bundled_for_the_help_viewer(self):
        """The Help → License viewer reads the bundled LICENSE file."""
        assert "--add-data=LICENSE:hsync_desktop" in _script()

    def test_every_client_bundling_target_requires_the_client(self):
        """Regression: native/dmg/appimage/rpi advertised a bundled client but
        only deb/rpm enforced it, so a missing client silently shipped a
        non-self-contained artifact (the reported "hsync binary not found")."""
        for fn in (
            "build_binary",
            "build_rpi",
            "build_deb",
            "build_rpm",
            "build_appimage",
            "build_dmg",
        ):
            assert "_require_bundled_client" in _shell_fn_body(fn), fn

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
        assert "packaging/deb/deb-depends.sh" in script
        helper = (COMPILE_SH.parent / "packaging" / "deb" / "deb-depends.sh").read_text(
            encoding="utf-8"
        )
        assert "_compute_runtime_depends" in helper
        assert "_inject_shlib_depends" in helper

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


# ── Bundled client stays executable in a staged .deb/.rpm payload ─────────────


def _shell_fn_body(name: str) -> str:
    match = re.search(rf"^{name}\(\) \{{.*?^\}}", _script(), re.S | re.M)
    assert match, f"{name}() not found in compile.sh"
    return match.group(0)


def _run_stage_harness(script: str) -> subprocess.CompletedProcess[str]:
    preamble = "\n".join(
        [
            "set -euo pipefail",
            'APP_NAME="hsync-desktop"',
            'BIN_EXT=""',
            'DEB_SRC_DATA="$(pwd)/packaging/deb"',
            "log_info(){ :; }",
            "log_ok(){ :; }",
            "log_warn(){ :; }",
            'log_error(){ echo "ERR: $*" >&2; }',
            "log_step(){ :; }",
        ]
    )
    return subprocess.run(
        ["bash", "-c", f"{preamble}\n{script}"],
        cwd=COMPILE_SH.parent,
        capture_output=True,
        text=True,
    )


class TestBundledClientStaysExecutable:
    """The stage finalisers must not strip the exec bit from the bundled client.

    They chmod every usr/ file to 0644; a non-executable bundled ``hsync`` makes
    ``find_hsync_binary()`` reject it, so the GUI silently fails to start a sync
    (the reported ".deb: clicking Yes does nothing" regression).
    """

    def test_deb_finalize_restores_the_client_exec_bit(self, tmp_path: Path) -> None:
        stage = tmp_path / "stage"
        client = stage / "usr/lib/hsync-desktop/_internal/hsync_desktop/bin/hsync"
        client.parent.mkdir(parents=True)
        client.write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
        client.chmod(0o755)  # PyInstaller leaves it executable before staging
        gui = stage / "usr/lib/hsync-desktop/hsync-desktop"
        gui.write_text("#!/bin/sh\n", encoding="utf-8")
        gui.chmod(0o755)

        proc = _run_stage_harness(
            "\n".join(
                [
                    _shell_fn_body("_restore_bundled_client_exec"),
                    _shell_fn_body("_finalize_deb_stage"),
                    f'_finalize_deb_stage "{stage}"',
                ]
            )
        )

        assert proc.returncode == 0, proc.stderr
        assert os.access(client, os.X_OK), "bundled hsync client lost its exec bit"
        assert os.access(gui, os.X_OK)

    def test_rpm_stage_restores_the_client_exec_bit(self, tmp_path: Path) -> None:
        built = tmp_path / "hsync-desktop"
        client = built / "_internal/hsync_desktop/bin/hsync"
        client.parent.mkdir(parents=True)
        client.write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
        client.chmod(0o755)
        (built / "hsync-desktop").write_text("#!/bin/sh\n", encoding="utf-8")
        (built / "hsync-desktop").chmod(0o755)

        stage = tmp_path / "stage"
        proc = _run_stage_harness(
            "\n".join(
                [
                    _shell_fn_body("_restore_bundled_client_exec"),
                    _shell_fn_body("_stage_rpm_buildroot"),
                    f'_stage_rpm_buildroot "{stage}" "{built}"',
                ]
            )
        )

        assert proc.returncode == 0, proc.stderr
        staged_client = stage / "usr/lib/hsync-desktop/_internal/hsync_desktop/bin/hsync"
        assert os.access(staged_client, os.X_OK), "bundled hsync client lost its exec bit"

    def test_restore_fails_the_build_when_the_client_is_missing(self, tmp_path: Path) -> None:
        (tmp_path / "stage/usr/lib/hsync-desktop").mkdir(parents=True)
        proc = _run_stage_harness(
            "\n".join(
                [
                    _shell_fn_body("_restore_bundled_client_exec"),
                    f'_restore_bundled_client_exec "{tmp_path}/stage"',
                ]
            )
        )
        assert proc.returncode != 0
        assert "missing the bundled hsync-client" in proc.stderr
