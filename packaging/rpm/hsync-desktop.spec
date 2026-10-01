%global _hsync_pkgdir %{pkgdir}

Name:           hsync-desktop
Version:        __VERSION__
Release:        1%{?dist}
Summary:        HSYNC - desktop GUI for file synchronization

License:        MPL-2.0
URL:            https://github.com/albertsdk/hsync-desktop
Packager:       Alberto Basso <17047798+albertsdk@users.noreply.github.com>

# PyInstaller onedir bundle carries its own Python/Qt runtime and private
# shared libraries; rpm's automatic dependency scanner would mis-detect them.
# Declare the real runtime requirements explicitly (RHEL-family package names).
AutoReqProv:    no
Requires:       hsync-client
Requires:       glibc
Requires:       libglvnd-egl
Requires:       libglvnd-glx
Requires:       libxkbcommon
Requires:       libxkbcommon-x11
Requires:       xcb-util-cursor
Requires:       xcb-util-wm
Requires:       xcb-util-keysyms
Requires:       xcb-util-renderutil
Requires:       fontconfig
Requires:       dbus-libs

%description
hsync-desktop is the Qt (PySide6) graphical front-end of the HSYNC sync
network. It drives the hsync client binary and provides a tray-resident
interface to configure and monitor folder syncs.

Requires hsync-client, which provides the /usr/bin/hsync engine.

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
