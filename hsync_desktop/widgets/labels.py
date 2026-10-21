# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025 Alberto Basso

"""Muted helper-text labels.

Consumers: the setup wizard (`wizard/widgets.py::RadioCard` and the wizard
pages) and the Settings tab descriptions (`settings/tab_layout.py`). Both read
the same ``QLabel#mutedHint`` rule of the theme stylesheet, so the visual
language stays single-sourced.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel

__all__ = ["muted_label"]


def muted_label(text: str = "") -> QLabel:
    """A muted, word-wrapped helper label (object name ``mutedHint``)."""

    label = QLabel(text)
    label.setObjectName("mutedHint")
    label.setWordWrap(True)
    return label
