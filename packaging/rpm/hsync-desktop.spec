%global _hsync_pkgdir %{pkgdir}

Name:           hsync-desktop
Version:        __VERSION__
Release:        1%{?dist}
Summary:        HSYNC - desktop GUI for file synchronization

License:        BSD-3-Clause
URL:            https://github.com/albertsdk/hsync-desktop
Packager:       Alberto Basso <17047798+albertsdk@users.noreply.github.com>

# PyInstaller onedir bundle carries its own Python/Qt runtime and private
# shared libraries; rpm's automatic dependency scanner would mis-detect them.
# Declare the real runtime requirements explicitly (RHEL-family package names).
AutoReqProv:    no
Requires:       glibc
Requires:       zlib
Requires:       libglvnd-egl
Requires:       libglvnd-glx
Requires:       libdrm
Requires:       libwayland-client
Requires:       libwayland-cursor
Requires:       libwayland-egl
Requires:       libxcb

%description
hsync-desktop is the Qt (PySide6) graphical front-end of the HSYNC sync
network. It drives the bundled hsync engine and provides a tray-resident
interface to configure and monitor folder syncs.

%prep
exit 0

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}
cp -a %{_hsync_pkgdir}/. %{buildroot}/

%post
# Desktop database refresh is best-effort; not every RHEL-family host runs a
# desktop session at install time.
command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database %{_datadir}/applications 2>/dev/null || true
exit 0

%postun
command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database %{_datadir}/applications 2>/dev/null || true
exit 0

%files
%{_prefix}/lib/hsync-desktop
/usr/bin/hsync-desktop
%{_datadir}/applications/hsync-desktop.desktop
%{_datadir}/icons/hicolor/1024x1024/apps/hsync-desktop.png
%{_datadir}/icons/hicolor/scalable/apps/hsync-desktop.svg

%changelog
