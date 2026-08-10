# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2025 Alberto Basso

"""
Shared pytest fixtures for the hsync-desktop test suite.

Provides ``autouse`` fixtures that guarantee a clean environment for every test,
preventing state leakage between tests — especially critical for Qt-based
projects where a stray ``QApplication`` or registered callback can cascade.
"""

from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def _reset_i18n_callbacks() -> Generator[None]:
    """Clear registered language-change callbacks before and after each test.

    The ``i18n._language_change_callbacks`` list is module-level state.  A test
    that registers a callback and crashes before removing it would leak a stale
    closure into later tests.  This fixture ensures the list is always clean.
    """
    import hsync_desktop.i18n as i18n

    i18n._language_change_callbacks.clear()
    yield
    i18n._language_change_callbacks.clear()
