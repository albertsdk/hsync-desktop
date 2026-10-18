# syntax=docker/dockerfile:1.6
#
# HSYNC — RPM builder image (x86_64 / aarch64)
#
# Single-stage builder on a RHEL-family base, 64-bit only: RHEL/Rocky publish
# no armv7 userspace, so RPM covers x86_64 + aarch64 only (armv7 stays on the
# .deb armhf / rpi binaries — and is unsupported for this GUI anyway, since
# PySide6 publishes no armv7 Linux wheels).
#
# BASE_IMAGE is chosen per arch by the rpm-all target (see compile.sh):
# rockylinux:9 (glibc 2.34) for x86_64, whose PySide6 wheel is manylinux_2_34,
# and almalinux:10 (glibc 2.39) for aarch64, whose wheel is manylinux_2_39.
#
# Installs Python 3.12 (AppStream), Poetry and rpm-build; ready to:
#   1. invoke PyInstaller on the project sources mounted at /repo
#   2. assemble a .rpm with rpmbuild from a staged buildroot mounted at /pkg
#
# Multi-arch manifest, so ``--platform`` selects the arch:
#   linux/amd64  -> x86_64
#   linux/arm64  -> aarch64
# ``BASE_IMAGE`` (default rockylinux:9) is overridden per arch by rpm-all.
#
# Built and consumed locally by:  compile.sh --target rpm-all
# Never published to any registry.

ARG BASE_IMAGE=rockylinux:9
ARG TARGET_PLATFORM=linux/amd64

FROM --platform=${TARGET_PLATFORM} ${BASE_IMAGE}

# POETRY_VIRTUALENVS_IN_PROJECT must NOT be set here: an environment variable
# overrides the POETRY_VIRTUALENVS_IN_PROJECT=1 the container command exports
# for the hsync-client in-project .venv, which that build requires.
ENV LC_ALL=C.UTF-8 \
    PATH=/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VIRTUALENVS_CREATE=true \
    POETRY_NO_INTERACTION=1

# Python 3.12 from the distro, binutils for PyInstaller --strip, rpm-build for
# packaging, plus the minimal X/Qt runtime libraries the frozen GUI links
# against at run time (also declared as Requires: in the spec). PySide6 ships
# binary manylinux wheels, so it installs on the matching glibc baseline
# without a source build.
RUN dnf -y install --setopt=install_weak_deps=False \
        python3.12 \
        python3.12-pip \
        ca-certificates \
        binutils \
        rpm-build \
        redhat-rpm-config \
        libglvnd-egl \
        libglvnd-glx \
        libxkbcommon \
        libxkbcommon-x11 \
        xcb-util-cursor \
        xcb-util-wm \
        xcb-util-keysyms \
        xcb-util-renderutil \
        fontconfig \
        dbus-libs \
    && dnf clean all

RUN python3.12 -m pip install --no-cache-dir --prefer-binary "poetry==2.3.2"

WORKDIR /src

CMD ["bash"]
